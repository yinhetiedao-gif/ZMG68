; 使用 Inno Setup 6 编译。本脚本由 build-installer.ps1 调用。
#define AppName "小芒造物"
#define AppVersion "1.6.14"
#define AppExeName "小芒造物.exe"
[Setup]
AppId={{567B90B1-07C2-4F1F-8E90-0E0C3AE32D5A}
AppName={#AppName}
AppVersion={#AppVersion}
; 默认仅安装给当前用户，不需要管理员权限，也不会写入 Program Files。
PrivilegesRequired=lowest
; 默认强制当前用户安装；避免管理员上下文意外切换为所有用户模式。
PrivilegesRequiredOverridesAllowed=commandline
DefaultDirName={localappdata}\Programs\{#AppName}
DefaultGroupName={#AppName}
OutputDir=installer-output
OutputBaseFilename=小芒造物-安装程序-{#AppVersion}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
UninstallDisplayName={#AppName}
[Languages]
Name: "chinesesimp"; MessagesFile: "ChineseSimplified.isl"
[Files]
Source: "dist\小芒造物\{#AppExeName}"; DestDir: "{app}"; Flags: ignoreversion
[Tasks]
Name: "startmenu"; Description: "创建开始菜单快捷方式"
Name: "desktopicon"; Description: "创建桌面快捷方式"
[Icons]
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExeName}"; Tasks: desktopicon
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExeName}"; Tasks: startmenu
[Run]
Filename: "{app}\{#AppExeName}"; Description: "打开小芒造物"; Flags: nowait postinstall skipifsilent

[Code]
function TargetApplicationRunning(): Boolean;
var
  ResultCode: Integer;
  TargetPath: String;
  PowerShellParams: String;
begin
  { 只检查即将被覆盖的当前用户安装位置；旧版、开发版和测试副本不能阻止升级。 }
  TargetPath := ExpandConstant('{app}\{#AppExeName}');
  PowerShellParams := '-NoProfile -NonInteractive -Command "$target = ''' + TargetPath + '''; '
    + '$matches = @(Get-CimInstance Win32_Process | Where-Object { $_.Name -eq ''{#AppExeName}'' '
    + '-and $_.ExecutablePath -and $_.ExecutablePath -ieq $target }); '
    + 'if ($matches.Count -gt 0) { exit 0 } else { exit 1 }"';
  Result := Exec(ExpandConstant('{sys}\WindowsPowerShell\v1.0\powershell.exe'), PowerShellParams,
    '', SW_HIDE, ewWaitUntilTerminated, ResultCode) and (ResultCode = 0);
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
begin
  { 此事件发生在用户已经选择安装目录之后；安装目录常量此时才有效。 }
  Result := '';
  { 不强制关闭用户正在编辑的项目；仅在目标安装程序仍运行时才阻止升级。 }
  if TargetApplicationRunning() then begin
    Result := '检测到当前安装的“小芒造物”仍在后台运行。请保存项目、完全退出该版本后，再重新运行安装程序。其他旧版或测试副本不会阻止安装。';
  end;
end;
