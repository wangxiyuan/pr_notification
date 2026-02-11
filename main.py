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
from PyQt5.QtCore import QTimer, QThread, pyqtSignal, Qt, pyqtSlot, QMetaObject, Q_ARG, QUrl
from PyQt5.QtGui import QFont, QColor, QDesktopServices
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

        # 倒计时相关
        self.countdown_timer = QTimer()
        self.countdown_timer.timeout.connect(self.update_countdown)
        self.remaining_seconds = 0

        # 最后刷新时间
        self.last_refresh_time = None

        self.init_ui()
        self.load_config()  # 加载保存的配置

    def init_ui(self):
        """初始化UI - 支持多PR监控"""
        self.setWindowTitle("GitHub PR 监控器")
        self.setGeometry(100, 100, 1200, 900)  # 增大窗口尺寸
        self.center()  # 居中显示

        # 创建中央部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # 主布局
        main_layout = QVBoxLayout()
        central_widget.setLayout(main_layout)

        # ===== GitHub Token配置区域 =====
        token_group = QGroupBox("GitHub Token 配置")
        token_group.setStyleSheet("QGroupBox { font-size: 12pt; font-weight: bold; }")
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
        pr_manage_group.setStyleSheet("QGroupBox { font-size: 12pt; font-weight: bold; }")
        pr_manage_layout = QVBoxLayout()

        # PR添加行（三段式）
        add_pr_layout = QHBoxLayout()

        # 用户名/组织名区域（含增删功能）
        owner_label = QLabel("用户名/组织:")
        owner_label.setFixedWidth(100)
        self.owner_combo = QComboBox()
        self.owner_combo.setEditable(True)  # 支持手动输入
        self.owner_combo.addItem("vllm-project")  # 默认值
        self.owner_combo.setFixedWidth(150)

        # 添加用户名/组织名按钮
        self.add_owner_button = QPushButton("添加")
        self.add_owner_button.clicked.connect(self.add_owner)
        self.add_owner_button.setFixedWidth(60)

        # 删除用户名/组织名按钮
        self.delete_owner_button = QPushButton("删除")
        self.delete_owner_button.clicked.connect(self.delete_owner)
        self.delete_owner_button.setFixedWidth(60)

        # 仓库下拉菜单
        repo_label = QLabel("仓库:")
        repo_label.setFixedWidth(50)
        self.repo_combo = QComboBox()
        self.repo_combo.setFixedWidth(180)

        # PR ID输入框
        pr_id_label = QLabel("PR ID:")
        pr_id_label.setFixedWidth(60)
        self.pr_id_input = QLineEdit()
        self.pr_id_input.setPlaceholderText("123")
        self.pr_id_input.setFixedWidth(100)

        self.add_pr_button = QPushButton("添加PR")
        self.add_pr_button.clicked.connect(self.add_pr)
        self.add_pr_button.setFixedWidth(100)

        self.remove_pr_button = QPushButton("删除选中")
        self.remove_pr_button.clicked.connect(self.remove_pr)
        self.remove_pr_button.setFixedWidth(100)

        # 绑定用户名/组织名变化事件
        self.owner_combo.currentTextChanged.connect(self.load_repos)

        # 初始化仓库列表
        self.load_repos("vllm-project")

        add_pr_layout.addWidget(owner_label)
        add_pr_layout.addWidget(self.owner_combo)
        add_pr_layout.addWidget(self.add_owner_button)
        add_pr_layout.addWidget(self.delete_owner_button)
        add_pr_layout.addWidget(repo_label)
        add_pr_layout.addWidget(self.repo_combo)
        add_pr_layout.addWidget(pr_id_label)
        add_pr_layout.addWidget(self.pr_id_input)
        add_pr_layout.addWidget(self.add_pr_button)
        add_pr_layout.addWidget(self.remove_pr_button)

        pr_manage_layout.addLayout(add_pr_layout)
        pr_manage_group.setLayout(pr_manage_layout)

        # ===== 监控状态区域（放在表格上方）=====
        status_group = QGroupBox("监控状态")
        status_group.setStyleSheet("QGroupBox { font-size: 12pt; font-weight: bold; }")
        status_layout = QVBoxLayout()
        self.status_label = QLabel("未开始监控 | PR数量: 0")
        self.status_label.setStyleSheet("color: gray;")

        # 倒计时标签
        self.countdown_label = QLabel("下次刷新: --")
        self.countdown_label.setStyleSheet("color: gray; font-size: 9pt;")

        status_layout.addWidget(self.status_label)
        status_layout.addWidget(self.countdown_label)
        status_group.setLayout(status_layout)

        # ===== PR列表表格 =====
        pr_table_group = QGroupBox("PR 列表")
        pr_table_group.setStyleSheet("QGroupBox { font-size: 12pt; font-weight: bold; }")
        pr_table_layout = QVBoxLayout()

        self.pr_table = QTableWidget()
        self.pr_table.setColumnCount(9)  # 增加一列用于作者名
        self.pr_table.setHorizontalHeaderLabels(['用户/组织', '仓库', 'PR ID', '标题', '作者', '状态', 'CI', '审查', '最后更新'])
        self.pr_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.pr_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.pr_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.pr_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        self.pr_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self.pr_table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeToContents)
        self.pr_table.horizontalHeader().setSectionResizeMode(6, QHeaderView.ResizeToContents)
        self.pr_table.horizontalHeader().setSectionResizeMode(7, QHeaderView.ResizeToContents)
        self.pr_table.horizontalHeader().setSectionResizeMode(8, QHeaderView.ResizeToContents)
        self.pr_table.setSelectionBehavior(QAbstractItemView.SelectItems)  # 允许选择单个单元格
        self.pr_table.setSelectionMode(QAbstractItemView.SingleSelection)  # 单选模式
        self.pr_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.pr_table.setMinimumHeight(400)  # 增大表格最小高度

        # 添加单元格点击事件（用于点击PR ID打开链接）
        self.pr_table.cellClicked.connect(self.on_cell_clicked)

        # 添加右键菜单支持
        self.pr_table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.pr_table.customContextMenuRequested.connect(self.show_context_menu)

        pr_table_layout.addWidget(self.pr_table)
        pr_table_group.setLayout(pr_table_layout)

        # ===== 监控控制区域 =====
        control_group = QGroupBox("监控控制")
        control_group.setStyleSheet("QGroupBox { font-size: 12pt; font-weight: bold; }")
        control_layout = QHBoxLayout()

        interval_label = QLabel("刷新间隔:")
        interval_label.setFixedWidth(80)

        # 刷新间隔下拉选项
        self.interval_combo = QComboBox()
        self.interval_options = {
            '10秒': 10,
            '30秒': 30,
            '1分钟': 60,
            '3分钟': 180,
            '5分钟': 300,
            '30分钟': 1800,
            '1小时': 3600
        }
        self.interval_combo.addItems(list(self.interval_options.keys()))
        self.interval_combo.setCurrentText('30秒')  # 默认30秒
        self.interval_combo.setFixedWidth(100)

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
        control_layout.addWidget(self.interval_combo)
        control_layout.addWidget(self.start_button)
        control_layout.addWidget(self.stop_button)
        control_layout.addWidget(self.refresh_button)
        control_layout.addStretch()
        control_group.setLayout(control_layout)

        # 添加所有组件到主布局（新的顺序）
        main_layout.addWidget(token_group)
        main_layout.addWidget(pr_manage_group)
        main_layout.addWidget(status_group)  # 监控状态放在表格上方
        main_layout.addWidget(pr_table_group)  # PR列表表格
        main_layout.addWidget(control_group)

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

    def load_repos(self, owner):
        """根据用户名/组织名加载仓库列表"""
        if not owner:
            return
        
        self.repo_combo.clear()
        # 异步加载仓库列表（避免UI卡顿）
        self.repo_combo.addItem("加载中...")
        self.repo_combo.setEnabled(False)
        
        # 使用线程加载仓库列表
        from threading import Thread
        def fetch_repos():
            repos = self.monitor.get_user_repos(owner)
            # 在主线程更新UI
            QMetaObject.invokeMethod(self, "_update_repo_combo", Qt.QueuedConnection, 
                                    Q_ARG(list, repos))
        
        Thread(target=fetch_repos).start()
    
    @pyqtSlot(list)
    def _update_repo_combo(self, repos):
        """更新仓库下拉菜单"""
        self.repo_combo.clear()
        self.repo_combo.setEnabled(True)
        if repos:
            self.repo_combo.addItems(repos)
        else:
            self.repo_combo.addItem("无可用仓库")
            self.repo_combo.setEnabled(False)
    
    def add_owner(self):
        """添加用户名/组织名"""
        owner_text = self.owner_combo.currentText().strip()
        if not owner_text:
            QMessageBox.warning(self, "警告", "请输入用户名/组织名")
            return
        
        # 检查是否已存在
        for i in range(self.owner_combo.count()):
            if self.owner_combo.itemText(i) == owner_text:
                QMessageBox.warning(self, "警告", "该用户名/组织名已存在")
                return
        
        # 添加到下拉菜单
        self.owner_combo.addItem(owner_text)
        self.owner_combo.setCurrentText(owner_text)
        
        # 保存配置
        self.save_config()
        QMessageBox.information(self, "成功", f"已添加用户名/组织名: {owner_text}")
    
    def delete_owner(self):
        """删除选中的用户名/组织名"""
        current_index = self.owner_combo.currentIndex()
        if current_index < 0:
            QMessageBox.warning(self, "警告", "请先选择要删除的用户名/组织名")
            return
        
        # 不允许删除最后一个选项
        if self.owner_combo.count() == 1:
            QMessageBox.warning(self, "警告", "至少需要保留一个用户名/组织名")
            return
        
        # 不允许删除默认的vllm-project
        if self.owner_combo.itemText(current_index) == "vllm-project":
            QMessageBox.warning(self, "警告", "不允许删除默认的vllm-project")
            return
        
        # 删除选中项
        self.owner_combo.removeItem(current_index)
        
        # 保存配置
        self.save_config()
        QMessageBox.information(self, "成功", "已删除选中的用户名/组织名")
        
        # 重新加载当前选中用户名/组织名的仓库列表
        self.load_repos(self.owner_combo.currentText())

    def get_interval_seconds(self):
        """获取当前选中的刷新间隔（秒）"""
        current_text = self.interval_combo.currentText()
        return self.interval_options.get(current_text, 30)

    def add_pr(self):
        """添加PR到监控列表"""
        # 获取三段式输入
        owner = self.owner_combo.currentText().strip()
        repo = self.repo_combo.currentText().strip()
        pr_id = self.pr_id_input.text().strip()

        # 验证输入
        if not owner:
            QMessageBox.warning(self, "警告", "请输入用户名/组织名")
            return
        
        if not repo or repo == "加载中..." or repo == "无可用仓库":
            QMessageBox.warning(self, "警告", "请选择有效的仓库")
            return
        
        if not pr_id or not pr_id.isdigit():
            QMessageBox.warning(self, "警告", "请输入有效的PR ID")
            return

        # 构建URL
        url = f"https://github.com/{owner}/{repo}/pull/{pr_id}"

        # 检查是否已存在
        for pr in self.pr_list:
            if pr['url'] == url:
                QMessageBox.warning(self, "警告", "该PR已在监控列表中")
                return

        try:
            # 立即获取一次状态信息（包括标题和作者）
            status = self.monitor.get_pr_status(owner, repo, pr_id)
            
            # 添加到列表
            pr_info = {
                'owner': owner,
                'repo': repo,
                'pull_number': pr_id,
                'url': url,
                'status': status  # 包含标题和作者的状态信息
            }
            self.pr_list.append(pr_info)

            # 更新表格
            self.update_pr_table()

            # 清空输入框
            self.pr_id_input.clear()

            # 更新状态
            self.update_status(f"已添加PR | 总数: {len(self.pr_list)}", "success")

            # 保存配置
            self.save_config()
            
        except GitHubAPIError as e:
            # 如果获取状态失败，仍然添加PR，只是没有状态信息
            pr_info = {
                'owner': owner,
                'repo': repo,
                'pull_number': pr_id,
                'url': url,
                'status': None
            }
            self.pr_list.append(pr_info)
            
            # 更新表格
            self.update_pr_table()
            
            # 清空输入框
            self.pr_id_input.clear()
            
            # 更新状态
            self.update_status(f"已添加PR | 总数: {len(self.pr_list)} | 警告: 无法获取状态信息 ({str(e)})")
            
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
            # 用户/组织
            owner_item = QTableWidgetItem(pr['owner'])
            self.pr_table.setItem(row, 0, owner_item)

            # 仓库
            repo_item = QTableWidgetItem(pr['repo'])
            self.pr_table.setItem(row, 1, repo_item)

            # PR ID (可点击)
            pr_id_item = QTableWidgetItem(pr['pull_number'])
            pr_id_item.setForeground(QColor(100, 180, 255))  # 浅蓝色，表示可点击
            pr_id_item.setFont(QFont('Arial', 10, QFont.Bold))  # 加粗
            self.pr_table.setItem(row, 2, pr_id_item)

            # 如果有状态信息，显示详细信息
            if pr.get('status'):
                status = pr['status']

                # 标题
                title_item = QTableWidgetItem(status.get('title', 'N/A'))
                self.pr_table.setItem(row, 3, title_item)
                
                # 作者
                author_item = QTableWidgetItem(status.get('author', 'N/A'))
                self.pr_table.setItem(row, 4, author_item)

                # PR状态
                state = status.get('state', 'unknown')
                merged = status.get('merged', False)
                if merged:
                    state_text = '✓ 已合并'
                    state_color = QColor(0, 200, 0)  # 更亮的绿色
                elif state == 'open':
                    state_text = '● 开放中'
                    state_color = QColor(100, 180, 255)  # 浅蓝色
                elif state == 'closed':
                    state_text = '✗ 已关闭'
                    state_color = QColor(255, 100, 100)  # 更亮的红色
                else:
                    state_text = state
                    state_color = QColor(180, 180, 180)  # 更亮的灰色

                state_item = QTableWidgetItem(state_text)
                state_item.setForeground(state_color)
                self.pr_table.setItem(row, 5, state_item)

                # CI状态
                ci_status = status.get('ci_status', 'unknown')
                ci_map = {
                    'success': ('✓ 通过', QColor(0, 200, 0)),  # 更亮的绿色
                    'pending': ('⏳ 进行中', QColor(255, 180, 0)),  # 更亮的橙色
                    'failure': ('✗ 失败', QColor(255, 100, 100)),  # 更亮的红色
                    'error': ('✗ 错误', QColor(255, 100, 100)),  # 更亮的红色
                }
                ci_text, ci_color = ci_map.get(ci_status, (ci_status, QColor(180, 180, 180)))
                ci_item = QTableWidgetItem(ci_text)
                ci_item.setForeground(ci_color)
                self.pr_table.setItem(row, 6, ci_item)

                # 审查状态
                review_status = status.get('review_status', 'unknown')
                review_map = {
                    'approved': ('✓ 已批准', QColor(0, 200, 0)),  # 更亮的绿色
                    'changes_requested': ('✗ 需修改', QColor(255, 100, 100)),  # 更亮的红色
                    'pending': ('⏳ 待审查', QColor(255, 180, 0)),  # 更亮的橙色
                }
                review_text, review_color = review_map.get(review_status, (review_status, QColor(180, 180, 180)))
                review_item = QTableWidgetItem(review_text)
                review_item.setForeground(review_color)
                self.pr_table.setItem(row, 7, review_item)

                # 最后更新
                updated_item = QTableWidgetItem(status.get('updated_at', 'N/A'))
                self.pr_table.setItem(row, 8, updated_item)
            else:
                # 没有状态信息，显示占位符
                for col in range(3, 9):
                    if col == 3:
                        placeholder_item = QTableWidgetItem('')  # 标题默认为空
                    else:
                        placeholder_item = QTableWidgetItem('-')
                    placeholder_item.setForeground(QColor(180, 180, 180))  # 更亮的灰色
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
        self.interval_combo.setEnabled(False)
        self.add_pr_button.setEnabled(False)
        self.remove_pr_button.setEnabled(False)

        # 更新状态
        self.update_status(f"正在监控中... | PR数量: {len(self.pr_list)}", "info")

        # 立即获取一次数据
        self.fetch_and_display()

        # 启动定时器
        interval = self.get_interval_seconds() * 1000  # 转换为毫秒
        self.timer.start(interval)

        # 启动倒计时
        self.remaining_seconds = self.get_interval_seconds()
        self.countdown_timer.start(1000)  # 每秒更新一次
        self.update_countdown()

    def stop_monitoring(self):
        """停止监控"""
        self.monitoring = False
        self.timer.stop()
        self.countdown_timer.stop()

        # 更新按钮状态
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.interval_combo.setEnabled(True)
        self.add_pr_button.setEnabled(True)
        self.remove_pr_button.setEnabled(True)

        # 保存配置（包含最新的PR状态信息）
        self.save_config()

        # 更新状态（显示最后刷新时间）
        if self.last_refresh_time:
            self.update_status(f"已停止监控 | PR数量: {len(self.pr_list)} | 上次刷新: {self.last_refresh_time}", "warning")
        else:
            self.update_status(f"已停止监控 | PR数量: {len(self.pr_list)}", "warning")
        self.countdown_label.setText("下次刷新: --")
        self.countdown_label.setStyleSheet("color: gray; font-size: 9pt;")

    def fetch_and_display(self):
        """获取并显示所有PR信息"""
        if not self.monitoring or not self.pr_list:
            return

        # 如果上一个线程还在运行，不启动新线程
        if self.fetch_thread and self.fetch_thread.isRunning():
            return

        # 重置倒计时
        self.remaining_seconds = self.get_interval_seconds()

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

        # 保存最后刷新时间（完整的日期时间）
        self.last_refresh_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        # 保存配置（持久化刷新时间）
        self.save_config()

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

            # 加载用户名/组织名列表
            owner_list = config.get('owner_list', [])
            if owner_list:
                self.owner_combo.clear()
                self.owner_combo.addItems(owner_list)
            else:
                # 如果没有保存的列表，至少保留默认值
                if self.owner_combo.count() == 0:
                    self.owner_combo.addItem("vllm-project")

            # 加载PR列表（兼容多种格式）
            pr_list_data = config.get('pr_list', [])
            for item in pr_list_data:
                if isinstance(item, str):
                    # 旧格式：URL字符串
                    pr_info = self.monitor.parse_pr_url(item)
                    if pr_info:
                        pr_info['url'] = item
                        pr_info['status'] = None
                        self.pr_list.append(pr_info)
                elif isinstance(item, dict):
                    # 新格式：对象
                    if 'url' in item and 'owner' in item and 'repo' in item and 'pull_number' in item:
                        pr_info = {
                            'url': item['url'],
                            'owner': item['owner'],
                            'repo': item['repo'],
                            'pull_number': item['pull_number'],
                            'status': None
                        }

                        # 如果有缓存的状态信息，恢复它
                        if 'cached_status' in item:
                                cached = item['cached_status']
                                pr_info['status'] = {
                                    'title': cached.get('title', ''),
                                    'author': cached.get('author', ''),  # 加载保存的作者信息
                                    'state': cached.get('state', ''),
                                    'merged': cached.get('merged', False),
                                    'ci_status': cached.get('ci_status', 'unknown'),
                                    'review_status': cached.get('review_status', 'unknown'),
                                    'updated_at': cached.get('updated_at', ''),
                                    'created_at': '',  # 创建时间不缓存
                                    'url': item['url']
                                }

                        self.pr_list.append(pr_info)
                    else:
                        # 如果只有url，尝试解析
                        url = item.get('url', '')
                        if url:
                            pr_info = self.monitor.parse_pr_url(url)
                            if pr_info:
                                pr_info['url'] = url
                                pr_info['status'] = None
                                self.pr_list.append(pr_info)

            # 加载刷新间隔
            interval = config.get('interval', 30)
            # 根据秒数找到对应的选项文本
            interval_text = '30秒'  # 默认值
            for text, seconds in self.interval_options.items():
                if seconds == interval:
                    interval_text = text
                    break
            self.interval_combo.setCurrentText(interval_text)

            # 加载最后刷新时间
            self.last_refresh_time = config.get('last_refresh_time', None)

            # 更新表格
            self.update_pr_table()

            # 初始化仓库列表
            if self.owner_combo.count() > 0:
                self.load_repos(self.owner_combo.currentText())

            # 更新状态（显示最后刷新时间）
            if self.pr_list:
                if self.last_refresh_time:
                    self.update_status(f"已加载配置 | PR数量: {len(self.pr_list)} | 上次刷新: {self.last_refresh_time}", "success")
                else:
                    self.update_status(f"已加载配置 | PR数量: {len(self.pr_list)}", "success")

        except Exception as e:
            print(f"加载配置失败: {e}")

    def save_config(self):
        """保存配置（包含PR的完整信息）"""
        try:
            # 获取所有用户名/组织名
            owner_list = []
            for i in range(self.owner_combo.count()):
                owner_list.append(self.owner_combo.itemText(i))

            # 保存PR的完整信息（包括标题等状态信息）
            pr_list_to_save = []
            for pr in self.pr_list:
                pr_data = {
                    'url': pr['url'],
                    'owner': pr['owner'],
                    'repo': pr['repo'],
                    'pull_number': pr['pull_number']
                }
                # 如果有状态信息，保存关键字段（包括作者）
                if pr.get('status'):
                    status = pr['status']
                    pr_data['cached_status'] = {
                        'title': status.get('title', ''),
                        'author': status.get('author', ''),  # 保存作者信息
                        'state': status.get('state', ''),
                        'merged': status.get('merged', False),
                        'ci_status': status.get('ci_status', 'unknown'),
                        'review_status': status.get('review_status', 'unknown'),
                        'updated_at': status.get('updated_at', '')
                    }
                pr_list_to_save.append(pr_data)

            config = {
                'token': self.token_input.text().strip(),
                'pr_list': pr_list_to_save,
                'interval': self.get_interval_seconds(),
                'owner_list': owner_list,
                'last_refresh_time': self.last_refresh_time
            }

            with open(self.CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2, ensure_ascii=False)

        except Exception as e:
            print(f"保存配置失败: {e}")

    def center(self):
        """将窗口居中显示在屏幕上"""
        # 获取屏幕几何信息
        screen_geometry = QApplication.desktop().screenGeometry()
        
        # 获取窗口几何信息
        window_geometry = self.frameGeometry()
        
        # 计算窗口中心点
        center_point = screen_geometry.center()
        
        # 将窗口中心点设置为屏幕中心点
        window_geometry.moveCenter(center_point)
        
        # 将窗口移动到计算好的位置
        self.move(window_geometry.topLeft())
    
    def on_cell_clicked(self, row, column):
        """处理单元格点击事件"""
        # 如果点击的是PR ID列（第2列），打开PR链接
        if column == 2 and row < len(self.pr_list):
            pr_url = self.pr_list[row]['url']
            QDesktopServices.openUrl(QUrl(pr_url))

    def show_context_menu(self, pos):
        """显示右键菜单"""
        from PyQt5.QtWidgets import QMenu, QAction

        # 获取当前选中的单元格
        selected_items = self.pr_table.selectedItems()
        if not selected_items:
            return

        # 创建菜单
        menu = QMenu(self)

        # 添加复制动作
        copy_action = QAction("复制", self)
        copy_action.triggered.connect(self.copy_selected_text)
        menu.addAction(copy_action)

        # 显示菜单
        menu.exec_(self.pr_table.viewport().mapToGlobal(pos))
    
    def copy_selected_text(self):
        """复制选中的文本到剪贴板"""
        selected_items = self.pr_table.selectedItems()
        if selected_items:
            # 将选中的文本复制到剪贴板
            clipboard = QApplication.clipboard()
            clipboard.setText(selected_items[0].text())
    
    def update_countdown(self):
        """更新倒计时显示"""
        if not self.monitoring:
            return

        self.remaining_seconds -= 1

        if self.remaining_seconds < 0:
            self.remaining_seconds = 0

        # 格式化显示
        minutes = self.remaining_seconds // 60
        seconds = self.remaining_seconds % 60

        if minutes > 0:
            countdown_text = f"下次刷新: {minutes}分{seconds}秒"
        else:
            countdown_text = f"下次刷新: {seconds}秒"

        # 根据剩余时间改变颜色
        if self.remaining_seconds <= 5:
            color = "red"
        elif self.remaining_seconds <= 10:
            color = "orange"
        else:
            color = "green"

        self.countdown_label.setText(countdown_text)
        self.countdown_label.setStyleSheet(f"color: {color}; font-size: 10pt; font-weight: bold;")

    def closeEvent(self, event):
        """窗口关闭事件 - 保存配置"""
        # 如果正在监控，先停止
        if self.monitoring:
            self.stop_monitoring()
        else:
            # 如果没有监控，也保存配置
            self.save_config()

        event.accept()

    def update_status(self, message, status_type=""):
        """更新状态标签"""
        self.status_label.setText(message)

        if status_type == "success":
            self.status_label.setStyleSheet("color: rgb(0, 200, 0);")  # 更亮的绿色
        elif status_type == "error":
            self.status_label.setStyleSheet("color: rgb(255, 100, 100);")  # 更亮的红色
        elif status_type == "warning":
            self.status_label.setStyleSheet("color: rgb(255, 180, 0);")  # 更亮的橙色
        elif status_type == "info":
            self.status_label.setStyleSheet("color: rgb(100, 180, 255);")  # 浅蓝色
        else:
            self.status_label.setStyleSheet("color: rgb(180, 180, 180);")  # 更亮的灰色


def main():
    """主函数"""
    # 修复macOS上的IMK错误（error messaging the mach port for IMKCFRunLoopWakeUpReliable）
    # 注意：这个错误在按Alt/Option键时会触发，不影响功能，只是系统层面的警告
    # 完全隐藏需要在启动时重定向stderr: python main.py 2>&1 | grep -v IMK

    # 设置环境变量，尝试减少IMK错误发生频率
    os.environ['QT_MAC_WANTS_LAYER'] = '1'
    os.environ['QT_IM_MODULE'] = ''

    app = QApplication(sys.argv)

    # 禁用输入法，减少与macOS输入法管理器的交互
    try:
        app.inputMethod().reset()
    except:
        pass

    window = PRMonitorGUI()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()