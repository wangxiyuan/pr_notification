# GitHub PR 监控器

一个跨平台的GitHub Pull Request状态监控工具，支持Mac和Windows系统。

## 功能特性

- ✅ 跨平台支持（Mac / Windows）
- ✅ 图形化界面，操作简单
- ✅ 实时监控PR状态变化
- ✅ 显示详细的PR信息：
  - PR标题、作者、链接
  - PR状态（开放/关闭/已合并）
  - CI/CD检查状态
  - 代码审查状态
  - 可合并状态
  - 创建和更新时间
- ✅ 可配置的刷新间隔（10-300秒）
- ✅ 支持公开仓库的PR（无需GitHub Token）

## 技术栈

- **Python 3.7+** - 编程语言
- **PyQt5** - 现代化GUI框架
- **requests** - HTTP请求库
- **GitHub REST API v3** - 数据来源

## 系统要求

- Python 3.7 或更高版本
- 网络连接

## 安装步骤

### 1. 克隆或下载项目

```bash
cd github_app
```

### 2. 创建虚拟环境（推荐）

```bash
python3 -m venv venv
source venv/bin/activate  # Mac/Linux
# 或者在Windows上: venv\Scripts\activate
```

### 3. 安装依赖

```bash
pip install -r requirements.txt
```

或者直接安装：

```bash
pip install requests PyQt5
```

## 使用方法

### 启动程序

如果使用虚拟环境：

```bash
source venv/bin/activate  # Mac/Linux
# 或者在Windows上: venv\Scripts\activate
python main.py
```

如果全局安装了依赖：

```bash
python main.py
```
```

### 使用步骤

1. **输入PR链接**
   - 在"PR链接"输入框中输入GitHub PR的完整URL
   - 格式示例：`https://github.com/microsoft/vscode/pull/12345`

2. **配置刷新间隔**
   - 在"刷新间隔"输入框中设置自动刷新的时间间隔（秒）
   - 建议设置30秒以上，避免触发GitHub API速率限制

3. **开始监控**
   - 点击"开始监控"按钮
   - 程序会立即获取PR信息并显示
   - 之后会按照设置的间隔自动刷新

4. **查看PR信息**
   - PR的详细信息会显示在下方的信息区域
   - 包括状态、CI检查、代码审查等信息
   - 不同状态用不同颜色标识（绿色=成功，红色=失败，橙色=进行中）

5. **停止监控**
   - 点击"停止监控"按钮停止自动刷新
   - 可以修改PR链接或刷新间隔后重新开始

6. **其他操作**
   - **立即刷新**：手动触发一次刷新
   - **清空显示**：清空信息显示区域

## 界面说明

```
┌─────────────────────────────────────────────┐
│  GitHub PR 监控器                            │
├─────────────────────────────────────────────┤
│  配置                                        │
│  PR链接: [___________________________] [开始]│
│  刷新间隔: [30] 秒                    [停止] │
├─────────────────────────────────────────────┤
│  监控状态                                    │
│  ● 监控中 - 最后更新: 14:30:25              │
├─────────────────────────────────────────────┤
│  PR 信息                                     │
│  ┌───────────────────────────────────────┐  │
│  │ 标题: Add new feature                 │  │
│  │ 状态: ● 开放中                        │  │
│  │ CI 状态: ✓ 通过                       │  │
│  │ 审查状态: ✓ 已批准                    │  │
│  │ 可合并: ✓ 是                          │  │
│  └───────────────────────────────────────┘  │
│  [清空显示] [立即刷新]                       │
└─────────────────────────────────────────────┘
```

## 注意事项

### API速率限制

- GitHub API对未认证的请求有速率限制：**60次/小时**
- 建议刷新间隔设置为30秒或更长
- 如果触发速率限制，程序会显示错误提示

### 支持的PR类型

- 当前版本仅支持**公开仓库**的PR
- 私有仓库的PR需要GitHub Token（未来版本可能支持）

### 网络要求

- 需要能够访问 `api.github.com`
- 如果网络连接失败，程序会显示错误信息

## 故障排除

### 问题：无法启动程序

**解决方案：**
- 确认Python版本是否为3.7或更高：`python --version`
- 确认已安装依赖：`pip install requests PyQt5`
- 如果遇到PyQt5安装问题，可以尝试：`pip install PyQt5 --upgrade`

### 问题：Tkinter导入错误（Python 3.13）

**解决方案：**
- 本程序已使用PyQt5替代Tkinter，避免了Python 3.13的兼容性问题
- 如果仍有问题，请确保已安装PyQt5：`pip install PyQt5`

### 问题：显示"API速率限制已达上限"

**解决方案：**
- 等待一小时后重试
- 增加刷新间隔时间
- 考虑使用GitHub Token（需要修改代码）

### 问题：显示"PR不存在或仓库不可访问"

**解决方案：**
- 检查PR链接是否正确
- 确认PR是否为公开仓库
- 确认PR编号是否存在

### 问题：界面显示异常

**解决方案：**
- 尝试调整窗口大小
- 重启程序
- 检查系统是否支持Tkinter

## 技术栈

- **Python 3.7+** - 编程语言
- **Tkinter** - GUI框架（Python内置）
- **requests** - HTTP请求库
- **GitHub REST API v3** - 数据来源

## 项目结构

```
github_app/
├── main.py              # 主程序和GUI实现
├── github_api.py        # GitHub API封装
├── requirements.txt     # 依赖列表
└── README.md           # 使用说明（本文件）
```

## 示例PR链接

可以使用以下公开PR进行测试：

- `https://github.com/microsoft/vscode/pull/200000`
- `https://github.com/python/cpython/pull/100000`
- `https://github.com/facebook/react/pull/25000`

（注意：这些PR编号可能不存在，请使用实际存在的PR链接）

## 许可证

本项目仅供学习和个人使用。

## 反馈与贡献

如有问题或建议，欢迎反馈。

---

**祝使用愉快！** 🚀
