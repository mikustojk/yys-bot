# YYS Bot Launcher

一个用于启动阴阳师脚本的 Windows 桌面启动器。当前启动器包含两个主要功能：

- `困难28`：运行自适应尺寸版 K28 脚本 `maa_lite_k28.py`
- `刷挑战`：运行自适应尺寸版挑战脚本 `忽略尺寸刷.py`

## 环境要求

- Windows
- MuMu 模拟器，窗口标题默认为 `MuMu安卓设备`
- Python 3.13
- uv
- 项目目录内的 `adb.exe`、`AdbWinApi.dll`、`AdbWinUsbApi.dll`

## 首次使用

在项目目录打开 PowerShell，运行：

```powershell
.\setup_env.ps1
```

看到 `Environment ready` 后，直接打开：

```powershell
.\script.exe
```

启动器会自动优先使用项目里的 `.venv` 虚拟环境。

## 重新生成启动器

修改 `script_launcher.cs` 后运行：

```powershell
.\build_exe.ps1
```

生成结果是 `script.exe`。

## 自适应模板截图

自适应脚本使用 `images/maa` 里的模板。需要重新截图时，把模拟器停在对应界面，然后运行：

```powershell
.\.venv\Scripts\python.exe .\capture_maa_template.py 模板名
```

常用模板名：

- 挑战脚本：`challenge`、`settlement`
- K28 脚本：`k28_stage`、`k28_explore`、`k28_battle`、`k28_boss`、`k28_paper`、`k28_treasure`、`k28_team_prompt`、`k28_team_confirm`

截图工具会把模板保存到 `images/maa`。

## 上传 GitHub 前建议

仓库会忽略 `.venv`、`__pycache__` 和 `MaaAssistantArknights` 参考仓库。上传前建议先检查：

```powershell
git status
```

确认没有把本地虚拟环境、临时截图或无关测试文件加入提交。

