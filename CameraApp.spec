# CameraApp.spec

import os
from PyInstaller.utils.hooks import collect_submodules

block_cipher = None

# ✅ Helper to gather all files recursively in a folder
def collect_folder(folder_path, target_folder):
    datas = []
    for root, _, files in os.walk(folder_path):
        for f in files:
            src = os.path.join(root, f)
            rel = os.path.relpath(src, folder_path)
            dst = os.path.join(target_folder, rel)
            datas.append((src, dst))
    return datas


a = Analysis(
    ['main.py'],
    pathex=['.'],
    binaries=[],
    datas=[
        *collect_folder('assets', 'assets'),
        *collect_folder('ffmpeg_binary', 'ffmpeg_binary'),
        *collect_folder('vlc_runtime', 'vlc'),  # 👈 VLC runtime (dlls + plugins)
        ('camera_config.json', '.'),
        ('camera_streams.json', '.'),
    ],
    hiddenimports=[
        'os', 'sys',
        'PyQt5.sip',
        'vlc',
        'PyQt5.QtMultimedia',
    ],
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='CameraAppSecure',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,   # safer to disable
    console=False,
    icon='assets/logo.ico',
    onefile=True,  # 👈 single .exe build
)
