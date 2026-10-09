#ifndef StarVersion
  #define StarVersion "0.7.0"
#endif
#define STARName "STAR Intelligence"
#define STARExe "STAR.exe"
[Setup]
AppId={{E2B5518B-30A1-409D-AF44-6F773BF05C97}
AppName={#STARName}
AppVerName={#STARName} {#StarVersion}
AppVersion={#StarVersion}
AppPublisher=STAR Intelligence
AppPublisherURL=https://github.com/oncoursemail/Star-AI
AppSupportURL=https://github.com/oncoursemail/Star-AI/issues
AppUpdatesURL=https://github.com/oncoursemail/Star-AI/releases
DefaultDirName={localappdata}\Programs\STAR
DefaultGroupName=STAR Intelligence
UninstallDisplayIcon={app}\{#STARExe}
OutputDir=..\dist
OutputBaseFilename=STAR-Setup-v{#StarVersion}
SetupIconFile=..\assets\star.ico
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
DisableProgramGroupPage=yes
UsePreviousAppDir=yes
CloseApplications=yes
RestartApplications=no
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
DisableWelcomePage=no

; Replace the old *application runtime* tree to avoid stale DLL/Python module files.
; NEVER delete {userappdata}\STAR (chats, models, memory) or arbitrary {app} files.
[InstallDelete]
Type: filesandordirs; Name: "{app}\_internal"

[Files]
Source: "..\dist\STAR\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\STAR Intelligence"; Filename: "{app}\{#STARExe}"
Name: "{autodesktop}\STAR Intelligence"; Filename: "{app}\{#STARExe}"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Shortcuts:"; Flags: unchecked

[Run]
Filename: "{app}\{#STARExe}"; Description: "Launch STAR Intelligence"; Flags: nowait postinstall skipifsilent
Filename: "{app}\{#STARExe}"; Flags: nowait skipifnotsilent
