"""
GitHub PR 监控器 - GUI主程序 (PyQt5版本)
跨平台支持 (Mac/Windows)
"""

import sys
import json
import os
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QTextEdit, QSpinBox,
    QGroupBox, QMessageBox, QTableWidget, QTableWidgetItem,
    QHeaderView, QAbstractItemView, QComboBox
)
from PyQt5.QtCore import QTimer, QThread, pyqtSignal, Qt
from PyQt5.QtGui import QFont, QColor
from datetime import datetime
from github_api import PRMonitor, GitHubAPIError


class FetchThread(QThread):
    """后台获取数据的线程 - 支持多个PR"""
    data_fetched = pyqtSignal(str, dict)  # (pr_url, pr_status)
    error_occurred = pyqtSignal(str, str)  # (pr_url, error_msg)

    def __init__(self, monitor, pr_list):
        super().__init__()
        self.monitor = monitor
        self.pr_list = pr_list  # 列表包含 {'url': str, 'owner': str, 'repo': str, 'pull_number': str}

    def run(self):
        """获取所有PR的状态"""
        for pr_info in self.pr_list:
            try:
                pr_status = self.monitor.get_pr_status(
                    pr_info['owner'],
                    pr_info['repo'],
                    pr_info['pull_number']
                )
                pr_status['owner'] = pr_info['owner']
                pr_status['repo'] = pr_info['repo']
                pr_status['pull_number'] = pr_info['pull_number']
                self.data_fetched.emit(pr_info['url'], pr_status)
            except GitHubAPIError as e:
                self.error_occurred.emit(pr_info['url'], str(e))


class PRMonitorGUI(QMainWindow):
    """PR监控器GUI应用 - 支持多PR监控"""

    CONFIG_FILE = os.path.expanduser('~/.github_pr_monitor_config.json')

    def __init__(self):
        super().__init__()
        self.monitor = PRMonitor()
        self.monitoring = False
        self.pr_list = []  # 存储多个PR信息: [{'url': str, 'owner': str, 'repo': str, 'pull_number': str, 'status': dict}, ...]
        self.timer = QTimer()
        self.timer.timeout.connect(self.fetch_and_display)
        self.fetch_thread = None

        self.init_ui()
        self.load_config()  # 加载保存的配置

    def init_ui(self):
        """初始化UI - 支持多PR监控"""
        self.setWindowTitle("GitHub PR 监控器 (多PR版)")
        self.setGeometry(100, 100, 1000, 800)

        # 创建中央部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # 主布局
        main_layout = QVBoxLayout()
        central_widget.setLayout(main_layout)

        # ===== GitHub Token配置区域 =====
        token_group = QGroupBox("GitHub Token 配置")
        token_layout = QHBoxLayout()

        token_label = QLabel("Token:")
        token_label.setFixedWidth(60)
        self.token_input = QLineEdit()
        self.token_input.setPlaceholderText("ghp_xxxxxxxxxxxxxxxxxxxx (可选，提高API限制到5000次/小时)")
        self.token_input.setEchoMode(QLineEdit.Password)

        self.set_token_button = QPushButton("设置Token")
        self.set_token_button.clicked.connect(self.set_token)
        self.set_token_button.setFixedWidth(100)

        token_layout.addWidget(token_label)
        token_layout.addWidget(self.token_input)
        token_layout.addWidget(self.set_token_button)
        token_group.setLayout(token_layout)

        # ===== PR管理区域 =====
        pr_manage_group = QGroupBox("PR 管理")
        pr_manage_layout = QVBoxLayout()

        # PR添加行
        add_pr_layout = QHBoxLayout()
        pr_url_label = QLabel("PR链接:")
        pr_url_label.setFixedWidth(60)
        self.pr_url_input = QLineEdit()
        self.pr_url_input.setPlaceholderText("https://github.com/owner/repo/pull/123")

        self.add_pr_button = QPushButton("添加PR")
        self.add_pr_button.clicked.connect(self.add_pr)
        self.add_pr_button.setFixedWidth(100)

        self.remove_pr_button = QPushButton("删除选中")
        self.remove_pr_button.clicked.connect(self.remove_pr)
        self.remove_pr_button.setFixedWidth(100)

        add_pr_layout.addWidget(pr_url_label)
        add_pr_layout.addWidget(self.pr_url_input)
        add_pr_layout.addWidget(self.add_pr_button)
        add_pr_layout.addWidget(self.remove_pr_button)

        # PR列表表格
        self.pr_table = QTableWidget()
        self.pr_table.setColumnCount(6)
        self.pr_table.setHorizontalHeaderLabels(['PR链接', '标题', '状态', 'CI', '审查', '最后更新'])
        self.pr_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.pr_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.pr_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.pr_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.pr_table.setMinimumHeight(200)

        pr_manage_layout.addLayout(add_pr_layout)
        pr_manage_layout.addWidget(self.pr_table)
        pr_manage_group.setLayout(pr_manage_layout)

        # ===== 监控控制区域 =====
        control_group = QGroupBox("监控控制")
        control_layout = QHBoxLayout()

        interval_label = QLabel("刷新间隔:")
        interval_label.setFixedWidth(80)
        self.interval_spinbox = QSpinBox()
        self.interval_spinbox.setRange(10, 300)
        self.interval_spinbox.setValue(30)
        self.interval_spinbox.setSuffix(" 秒")
        self.interval_spinbox.setFixedWidth(100)

        self.start_button = QPushButton("开始监控")
        self.start_button.clicked.connect(self.start_monitoring)
        self.start_button.setFixedWidth(100)

        self.stop_button = QPushButton("停止监控")
        self.stop_button.clicked.connect(self.stop_monitoring)
        self.stop_button.setEnabled(False)
        self.stop_button.setFixedWidth(100)

        self.refresh_button = QPushButton("立即刷新")
        self.refresh_button.clicked.connect(self.manual_refresh)
        self.refresh_button.setFixedWidth(100)

        control_layout.addWidget(interval_label)
        control_layout.addWidget(self.interval_spinbox)
        control_layout.addWidget(self.start_button)
        control_layout.addWidget(self.stop_button)
        control_layout.addWidget(self.refresh_button)
        control_layout.addStretch()
        control_group.setLayout(control_layout)

        # ===== 状态显示区域 =====
        status_group = QGroupBox("监控状态")
        status_layout = QVBoxLayout()
        self.status_label = QLabel("未开始监控 | PR数量: 0")
        self.status_label.setStyleSheet("color: gray;")
        status_layout.addWidget(self.status_label)
        status_group.setLayout(status_layout)

        # 添加所有组件到主布局
        main_layout.addWidget(token_group)
        main_layout.addWidget(pr_manage_group)
        main_layout.addWidget(control_group)
        main_layout.addWidget(status_group)

    def set_token(self):
        """设置GitHub Token"""
        token = self.token_input.text().strip()
        if token:
            self.monitor.set_token(token)
            QMessageBox.information(self, "成功", "GitHub Token已设置\nAPI速率限制已提升到5000次/小时")
            self.save_config()  # 保存配置
        else:
            self.monitor.set_token(None)
            QMessageBox.information(self, "提示", "已清除Token")

    def add_pr(self):
        """添加PR到监控列表"""
        url = self.pr_url_input.text().strip()

        if not url:
            QMessageBox.warning(self, "警告", "请输入PR链接")
            return

        # 检查是否已存在
        for pr in self.pr_list:
            if pr['url'] == url:
                QMessageBox.warning(self, "警告", "该PR已在监控列表中")
                return

        # 解析URL
        pr_info = self.monitor.parse_pr_url(url)
        if not pr_info:
            QMessageBox.critical(
                self,
                "错误",
                "无效的GitHub PR链接\n\n格式示例:\nhttps://github.com/owner/repo/pull/123"
            )
            return

        # 添加到列表
        pr_info['url'] = url
        pr_info['status'] = None
        self.pr_list.append(pr_info)

        # 更新表格
        self.update_pr_table()

        # 清空输入框
        self.pr_url_input.clear()

        # 更新状态
        self.update_status(f"已添加PR | 总数: {len(self.pr_list)}", "success")

        # 保存配置
        self.save_config()

    def remove_pr(self):
        """删除选中的PR"""
        selected_rows = set()
        for item in self.pr_table.selectedItems():
            selected_rows.add(item.row())

        if not selected_rows:
            QMessageBox.warning(self, "警告", "请先选择要删除的PR")
            return

        # 按行号倒序删除（避免索引变化问题）
        for row in sorted(selected_rows, reverse=True):
            if row < len(self.pr_list):
                del self.pr_list[row]

        # 更新表格
        self.update_pr_table()

        # 更新状态
        self.update_status(f"已删除选中PR | 总数: {len(self.pr_list)}", "success")

        # 保存配置
        self.save_config()

    def update_pr_table(self):
        """更新PR列表表格"""
        self.pr_table.setRowCount(len(self.pr_list))

        for row, pr in enumerate(self.pr_list):
            # PR链接
            url_item = QTableWidgetItem(pr['url'])
            self.pr_table.setItem(row, 0, url_item)

            # 如果有状态信息，显示详细信息
            if pr.get('status'):
                status = pr['status']

                # 标题
                title_item = QTableWidgetItem(status.get('title', 'N/A'))
                self.pr_table.setItem(row, 1, title_item)

                # PR状态
                state = status.get('state', 'unknown')
                merged = status.get('merged', False)
                if merged:
                    state_text = '✓ 已合并'
                    state_color = QColor(0, 128, 0)
                elif state == 'open':
                    state_text = '● 开放中'
                    state_color = QColor(0, 0, 255)
                elif state == 'closed':
                    state_text = '✗ 已关闭'
                    state_color = QColor(255, 0, 0)
                else:
                    state_text = state
                    state_color = QColor(128, 128, 128)

                state_item = QTableWidgetItem(state_text)
                state_item.setForeground(state_color)
                self.pr_table.setItem(row, 2, state_item)

                # CI状态
                ci_status = status.get('ci_status', 'unknown')
                ci_map = {
                    'success': ('✓ 通过', QColor(0, 128, 0)),
                    'pending': ('⏳ 进行中', QColor(255, 165, 0)),
                    'failure': ('✗ 失败', QColor(255, 0, 0)),
                    'error': ('✗ 错误', QColor(255, 0, 0)),
                }
                ci_text, ci_color = ci_map.get(ci_status, (ci_status, QColor(128, 128, 128)))
                ci_item = QTableWidgetItem(ci_text)
                ci_item.setForeground(ci_color)
                self.pr_table.setItem(row, 3, ci_item)

                # 审查状态
                review_status = status.get('review_status', 'unknown')
                review_map = {
                    'approved': ('✓ 已批准', QColor(0, 128, 0)),
                    'changes_requested': ('✗ 需修改', QColor(255, 0, 0)),
                    'pending': ('⏳ 待审查', QColor(255, 165, 0)),
                }
                review_text, review_color = review_map.get(review_status, (review_status, QColor(128, 128, 128)))
                review_item = QTableWidgetItem(review_text)
                review_item.setForeground(review_color)
                self.pr_table.setItem(row, 4, review_item)

                # 最后更新
                updated_item = QTableWidgetItem(status.get('updated_at', 'N/A'))
                self.pr_table.setItem(row, 5, updated_item)
            else:
                # 没有状态信息，显示占位符
                for col in range(1, 6):
                    placeholder_item = QTableWidgetItem('加载中...' if col == 1 else '-')
                    placeholder_item.setForeground(QColor(128, 128, 128))
                    self.pr_table.setItem(row, col, placeholder_item)

    def start_monitoring(self):
        """开始监控所有PR"""
        if not self.pr_list:
            QMessageBox.warning(self, "警告", "请先添加要监控的PR")
            return

        self.monitoring = True

        # 更新按钮状态
        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.interval_spinbox.setEnabled(False)
        self.add_pr_button.setEnabled(False)
        self.remove_pr_button.setEnabled(False)

        # 更新状态
        self.update_status(f"正在监控中... | PR数量: {len(self.pr_list)}", "info")

        # 立即获取一次数据
        self.fetch_and_display()

        # 启动定时器
        interval = self.interval_spinbox.value() * 1000  # 转换为毫秒
        self.timer.start(interval)

    def stop_monitoring(self):
        """停止监控"""
        self.monitoring = False
        self.timer.stop()

        # 更新按钮状态
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.interval_spinbox.setEnabled(True)
        self.add_pr_button.setEnabled(True)
        self.remove_pr_button.setEnabled(True)

        # 更新状态
        self.update_status(f"已停止监控 | PR数量: {len(self.pr_list)}", "warning")

    def fetch_and_display(self):
        """获取并显示所有PR信息"""
        if not self.monitoring or not self.pr_list:
            return

        # 如果上一个线程还在运行，不启动新线程
        if self.fetch_thread and self.fetch_thread.isRunning():
            return

        # 创建并启动后台线程
        self.fetch_thread = FetchThread(self.monitor, self.pr_list)
        self.fetch_thread.data_fetched.connect(self.on_pr_data_fetched)
        self.fetch_thread.error_occurred.connect(self.on_pr_error)
        self.fetch_thread.start()

    def on_pr_data_fetched(self, pr_url, pr_status):
        """处理获取到的PR数据"""
        # 更新pr_list中对应的状态
        for pr in self.pr_list:
            if pr['url'] == pr_url:
                pr['status'] = pr_status
                break

        # 更新表格显示
        self.update_pr_table()

        # 更新状态
        current_time = datetime.now().strftime('%H:%M:%S')
        self.update_status(f"监控中 - 最后更新: {current_time} | PR数量: {len(self.pr_list)}", "success")

    def on_pr_error(self, pr_url, error_msg):
        """处理PR获取错误"""
        # 在对应的PR状态中标记错误
        for pr in self.pr_list:
            if pr['url'] == pr_url:
                pr['status'] = {
                    'title': f'错误: {error_msg}',
                    'state': 'error',
                    'merged': False,
                    'author': 'N/A',
                    'created_at': 'N/A',
                    'updated_at': 'N/A',
                    'ci_status': 'unknown',
                    'review_status': 'unknown',
                    'url': pr_url
                }
                break

        # 更新表格显示
        self.update_pr_table()

    def manual_refresh(self):
        """手动刷新"""
        if self.monitoring and self.pr_list:
            self.update_status("正在刷新...", "info")
            self.fetch_and_display()
        else:
            QMessageBox.information(self, "提示", "请先开始监控")

    def load_config(self):
        """加载保存的配置"""
        if not os.path.exists(self.CONFIG_FILE):
            return

        try:
            with open(self.CONFIG_FILE, 'r', encoding='utf-8') as f:
                config = json.load(f)

            # 加载Token
            token = config.get('token', '')
            if token:
                self.token_input.setText(token)
                self.monitor.set_token(token)

            # 加载PR列表
            pr_urls = config.get('pr_list', [])
            for url in pr_urls:
                pr_info = self.monitor.parse_pr_url(url)
                if pr_info:
                    pr_info['url'] = url
                    pr_info['status'] = None
                    self.pr_list.append(pr_info)

            # 加载刷新间隔
            interval = config.get('interval', 30)
            self.interval_spinbox.setValue(interval)

            # 更新表格
            self.update_pr_table()

            # 更新状态
            if self.pr_list:
                self.update_status(f"已加载配置 | PR数量: {len(self.pr_list)}", "success")

        except Exception as e:
            print(f"加载配置失败: {e}")

    def save_config(self):
        """保存配置"""
        try:
            config = {
                'token': self.token_input.text().strip(),
                'pr_list': [pr['url'] for pr in self.pr_list],
                'interval': self.interval_spinbox.value()
            }

            with open(self.CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2, ensure_ascii=False)

        except Exception as e:
            print(f"保存配置失败: {e}")

    def update_status(self, message, status_type=""):
        """更新状态标签"""
        self.status_label.setText(message)

        if status_type == "success":
            self.status_label.setStyleSheet("color: green;")
        elif status_type == "error":
            self.status_label.setStyleSheet("color: red;")
        elif status_type == "warning":
            self.status_label.setStyleSheet("color: orange;")
        elif status_type == "info":
            self.status_label.setStyleSheet("color: blue;")
        else:
            self.status_label.setStyleSheet("color: gray;")


def main():
    """主函数"""
    app = QApplication(sys.argv)
    window = PRMonitorGUI()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
