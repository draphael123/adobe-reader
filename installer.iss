; PDF Screenshot Tool - Inno Setup Script
; Creates a professional Windows installer

#define MyAppName "PDF Screenshot Tool"
#define MyAppVersion "2.0.0"
#define MyAppPublisher "PDF Screenshot Tool"
#define MyAppURL "https://pdfscreenshottool.com"
#define MyAppExeName "PDFScreenshotTool.exe"

[Setup]
; Basic app info
AppId={{A1B2C3D4-E5F6-7890-ABCD-EF1234567890}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}

; Installation settings
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
AllowNoIcons=yes
DisableProgramGroupPage=yes

; Output settings
OutputDir=installer_output
OutputBaseFilename=PDFScreenshotTool_Setup
SetupIconFile=assets\icon.ico
UninstallDisplayIcon={app}\{#MyAppExeName}

; Compression
Compression=lzma2/ultra64
SolidCompression=yes
LZMAUseSeparateProcess=yes

; Visual settings - Modern wizard with custom images
WizardStyle=modern
WizardSizePercent=120
WizardImageFile=assets\wizard_image.bmp
WizardSmallImageFile=assets\wizard_small_image.bmp
WizardImageStretch=yes

; Privileges (no admin required - installs to user folder)
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog

; Version info
VersionInfoVersion={#MyAppVersion}
VersionInfoCompany={#MyAppPublisher}
VersionInfoDescription={#MyAppName} Setup
VersionInfoCopyright=Copyright (C) 2026 {#MyAppPublisher}
VersionInfoProductName={#MyAppName}
VersionInfoProductVersion={#MyAppVersion}

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Messages]
WelcomeLabel1=Welcome to PDF Screenshot Tool
WelcomeLabel2=The ultimate tool for capturing PDF pages in Adobe Acrobat.%n%n✓  Automatic capture as you navigate pages%n✓  Smart duplicate detection%n✓  Customizable hotkeys%n✓  Advanced image processing%n%nVersion {#MyAppVersion}%n%nClick Next to continue.
FinishedLabel=Setup has successfully installed [name] on your computer.%n%nThe application will run in your system tray (look for the camera icon near your clock).%n%nRight-click the tray icon to access settings and controls.
FinishedHeadingLabel=Installation Complete!

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Additional Options:"; Flags: checkedonce
Name: "startupicon"; Description: "&Start automatically with Windows (recommended)"; GroupDescription: "Additional Options:"; Flags: checkedonce

[Files]
Source: "dist\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion
Source: "assets\icon.ico"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\icon.ico"
Name: "{group}\Uninstall {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\icon.ico"; Tasks: desktopicon

[Registry]
; Add to Windows startup if selected
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "PDFScreenshotTool"; ValueData: """{app}\{#MyAppExeName}"""; Flags: uninsdeletevalue; Tasks: startupicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch {#MyAppName} now"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{app}"

[Code]
// Modern color scheme
const
  COLOR_BACKGROUND = $00FFFFFF;     // White background
  COLOR_PRIMARY = $00F97316;        // Orange accent
  COLOR_DARK = $001A1A2E;           // Dark text
  COLOR_SECONDARY = $00666666;      // Gray text
  COLOR_ACCENT = $004F46E5;         // Purple accent
  COLOR_SUCCESS = $0022C55E;        // Green
  
procedure InitializeWizard;
begin
  // Main wizard styling
  WizardForm.Color := COLOR_BACKGROUND;
  
  // Welcome page styling
  WizardForm.WelcomeLabel1.Font.Name := 'Segoe UI';
  WizardForm.WelcomeLabel1.Font.Size := 18;
  WizardForm.WelcomeLabel1.Font.Style := [fsBold];
  WizardForm.WelcomeLabel1.Font.Color := COLOR_DARK;
  
  WizardForm.WelcomeLabel2.Font.Name := 'Segoe UI';
  WizardForm.WelcomeLabel2.Font.Size := 10;
  WizardForm.WelcomeLabel2.Font.Color := COLOR_SECONDARY;
  
  // Finish page styling
  WizardForm.FinishedLabel.Font.Name := 'Segoe UI';
  WizardForm.FinishedLabel.Font.Size := 10;
  WizardForm.FinishedLabel.Font.Color := COLOR_SECONDARY;
  
  WizardForm.FinishedHeadingLabel.Font.Name := 'Segoe UI';
  WizardForm.FinishedHeadingLabel.Font.Size := 18;
  WizardForm.FinishedHeadingLabel.Font.Style := [fsBold];
  WizardForm.FinishedHeadingLabel.Font.Color := COLOR_SUCCESS;
  
  // Directory page styling
  WizardForm.DirEdit.Font.Name := 'Segoe UI';
  WizardForm.DirEdit.Font.Size := 9;
  
  // Tasks page styling  
  WizardForm.TasksList.Font.Name := 'Segoe UI';
  WizardForm.TasksList.Font.Size := 9;
  WizardForm.TasksList.Color := COLOR_BACKGROUND;
  
  // Style select directory page labels
  WizardForm.SelectDirLabel.Font.Name := 'Segoe UI';
  WizardForm.SelectDirLabel.Font.Size := 9;
  WizardForm.SelectDirLabel.Font.Color := COLOR_SECONDARY;
  
  WizardForm.SelectDirBrowseLabel.Font.Name := 'Segoe UI';
  WizardForm.SelectDirBrowseLabel.Font.Size := 9;
  WizardForm.SelectDirBrowseLabel.Font.Color := COLOR_SECONDARY;
  
  // Style page headers
  WizardForm.PageNameLabel.Font.Name := 'Segoe UI Semibold';
  WizardForm.PageNameLabel.Font.Size := 12;
  WizardForm.PageNameLabel.Font.Color := COLOR_DARK;
  
  WizardForm.PageDescriptionLabel.Font.Name := 'Segoe UI';
  WizardForm.PageDescriptionLabel.Font.Size := 9;
  WizardForm.PageDescriptionLabel.Font.Color := COLOR_SECONDARY;
  
  // Style ready memo
  WizardForm.ReadyMemo.Font.Name := 'Consolas';
  WizardForm.ReadyMemo.Font.Size := 9;
  WizardForm.ReadyMemo.Color := $00F5F5F5;
end;

function InitializeSetup(): Boolean;
begin
  Result := True;
  // The mutex in the app handles single-instance logic
end;

procedure CurPageChanged(CurPageID: Integer);
begin
  // Customize button text based on page
  case CurPageID of
    wpWelcome:
      WizardForm.NextButton.Caption := 'Get Started →';
    wpSelectDir:
      WizardForm.NextButton.Caption := 'Next →';
    wpSelectTasks:
      WizardForm.NextButton.Caption := 'Install →';
    wpFinished:
      WizardForm.NextButton.Caption := 'Finish';
  else
    WizardForm.NextButton.Caption := 'Next →';
  end;
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then
  begin
    // Post-installation tasks
  end;
end;
