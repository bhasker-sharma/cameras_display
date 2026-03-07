; tuyere_setup.iss
; Inno Setup 6 installer script for Tuyere Camera Viewer
;
; Run via build.bat, or manually:
;   "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" installer\tuyere_setup.iss
;
; Output: installer\TuyereCameraViewer_Setup.exe

#define AppName      "Tuyere Camera Viewer"
#define AppVersion   "1.0.0"
#define AppPublisher "TIPL"
#define AppExeName   "TuyereCameraViewer.exe"
#define SourceDir    "..\dist\TuyereCameraViewer"
#define AppURL       "https://tipl.com"

; ── [Setup] ──────────────────────────────────────────────────────────────────
[Setup]
; Unique application ID — do NOT change after first release (used by uninstaller)
AppId={{A7F3E2C1-84B0-4D56-9E3A-2F10B8C7D495}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher={#AppPublisher}
AppPublisherURL={#AppURL}
AppSupportURL={#AppURL}
AppUpdatesURL={#AppURL}

; Installation directory
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}

; Always install machine-wide with admin rights (required for HKLM registry writes)
PrivilegesRequired=admin

; Output
OutputDir=.
OutputBaseFilename=TuyereCameraViewer_Setup
SetupIconFile=..\assets\logo.ico

; Compression (lzma2/ultra64 gives the smallest installer)
Compression=lzma2/ultra64
SolidCompression=yes
LZMAUseSeparateProcess=yes

; Visual style
WizardStyle=modern
WizardSizePercent=120

; Only install on 64-bit Windows
ArchitecturesInstallIn64BitMode=x64
ArchitecturesAllowed=x64

; Minimum Windows version: Windows 10 (10.0)
MinVersion=10.0

; ── [Languages] ──────────────────────────────────────────────────────────────
[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

; ── [Tasks] ──────────────────────────────────────────────────────────────────
[Tasks]
Name: "desktopicon";    Description: "Create a &desktop shortcut";    GroupDescription: "Additional shortcuts:"
Name: "startupicon";    Description: "Launch automatically at &Windows startup"; GroupDescription: "Additional shortcuts:"; Flags: unchecked

; ── [Files] ──────────────────────────────────────────────────────────────────
[Files]
; All files from the PyInstaller output folder (app + GStreamer + VLC + FFmpeg)
Source: "{#SourceDir}\*"; \
    DestDir: "{app}"; \
    Flags: ignoreversion recursesubdirs createallsubdirs

; ── [Dirs] ───────────────────────────────────────────────────────────────────
[Dirs]
; Create writable runtime directories the app needs
Name: "{app}\recordings"
Name: "{app}\logs"
Name: "{app}\temp"

; ── [Icons] ──────────────────────────────────────────────────────────────────
[Icons]
; Start Menu
Name: "{group}\{#AppName}"; \
    Filename: "{app}\{#AppExeName}"; \
    WorkingDir: "{app}"; \
    IconFilename: "{app}\_internal\assets\logo.ico"

Name: "{group}\Uninstall {#AppName}"; \
    Filename: "{uninstallexe}"

; Desktop shortcut (optional task)
Name: "{autodesktop}\{#AppName}"; \
    Filename: "{app}\{#AppExeName}"; \
    WorkingDir: "{app}"; \
    IconFilename: "{app}\_internal\assets\logo.ico"; \
    Tasks: desktopicon

; Windows Startup (optional task)
Name: "{userstartup}\{#AppName}"; \
    Filename: "{app}\{#AppExeName}"; \
    WorkingDir: "{app}"; \
    Tasks: startupicon

; ── [Registry] ───────────────────────────────────────────────────────────────
[Registry]
; Register the app so it appears in "Apps & Features"
Root: HKLM; Subkey: "Software\{#AppPublisher}\{#AppName}"; \
    ValueType: string; ValueName: "InstallPath"; ValueData: "{app}"; \
    Flags: uninsdeletekey

; ── [Run] ────────────────────────────────────────────────────────────────────
[Run]
; Offer to launch the app after installation
Filename: "{app}\{#AppExeName}"; \
    Description: "Launch {#AppName} now"; \
    WorkingDir: "{app}"; \
    Flags: nowait postinstall skipifsilent

; ── [UninstallRun] ───────────────────────────────────────────────────────────
[UninstallRun]
; Kill running processes before uninstall
Filename: "taskkill.exe"; Parameters: "/F /IM {#AppExeName}";     Flags: runhidden; RunOnceId: "KillApp"
Filename: "taskkill.exe"; Parameters: "/F /IM gst-launch-1.0.exe"; Flags: runhidden; RunOnceId: "KillGst"
Filename: "taskkill.exe"; Parameters: "/F /IM ffmpeg.exe";         Flags: runhidden; RunOnceId: "KillFfmpeg"

; ── [UninstallDelete] ────────────────────────────────────────────────────────
[UninstallDelete]
; Remove runtime-generated files that weren't part of the original install
Type: filesandordirs; Name: "{app}\logs"
Type: filesandordirs; Name: "{app}\temp"
Type: filesandordirs; Name: "{app}\gst_registry.bin"
; NOTE: recordings\ is intentionally NOT deleted on uninstall to preserve footage
