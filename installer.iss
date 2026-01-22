; PDF Screenshot Tool - Inno Setup Script
; Creates a professional Windows installer

#define MyAppName "PDF Screenshot Tool"
#define MyAppVersion "2.1.0"
#define MyAppPublisher "Daniel Raphael"
#define MyAppURL "https://pdfscreenshottool.com"
#define MyAppExeName "PDFScreenshotTool.exe"
#define MyAppContact "support@pdfscreenshottool.com"
#define MyAppCopyright "Copyright (C) 2024-2026 Daniel Raphael"

[Setup]
AppId={{A1B2C3D4-E5F6-7890-ABCD-EF1234567890}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL=https://github.com/draphael123/adobe-reader/issues
AppUpdatesURL={#MyAppURL}/download
AppContact={#MyAppContact}
AppCopyright={#MyAppCopyright}
AppComments=Automatically capture PDF pages as you navigate in Adobe Acrobat
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
AllowNoIcons=yes
DisableProgramGroupPage=yes
OutputDir=installer_output
OutputBaseFilename=PDFScreenshotTool_Setup_{#MyAppVersion}
SetupIconFile=assets\icon.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
UninstallDisplayName={#MyAppName}
Compression=lzma2/ultra64
SolidCompression=yes
LZMAUseSeparateProcess=yes
WizardStyle=modern
WizardSizePercent=120
WizardImageFile=assets\wizard_image.bmp
WizardSmallImageFile=assets\wizard_small_image.bmp
WizardImageStretch=yes
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
VersionInfoVersion={#MyAppVersion}
VersionInfoCompany={#MyAppPublisher}
VersionInfoDescription={#MyAppName} - Official Installer
VersionInfoCopyright={#MyAppCopyright}
VersionInfoProductName={#MyAppName}
VersionInfoProductVersion={#MyAppVersion}
VersionInfoTextVersion={#MyAppVersion}
VersionInfoOriginalFileName=PDFScreenshotTool_Setup_{#MyAppVersion}.exe
MinVersion=10.0

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Messages]
WelcomeLabel1=Welcome to PDF Screenshot Tool!
WelcomeLabel2=You're about to install PDF Screenshot Tool - the easiest way to capture PDF pages.%n%n* Screenshots happen while you scroll%n* AI-powered duplicate detection%n* Fixed installation scrolling + funnier setup experience%n* Keyboard shortcuts for power users%n* Lots of customization options%n%nVersion {#MyAppVersion}%n%nClick Next to continue.
FinishedLabel=Installation complete!%n%nWhen you launch the app, you'll see our improved welcome screen with funnier text and working scroll!%n%nLook for the camera icon in your system tray (bottom-right, near the clock).%n%nCan't find it? Click the ^ arrow to expand the tray.%n%nRight-click the icon to access settings.%n%nEnjoy!
FinishedHeadingLabel=Setup Complete!
ConfirmUninstall=We'll miss you dearly. You'll always be in our heart...%n%nAre you sure you want to completely remove %1 and all of its components?
UninstallAppFullTitle=Farewell, Friend
UninstalledAll=%1 was successfully removed from your computer.%n%nThank you for giving us a try. If you ever need to capture PDF pages again, we'll be here waiting. Take care out there!
UninstalledMost=%1 uninstall has completed.%n%nSome elements could not be removed. You can remove them manually if you'd like.%n%nWe hope to see you again someday!

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional Options:"; Flags: checkedonce
Name: "startupicon"; Description: "Start with Windows (recommended)"; GroupDescription: "Additional Options:"; Flags: checkedonce

[Files]
Source: "dist\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion
Source: "assets\icon.ico"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\icon.ico"
Name: "{group}\Uninstall {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\icon.ico"; Tasks: desktopicon

[Registry]
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "PDFScreenshotTool"; ValueData: """{app}\{#MyAppExeName}"""; Flags: uninsdeletevalue; Tasks: startupicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch {#MyAppName} now"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{app}"

[Code]
var
  WhatsNewPage: TWizardPage;
  HowItWorksPage: TWizardPage;
  FeaturesPage: TWizardPage;
  UseCasesPage: TWizardPage;

procedure CreateInfoLabel(Page: TWizardPage; TopPos: Integer; LabelCaption: String; IsHeader: Boolean; IsHighlight: Boolean);
var
  InfoLabel: TLabel;
begin
  InfoLabel := TLabel.Create(Page);
  InfoLabel.Parent := Page.Surface;
  InfoLabel.Left := 0;
  InfoLabel.Top := TopPos;
  InfoLabel.Width := Page.SurfaceWidth;
  InfoLabel.Caption := LabelCaption;
  InfoLabel.WordWrap := True;
  InfoLabel.AutoSize := False;
  InfoLabel.Font.Name := 'Segoe UI';
  
  if IsHighlight then
  begin
    InfoLabel.Font.Size := 11;
    InfoLabel.Font.Color := $00EED322;
    InfoLabel.Height := 28;
  end
  else if IsHeader then
  begin
    InfoLabel.Font.Size := 18;
    InfoLabel.Font.Style := [fsBold];
    InfoLabel.Font.Color := $006B6BFF;
    InfoLabel.Height := 36;
  end
  else
  begin
    InfoLabel.Font.Size := 10;
    InfoLabel.Font.Color := $00AAAAAA;
    InfoLabel.Height := 50;
  end;
end;

procedure CreateWhatsNewPage;
begin
  WhatsNewPage := CreateCustomPage(wpWelcome, 
    'What''s New in v2.1.0', 
    'Latest improvements and fixes');
  
  CreateInfoLabel(WhatsNewPage, 8, 'Latest Updates', True, False);
  
  CreateInfoLabel(WhatsNewPage, 52, '🔧 Fixed Installation Scrolling', False, True);
  CreateInfoLabel(WhatsNewPage, 76, 'You can now scroll through the entire welcome screen! No more missing the "Start" button or important instructions.', False, False);
  
  CreateInfoLabel(WhatsNewPage, 130, '😄 Funnier Setup Experience', False, True);
  CreateInfoLabel(WhatsNewPage, 154, 'We''ve spiced up the welcome screen with more engaging, humorous text. Installation doesn''t have to be boring!', False, False);
  
  CreateInfoLabel(WhatsNewPage, 208, '🧠 AI Duplicate Detection', False, True);
  CreateInfoLabel(WhatsNewPage, 232, 'Smart perceptual hashing automatically skips identical pages, saving you disk space and processing time.', False, False);
  
  CreateInfoLabel(WhatsNewPage, 286, '⚙️ Improved Settings', False, True);
  CreateInfoLabel(WhatsNewPage, 310, 'Better organized settings window with more customization options and clearer explanations.', False, False);
end;

procedure CreateHowItWorksPage;
begin
  HowItWorksPage := CreateCustomPage(WhatsNewPage.ID, 
    'How It Works', 
    'Zero-effort PDF page capture - just scroll and go!');
  
  CreateInfoLabel(HowItWorksPage, 8, 'The Magic Behind the Scenes', True, False);
  
  CreateInfoLabel(HowItWorksPage, 52, '[1]  DETECT', False, True);
  CreateInfoLabel(HowItWorksPage, 76, 'The tool automatically detects when Adobe Acrobat is open and actively monitors your PDF navigation.', False, False);
  
  CreateInfoLabel(HowItWorksPage, 130, '[2]  CAPTURE', False, True);
  CreateInfoLabel(HowItWorksPage, 154, 'Every time you turn to a new page, a high-quality screenshot is instantly captured - no clicking required!', False, False);
  
  CreateInfoLabel(HowItWorksPage, 208, '[3]  ORGANIZE', False, True);
  CreateInfoLabel(HowItWorksPage, 232, 'Screenshots are saved with smart naming (PDF name + page number + timestamp) in your chosen folder.', False, False);
  
  CreateInfoLabel(HowItWorksPage, 286, '[4]  DEDUPLICATE', False, True);
  CreateInfoLabel(HowItWorksPage, 310, 'AI-powered duplicate detection ensures you only keep unique captures - no wasted storage!', False, False);
  
  CreateInfoLabel(HowItWorksPage, 364, 'NEW in v2.1.0: Fixed installation scrolling + funnier welcome screen!', False, True);
end;

procedure CreateFeaturesPage;
begin
  FeaturesPage := CreateCustomPage(HowItWorksPage.ID, 
    'Key Features', 
    'Everything you need for effortless PDF documentation');
  
  CreateInfoLabel(FeaturesPage, 8, 'Why You Will Love It', True, False);
  
  CreateInfoLabel(FeaturesPage, 52, '>>  Automatic Capture', False, True);
  CreateInfoLabel(FeaturesPage, 76, 'Screenshots happen automatically as you browse - focus on reading, not clicking.', False, False);
  
  CreateInfoLabel(FeaturesPage, 122, '>>  Smart Duplicate Detection', False, True);
  CreateInfoLabel(FeaturesPage, 146, 'Perceptual hashing technology identifies and skips duplicate pages automatically.', False, False);
  
  CreateInfoLabel(FeaturesPage, 192, '>>  Keyboard Shortcuts', False, True);
  CreateInfoLabel(FeaturesPage, 216, 'Quick controls: Ctrl+Shift+S to toggle, Ctrl+Shift+P for manual capture, and more.', False, False);
  
  CreateInfoLabel(FeaturesPage, 262, '>>  Flexible Output', False, True);
  CreateInfoLabel(FeaturesPage, 286, 'Save as PNG, JPEG, or WebP. Customize quality, naming patterns, and save locations.', False, False);
  
  CreateInfoLabel(FeaturesPage, 332, '>>  Auto-Updates', False, True);
  CreateInfoLabel(FeaturesPage, 356, 'Stay current with automatic update checks and one-click upgrades.', False, False);
  
  CreateInfoLabel(FeaturesPage, 402, '>>  Improved Installation', False, True);
  CreateInfoLabel(FeaturesPage, 426, 'Fixed scrolling in welcome screen + funnier setup text for a better first impression!', False, False);
end;

procedure CreateUseCasesPage;
begin
  UseCasesPage := CreateCustomPage(FeaturesPage.ID, 
    'Perfect For', 
    'Built for professionals who need reliable documentation');
  
  CreateInfoLabel(UseCasesPage, 8, 'Real-World Use Cases', True, False);
  
  CreateInfoLabel(UseCasesPage, 52, '*  Compliance and Auditing', False, True);
  CreateInfoLabel(UseCasesPage, 76, 'Create verifiable proof that every page of a document was reviewed. Essential for regulatory compliance.', False, False);
  
  CreateInfoLabel(UseCasesPage, 130, '*  Legal Documentation', False, True);
  CreateInfoLabel(UseCasesPage, 154, 'Maintain timestamped evidence of document review for legal proceedings and contracts.', False, False);
  
  CreateInfoLabel(UseCasesPage, 208, '*  Research and Analysis', False, True);
  CreateInfoLabel(UseCasesPage, 232, 'Capture key pages from research papers, reports, and reference materials for later review.', False, False);
  
  CreateInfoLabel(UseCasesPage, 286, '*  Quality Assurance', False, True);
  CreateInfoLabel(UseCasesPage, 310, 'Document that standard operating procedures and manuals were properly reviewed.', False, False);
  
  CreateInfoLabel(UseCasesPage, 364, 'TIP: The tool runs silently in your system tray - just set it and forget it!', False, False);
end;

procedure InitializeWizard;
begin
  WizardForm.Color := $000F0A0A;
  
  CreateWhatsNewPage;
  CreateHowItWorksPage;
  CreateFeaturesPage;
  CreateUseCasesPage;
  
  WizardForm.WelcomeLabel1.Font.Name := 'Segoe UI';
  WizardForm.WelcomeLabel1.Font.Size := 22;
  WizardForm.WelcomeLabel1.Font.Style := [fsBold];
  WizardForm.WelcomeLabel1.Font.Color := $006B6BFF;
  
  WizardForm.WelcomeLabel2.Font.Name := 'Segoe UI';
  WizardForm.WelcomeLabel2.Font.Size := 10;
  WizardForm.WelcomeLabel2.Font.Color := $00AAAAAA;
  
  WizardForm.FinishedLabel.Font.Name := 'Segoe UI';
  WizardForm.FinishedLabel.Font.Size := 10;
  WizardForm.FinishedLabel.Font.Color := $00AAAAAA;
  
  WizardForm.FinishedHeadingLabel.Font.Name := 'Segoe UI';
  WizardForm.FinishedHeadingLabel.Font.Size := 22;
  WizardForm.FinishedHeadingLabel.Font.Style := [fsBold];
  WizardForm.FinishedHeadingLabel.Font.Color := $007CDB69;
  
  WizardForm.DirEdit.Font.Name := 'Consolas';
  WizardForm.DirEdit.Font.Size := 9;
  WizardForm.DirEdit.Color := $00202020;
  WizardForm.DirEdit.Font.Color := $00FFFFFF;
  
  WizardForm.TasksList.Font.Name := 'Segoe UI';
  WizardForm.TasksList.Font.Size := 10;
  WizardForm.TasksList.Color := $00151515;
  WizardForm.TasksList.Font.Color := $00FFFFFF;
  
  WizardForm.SelectDirLabel.Font.Name := 'Segoe UI';
  WizardForm.SelectDirLabel.Font.Size := 10;
  WizardForm.SelectDirLabel.Font.Color := $00AAAAAA;
  
  WizardForm.SelectDirBrowseLabel.Font.Name := 'Segoe UI';
  WizardForm.SelectDirBrowseLabel.Font.Size := 10;
  WizardForm.SelectDirBrowseLabel.Font.Color := $00AAAAAA;
  
  WizardForm.PageNameLabel.Font.Name := 'Segoe UI Semibold';
  WizardForm.PageNameLabel.Font.Size := 14;
  WizardForm.PageNameLabel.Font.Color := $006B6BFF;
  
  WizardForm.PageDescriptionLabel.Font.Name := 'Segoe UI';
  WizardForm.PageDescriptionLabel.Font.Size := 10;
  WizardForm.PageDescriptionLabel.Font.Color := $00AAAAAA;
  
  WizardForm.ReadyMemo.Font.Name := 'Consolas';
  WizardForm.ReadyMemo.Font.Size := 9;
  WizardForm.ReadyMemo.Color := $00151515;
  WizardForm.ReadyMemo.Font.Color := $00FFFFFF;
  
  WizardForm.InnerPage.Color := $000F0A0A;
end;

function InitializeSetup(): Boolean;
begin
  Result := True;
end;

procedure CurPageChanged(CurPageID: Integer);
begin
  case CurPageID of
    wpWelcome:
      WizardForm.NextButton.Caption := 'What''s New';
    wpSelectDir:
      WizardForm.NextButton.Caption := 'Continue';
    wpSelectTasks:
      WizardForm.NextButton.Caption := 'Install';
    wpFinished:
      WizardForm.NextButton.Caption := 'Launch';
  else
    if CurPageID = WhatsNewPage.ID then
      WizardForm.NextButton.Caption := 'How It Works'
    else if CurPageID = HowItWorksPage.ID then
      WizardForm.NextButton.Caption := 'See Features'
    else if CurPageID = FeaturesPage.ID then
      WizardForm.NextButton.Caption := 'Use Cases'
    else if CurPageID = UseCasesPage.ID then
      WizardForm.NextButton.Caption := 'Install'
    else
      WizardForm.NextButton.Caption := 'Next';
  end;
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then
  begin
  end;
end;
