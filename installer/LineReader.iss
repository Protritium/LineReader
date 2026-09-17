#define MyAppName "LineReader"
#define MyAppVersion "1.7.0"
#define MyAppExeName "LineReader.exe"

[Setup]
AppId={{62E35C48-10E4-45ED-8B80-423D1D32B42C}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher=Protritium
AppPublisherURL=https://github.com/Protritium
AppSupportURL=https://github.com/Protritium/LineReader/issues
AppUpdatesURL=https://github.com/Protritium/LineReader/releases
DefaultDirName={localappdata}\Programs\LineReader
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
OutputDir=..\output
OutputBaseFilename=LineReader-Setup-{#MyAppVersion}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
UninstallDisplayIcon={app}\{#MyAppExeName}
CloseApplications=yes

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional shortcuts:"; Flags: checkedonce

[Files]
Source: "..\dist\LineReader\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\README.md"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch {#MyAppName}"; Flags: nowait postinstall skipifsilent
