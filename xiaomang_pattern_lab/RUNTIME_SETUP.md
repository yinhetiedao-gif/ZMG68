# Pattern Lab 一键运行环境

用户只需运行：

```powershell
.\start_pattern_lab.ps1
```

脚本会自动定位项目专用运行时或本机完整 Python，验证 Tcl/Tk，创建/检查 `.venv`，安装 `requirements.txt`，执行关键导入测试，再启动 `xiaomang_pattern_lab.main`。

出现启动问题时运行：

```powershell
.\diagnose_pattern_lab.ps1
```

它会显示项目根目录、发现的 Python、Tk 检查、`.venv`、依赖、入口、测试素材和最后一次启动错误；错误副本保存在 `work\diagnostics\last-launch-error.txt`。

这个流程不会修改系统 PATH、不会注册全局 Python，也不会启动或修改旧版“小芒造物”。只有在源码启动和回归验证通过后，才允许使用 `build_pattern_lab.ps1` 构建 `XiaomangPatternLab.exe`。
