# logx

本工具为本地离线日志搜索工具，支持：

- `zgrep`：类似 GNU zgrep 的流式搜索（无需索引）
- `grep`：简化版流式搜索
- `gui`：维护人员可用的桌面界面

## 1. 快速开始

```bash
logx zgrep "timeout|retry|exception" ./data/workspace --name "collect*" -n --color=always
logx gui
```

## 2. 安装方式（其他环境）

### 2.1 直接运行（源码）

```bash
# 进入项目目录
python main.py zgrep "timeout" ./data/workspace --name "collect*" -n
python main.py gui
```

### 2.2 安装为本地命令（推荐）

```bash
python -m pip install -e .
logx zgrep "timeout" ./data/workspace --name "collect*" -n
logx gui
```

### 2.3 打包为单文件 exe（无 Python 环境）

```bash
powershell -ExecutionPolicy Bypass -File scripts/build_exe.ps1
```

产物位置：`dist/logx.exe`

使用方式：

```bash
# 命令行
.\dist\logx.exe zgrep "timeout|retry|exception" .\data\workspace --name "collect*" -n --color=always

# GUI
.\dist\logx.exe gui
```

## 3. 常用命令示例

```bash
logx zgrep "timeout" ./data/workspace --name "collect*" --and "ERROR" -n
logx zgrep "timeout" ./data/workspace --name "collect*" --or "失败" --or "ERROR" -n
logx zgrep "timeout" ./data/workspace --name "collect*" -n -C 2
```

## 4. GUI 功能

- 基础搜索 + 高级过滤（可展开）
- 命中关键字高亮 + 级别着色
- 结果导出 CSV/TXT

## 5. 目录结构说明

- `src/function_calling/logx`：核心代码
- `scripts/build_exe.ps1`：打包脚本
- `data/workspace`：本地日志目录（可自行替换）

## 6. 常见问题/故障排查

- **exe 双击闪退**：请在 PowerShell 里运行（双击无法看到错误信息）。
  ```bash
  .\dist\logx.exe gui
  .\dist\logx.exe zgrep "timeout" .\data\workspace --name "collect*"
  ```

- **`pyinstaller` 找不到**：确保用 `python -m PyInstaller`，并先执行打包脚本。
  ```bash
  powershell -ExecutionPolicy Bypass -File scripts/build_exe.ps1
  ```

- **`ModuleNotFoundError: function_calling`**：说明打包时没有加入 `src`。
  请使用当前 `build_exe.ps1`（已包含 `--paths src`）。

- **`zipfile.BadZipFile`**：日志目录里可能有伪装成 `.zip` 的文件。
  已自动跳过无效 zip，如仍报错，请先排查损坏文件。

- **GUI 无高亮**：确保 `Regex/Fixed` 选择正确。
  - 固定字符串：勾选 `Fixed`
  - 正则匹配：勾选 `Regex`
  - 高级高亮设置可在 `Highlight Options` 展开

- **GUI 显示太小/太大**：可在 `gui.py` 调整 `tk scaling` 与字体大小。

- **搜索不到内容**：检查 `Root Path` 与 `File Name Glob` 是否正确，确保日志路径在扫描范围内。
