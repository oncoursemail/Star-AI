#ifndef StarVersion
  #define StarVersion "1.0.0"
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
; Multi-threaded LZMA2 (CI runners have 4 cores): same files, ~2-3x faster compile, slightly larger Setup.
LZMAUseSeparateProcess=yes
LZMANumBlockThreads=4
WizardStyle=modern
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
; Manual Setup preserves an existing install's scope; the in-app updater passes
; /CURRENTUSER or /ALLUSERS when it can identify the running copy's registration.
UsePreviousPrivileges=yes
DisableProgramGroupPage=yes
UsePreviousAppDir=yes
CloseApplications=yes
RestartApplications=no
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
DisableWelcomePage=no

; The old *application runtime* ({app}\_internal and STAR.exe) is replaced as a whole, so no stale DLL or
; Python module survives an upgrade: [Code] below moves it aside first and restores it if Setup fails.
; NEVER delete {userappdata}\STAR (chats, models, memory) or arbitrary {app} files.

[Files]
Source: "..\dist\STAR\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\STAR Intelligence"; Filename: "{app}\{#STARExe}"
Name: "{autodesktop}\STAR Intelligence"; Filename: "{app}\{#STARExe}"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Shortcuts:"; Flags: unchecked

[Run]
Filename: "{app}\{#STARExe}"; Description: "Launch STAR Intelligence"; Flags: nowait postinstall skipifsilent runasoriginaluser
Filename: "{app}\{#STARExe}"; Flags: nowait skipifnotsilent runasoriginaluser

; Issue 120: never leave a half-replaced STAR. Setup's own rollback does not undo [InstallDelete], so the
; old runtime ({app}\_internal and {app}\STAR.exe) is moved aside before the new files are copied, put back
; if the installation does not finish, and deleted only after it has finished. Leftovers from a Setup that
; was killed are removed by the next Setup or by the uninstaller.
[UninstallDelete]
Type: filesandordirs; Name: "{app}\_internal.star-previous"
Type: files; Name: "{app}\{#STARExe}.star-previous"

[Code]
const
  RuntimeDir = '_internal';
  KeptSuffix = '.star-previous';

var
  AppFolder: String;
  RuntimeMoved: Boolean;
  ExeMoved: Boolean;
  InstallFinished: Boolean;

function KeptPath(const Name: String): String;
begin
  Result := AppFolder + '\' + Name + KeptSuffix;
end;

{ Removes the copy kept by an earlier Setup that never finished. }
procedure RemoveLeftover(const Name: String);
var
  Path: String;
begin
  Path := KeptPath(Name);
  if DirExists(Path) then
    DelTree(Path, True, True, True)
  else if FileExists(Path) then
    DeleteFile(Path);
end;

{ Fails while STAR (or anything else) still has a file of the runtime open: nothing is deleted then.
  Tried for a few seconds, so a STAR that is still finishing its shutdown or a virus scanner that briefly
  holds a file does not stop the upgrade. }
function MoveAside(const Name: String): Boolean;
var
  Attempt: Integer;
begin
  Result := False;
  for Attempt := 1 to 8 do
  begin
    Result := RenameFile(AppFolder + '\' + Name, KeptPath(Name));
    if Result then
      Exit;
    Sleep(500);
  end;
end;

{ Replaces whatever a failed installation left with the kept old copy. }
procedure PutBack(const Name: String);
var
  Live: String;
begin
  Live := AppFolder + '\' + Name;
  if DirExists(Live) then
    DelTree(Live, True, True, True)
  else if FileExists(Live) then
    DeleteFile(Live);
  if not RenameFile(KeptPath(Name), Live) then
    Log('Could not put back ' + Live + '; the previous copy is kept at ' + KeptPath(Name));
end;

procedure RefuseWhileRunning;
begin
  SuppressibleMsgBox('STAR Intelligence is still running, or one of its files is open in another program, ' +
    'so Setup cannot replace it.' + #13#10 + #13#10 +
    'Nothing was changed: the installed STAR, your chats and your settings are as they were. ' +
    'Close every STAR window (also one started with "Run as administrator") and run Setup again.',
    mbError, MB_OK, IDOK);
  Abort;
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssInstall then
  begin
    { Restart Manager has already been asked to close STAR (CloseApplications=yes). }
    AppFolder := ExpandConstant('{app}');
    RemoveLeftover(RuntimeDir);
    RemoveLeftover('{#STARExe}');
    if DirExists(AppFolder + '\' + RuntimeDir) then
    begin
      if not MoveAside(RuntimeDir) then
        RefuseWhileRunning;
      RuntimeMoved := True;
    end;
    if FileExists(AppFolder + '\{#STARExe}') then
    begin
      if not MoveAside('{#STARExe}') then
      begin
        if RuntimeMoved then
          PutBack(RuntimeDir);
        RuntimeMoved := False;
        RefuseWhileRunning;
      end;
      ExeMoved := True;
    end;
  end
  else if CurStep = ssPostInstall then
  begin
    InstallFinished := True;
    if RuntimeMoved then
      DelTree(KeptPath(RuntimeDir), True, True, True);
    if ExeMoved then
      DeleteFile(KeptPath('{#STARExe}'));
  end;
end;

{ Runs when Setup ends for any reason, after its own rollback of the files it copied. }
procedure DeinitializeSetup;
begin
  if InstallFinished then
    Exit;
  if RuntimeMoved then
    PutBack(RuntimeDir);
  if ExeMoved then
    PutBack('{#STARExe}');
end;
