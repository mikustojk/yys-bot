# YYS Bot Launcher

一个用于启动阴阳师脚本的 Windows 桌面启动器。当前启动器包含两个主要功能：

- `困难28`：自动刷取困28。（注：主要用于刷绘卷，自动清结界票功能开发中）
- `刷挑战`：所有通过点击 “挑战” 按钮开始战斗的副本均可刷取

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

如果提示“因为在此系统上禁止运行脚本”，先在当前 PowerShell 窗口运行：

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

然后再运行：

```powershell
.\setup_env.ps1
```

这个设置只对当前 PowerShell 窗口生效，不会永久修改系统策略。

看到 `Environment ready` 后，直接打开目录中的：

```powershell
.\script.exe
```

启动器会自动优先使用项目里的 `.venv` 虚拟环境。

### 重新生成启动器

修改 `script_launcher.cs` 后运行：

```powershell
.\build_exe.ps1
```

生成结果是 `script.exe`。

### 自适应模板截图

自适应脚本使用 `images/templates` 里的模板。需要重新截图时，把模拟器停在对应界面，然后运行：

```powershell
.\.venv\Scripts\python.exe .\capture_template.py 模板名
```

常用模板名：

- 挑战脚本：`challenge`、`settlement`
- K28 脚本：`k28_stage`、`k28_explore`、`k28_battle`、`k28_boss`、`k28_paper`、`k28_treasure`、`k28_team_prompt`、`k28_team_confirm`

截图工具会把模板保存到 `images/templates`。

# 免责声明
本脚本**无法保证绝对的安全与稳定**，使用本脚本导致封号**概不负责**。