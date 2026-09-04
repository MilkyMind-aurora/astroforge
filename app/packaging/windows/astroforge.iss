; AstroForge Windows 安装包脚本（Phase 8 打包，Inno Setup 6）
; 前置：先在 app/ 执行 flutter build windows --release
; 产物：app/build/windows/x64/runner/Release/
; 用法：iscc app\packaging\windows\astroforge.iss

#define MyAppName "AstroForge"
#define MyAppVersion "0.1.0"
#define MyAppPublisher "MilkyMind-aurora"
#define MyAppExeName "astroforge.exe"
#define ReleaseDir "..\..\build\windows\x64\runner\Release"

[Setup]
AppId={{7C3A1E9F-5B2D-4F8A-9C4E-ASTROFORGE01}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\AstroForge
DefaultGroupName={#MyAppName}
OutputDir=dist
OutputBaseFilename=AstroForgeSetup_{#MyAppVersion}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayIcon={app}\{#MyAppExeName}

[Languages]
Name: "chinesesimplified"; MessagesFile: "compiler:Languages\ChineseSimplified.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
Source: "{#ReleaseDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#MyAppName}}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; 清理运行时残留（token/日志/缓存），保留用户数据目录由用户自行处置
Type: filesandordirs; Name: "{app}\data"
