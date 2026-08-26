#ifndef AppVersion
  #define AppVersion "3.3.3"
#endif

[Setup]
AppName=GeForce Presence
AppVersion={#AppVersion}
AppPublisher=KarmaDevz
AppPublisherURL=https://github.com/KarmaDevz
AppUserModelId=KarmaDevz.GeForcePresence
DefaultDirName={userappdata}\GeForceNOWRichPresence
PrivilegesRequired=lowest
DefaultGroupName=GeForce Presence
OutputDir=.
OutputBaseFilename=GeForcePresenceSetupv{#AppVersion}
Compression=lzma
DisableDirPage=no
SolidCompression=yes
WizardStyle=modern
SetupIconFile=_internal\assets\geforce.ico
; activa selector de idioma
ShowLanguageDialog=yes
ArchitecturesAllowed=x64
ArchitecturesInstallIn64BitMode=x64
LicenseFile=LICENSE.txt
AppSupportURL=https://github.com/KarmaDevz/GeForce-NOW-Rich-Presence/issues
AppUpdatesURL=https://github.com/KarmaDevz/GeForce-NOW-Rich-Presence/releases

[Tasks]
Name: "desktopicon"; Description: "Create desktop shortcut"; Flags: unchecked
; Name: "startup"; Description: "Start with Windows"; Flags: unchecked

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"; LicenseFile: "LICENSE.txt"
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"; LicenseFile: "LICENCE_es"
Name: "russian"; MessagesFile: "compiler:Languages\Russian.isl"; LicenseFile: "LICENCE_ru"

[Files]
Source: "GeForceNOWRichPresence.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "_internal\*"; DestDir: "{app}\_internal"; Flags: ignoreversion recursesubdirs createallsubdirs
; copiar también la carpeta locales con en.json, es.json, etc.
Source: "_internal\lang\*"; DestDir: "{app}\lang"; Flags: ignoreversion recursesubdirs createallsubdirs
; copiar archivos de licencia para diferentes idiomas
Source: "LICENSE.txt"; DestDir: "{app}"; Flags: ignoreversion
Source: "LICENCE_es"; DestDir: "{app}"; Flags: ignoreversion
Source: "LICENCE_ru"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
; Acceso directo en menú inicio
Name: "{group}\GeForce Presence"; Filename: "{app}\GeForceNOWRichPresence.exe"; IconFilename: "{app}\_internal\assets\geforce.ico"; AppUserModelID: "KarmaDevz.GeForcePresence"
; Acceso directo en escritorio
Name: "{userdesktop}\GeForce Presence"; Filename: "{app}\GeForceNOWRichPresence.exe"; IconFilename: "{app}\_internal\assets\geforce.ico"; Tasks: desktopicon; AppUserModelID: "KarmaDevz.GeForcePresence"
; (Opcional) arranque con Windows
; Name: "{userstartup}\GeForce Presence"; Filename: "{app}\GeForceNOWRichPresence.exe"; WorkingDir: "{app}"

[Registry]
; Guardar idioma elegido por el usuario en registro
Root: HKCU; Subkey: "Software\GeForcePresence"; ValueType: string; ValueName: "lang"; ValueData: "{language}"; Flags: uninsdeletevalue

[Run]
; Ejecutar al finalizar instalación
Filename: "{app}\GeForceNOWRichPresence.exe"; \
Description: "Start GeForce Presence"; \
Flags: nowait postinstall skipifsilent


[CustomMessages]
english.FinishedSupport=Thanks for using GeForce Presence! Consider supporting this application ^_^
spanish.FinishedSupport=¡Gracias por usar GeForce Presence! Considera apoyar esta aplicación ^_^
russian.FinishedSupport=Спасибо за использование GeForce Presence! Подумайте о поддержке этого приложения ^_^
english.Donate=💖 Donate
spanish.Donate=💖 Donar
russian.Donate=💖 Пожертвовать
english.Star=⭐ Star on GitHub
spanish.Star=⭐ Dar estrella en GitHub
russian.Star=⭐ Звезда на GitHub

[InstallDelete]
Type: filesandordirs; Name: "{app}\_internal"
Type: filesandordirs; Name: "{app}\lang"

[UninstallRun]
Filename: "taskkill.exe"; \
Parameters: "/IM GeForceNOWRichPresence.exe /F"; \
Flags: runhidden skipifdoesntexist

[UninstallDelete]
Type: filesandordirs; Name: "{tmp}\discord_fake_game"
Type: filesandordirs; Name: "{tmp}\discord_quests"
Type: filesandordirs; Name: "{tmp}\geforce_update"
Type: filesandordirs; Name: "{tmp}\geforce_driver"

[Code]

var
  DonateButton: TNewButton;
  StarButton: TNewButton;

procedure OpenURL(URL: String);
var
  ErrorCode: Integer;
begin
  ShellExec('open', URL, '', '', SW_SHOWNORMAL, ewNoWait, ErrorCode);
end;

procedure DonateButtonClick(Sender: TObject);
begin
  OpenURL('https://paypal.me/KarmaDevz');
end;

procedure StarButtonClick(Sender: TObject);
begin
  OpenURL('https://github.com/KarmaDevz/GeForce-NOW-Rich-Presence');
end;

procedure CurPageChanged(CurPageID: Integer);
begin
  if CurPageID = wpFinished then
  begin
    WizardForm.FinishedLabel.Caption := ExpandConstant('{cm:FinishedSupport}');
    { Donate }
    DonateButton := TNewButton.Create(WizardForm);
    DonateButton.Parent := WizardForm.FinishedPage;
    DonateButton.Caption := ExpandConstant('{cm:Donate}');
    DonateButton.Width := 100;
    DonateButton.Height := ScaleY(23);
    DonateButton.Left := WizardForm.FinishedPage.ClientWidth - DonateButton.Width - ScaleX(20);
    DonateButton.Top := WizardForm.FinishedPage.ClientHeight - DonateButton.Height - ScaleY(50);
    DonateButton.OnClick := @DonateButtonClick;

    { GitHub Star }
    StarButton := TNewButton.Create(WizardForm);
    StarButton.Parent := WizardForm.FinishedPage;
    StarButton.Caption := ExpandConstant('{cm:Star}');
    StarButton.Width := 130;
    StarButton.Height := ScaleY(23);
    StarButton.Left := DonateButton.Left - StarButton.Width - ScaleX(10);
    StarButton.Top := DonateButton.Top;
    StarButton.OnClick := @StarButtonClick;
  end;
end;

