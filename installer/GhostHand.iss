; Inno Setup script for a real .exe installer.
; Install Inno Setup 6 (https://jrsoftware.org/isdl.php), then:
;   iscc installer\GhostHand.iss
; Produces installer\Output\GhostHand-Setup.exe
;
; The PowerShell installer (install.ps1) needs no extra tooling and is the
; recommended path unless you want a single distributable setup file.

#define AppName "Ghost Hand"
#define AppVersion "0.5.0"
#define AppExe "GhostHand.exe"
#define AppPublisher "Local"

[Setup]
AppId={{8E5F1E3A-7C21-4F7B-9F8C-2B6C1D44A901}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
DefaultDirName={localappdata}\Programs\GhostHand
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputBaseFilename=GhostHand-Setup
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
SetupIconFile=..\assets\app.ico
UninstallDisplayIcon={app}\{#AppExe}

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Shortcuts:"

[Files]
Source: "..\dist\GhostHand\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExe}"; Description: "Launch {#AppName}"; Flags: nowait postinstall skipifsilent

[UninstallRun]
Filename: "{cmd}"; Parameters: "/C taskkill /IM {#AppExe} /F"; Flags: runhidden

[UninstallDelete]
Type: filesandordirs; Name: "{app}\config"
Type: filesandordirs; Name: "{app}\debug"
