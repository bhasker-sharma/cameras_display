# tuyere_camera.spec
# PyInstaller build spec for Tuyere Camera Viewer
# Build mode  : --onedir  (faster startup, better for always-on surveillance apps)
# Output      : dist\TuyereCameraViewer\TuyereCameraViewer.exe
#
# Do NOT run this file directly.  Use build.bat instead —
# it handles PyInstaller, then copies GStreamer / FFmpeg / VLC alongside the EXE.
# -*- mode: python ; coding: utf-8 -*-

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[
        # Bundle read-only assets so logo.png / logo.ico are available at runtime
        ('assets', 'assets'),
    ],
    hiddenimports=[
        # python-vlc is a ctypes wrapper; PyInstaller won't auto-detect it
        'vlc',
        # reportlab sub-packages are not always auto-detected by the hook
        'reportlab.platypus',
        'reportlab.lib.pagesizes',
        'reportlab.lib.styles',
        'reportlab.lib.colors',
        'reportlab.lib.enums',
        'reportlab.graphics',
        # psutil platform-specific backend for Windows
        'psutil',
        'psutil._pswindows',
        # OpenCV
        'cv2',
        # numpy (usually auto-detected; listed for safety)
        'numpy',
        # PyQt5 SIP binding layer
        'PyQt5.sip',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Unused Qt modules — reduces build size
        'PyQt5.QtMultimedia',
        'PyQt5.QtMultimediaWidgets',
        'PyQt5.QtBluetooth',
        'PyQt5.QtNfc',
        'PyQt5.QtSql',
        'PyQt5.QtTest',
        'PyQt5.QtXml',
        'tkinter',
        'matplotlib',
    ],
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,         # onedir: binaries collected separately
    name='TuyereCameraViewer',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    console=False,                 # no black console window
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='assets/logo.ico',
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='TuyereCameraViewer',     # output folder: dist\TuyereCameraViewer\
)
