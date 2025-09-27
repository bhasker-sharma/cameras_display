# CameraApp.spec

import os
from PyInstaller.utils.hooks import collect_submodules, collect_all

block_cipher = None

def collect_folder(folder_path, target_folder):
    datas = []
    for root, _, files in os.walk(folder_path):
        for f in files:
            src = os.path.join(root, f)
            rel = os.path.relpath(src, folder_path)
            dst = os.path.join(target_folder, rel)
            datas.append((src, dst))
    return datas

# ✅ Collect everything from Pillow (PIL) to fix ImportError: _imaging
pillow_datas, pillow_binaries, pillow_hiddenimports = collect_all('PIL')

# ✅ Collect everything from OpenCV (cv2)
opencv_datas, opencv_binaries, opencv_hiddenimports = collect_all('cv2')

# ✅ Collect everything from ReportLab
reportlab_datas, reportlab_binaries, reportlab_hiddenimports = collect_all('reportlab')

# ✅ Collect all submodules from your own packages
project_hidden = (
    collect_submodules('config') +
    collect_submodules('core') +
    collect_submodules('ui') +
    collect_submodules('controller') +
    collect_submodules('utils')
)

a = Analysis(
    ['main.py'],
    pathex=['.', 'config', 'core', 'ui', 'controller', 'utils'],
    binaries=pillow_binaries + opencv_binaries + reportlab_binaries,
    datas=[
        *pillow_datas,
        *opencv_datas,
        *reportlab_datas,
        *collect_folder('assets', 'assets'),
        *collect_folder('ffmpeg_binary', 'ffmpeg_binary'),
        *collect_folder('vlc_runtime', 'vlc_runtime'),
        ('camera_config.json', '.'),
        ('camera_streams.json', '.'),
    ],
    hiddenimports=[
        *pillow_hiddenimports,
        *opencv_hiddenimports,
        *reportlab_hiddenimports,
        *project_hidden,
        'os', 'sys',
        'PyQt5.sip',
        'vlc',
        'PyQt5.QtMultimedia',
        # extra stdlib modules
        'email', 'email.parser', 'email.feedparser', 'email.utils',
        'copy', 'types', 'collections', 'inspect', 'traceback',
        'calendar', 'http.client', 'urllib.request',
        # 👇 explicit Pillow C-extensions
        'PIL._imaging', 'PIL._imagingft', 'PIL._webp', 'PIL._tkinter_finder'
    ],
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    noarchive=True,  
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,    # ✅ include binaries
    a.datas,       # ✅ include datas
    [],
    name='CameraAppSecure',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    icon='assets/logo.ico',
    onefile=True,  
)
