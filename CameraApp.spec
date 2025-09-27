# -- mode: python ; coding: utf-8 --
import os
from PyInstaller.utils.hooks import collect_data_files

# Collect data files for VLC
vlc_datas = []
if os.path.exists('core/vlc_runtime'):
    vlc_datas = [('core/vlc_runtime', 'vlc_runtime')]

# Collect FFmpeg binary
ffmpeg_datas = []
if os.path.exists('core/ffmpeg_binary'):
    ffmpeg_datas = [('core/ffmpeg_binary', 'ffmpeg_binary')]

# Collect assets
asset_datas = []
if os.path.exists('assets'):
    asset_datas = [('assets', 'assets')]

block_cipher = None

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=vlc_datas + ffmpeg_datas + asset_datas,
    hiddenimports=[
        'PyQt5.QtCore',
        'PyQt5.QtWidgets', 
        'PyQt5.QtGui',
        'PyQt5.QtMultimedia',
        'PyQt5.QtMultimediaWidgets',
        'cv2',
        'numpy',
        'vlc',
        'reportlab.pdfgen',
        'reportlab.lib.pagesizes',
        'reportlab.platypus',
        'reportlab.lib.styles',
        'reportlab.lib.colors',
        'reportlab.lib.enums',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='CameraViewer',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,  # Set to False for windowed app
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='assets/logo.png' if os.path.exists('assets/logo.png') else None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='CameraViewer',
)