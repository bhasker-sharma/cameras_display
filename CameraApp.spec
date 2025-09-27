# CameraApp.spec

import os
import sys
from PyInstaller.utils.hooks import collect_submodules, collect_all, collect_data_files

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

# ✅ Collect everything from OpenCV (cv2) with enhanced configuration
opencv_datas, opencv_binaries, opencv_hiddenimports = collect_all('cv2')

# ✅ Additional OpenCV data collection - this is crucial for the config.py issue
try:
    # Collect cv2 data files including config.py
    cv2_data_files = collect_data_files('cv2')
    opencv_datas.extend(cv2_data_files)
except Exception as e:
    print(f"Warning: Could not collect cv2 data files: {e}")

# ✅ Find OpenCV installation path and collect config files manually
try:
    import cv2
    cv2_path = os.path.dirname(cv2.__file__)
    config_py_path = os.path.join(cv2_path, 'config.py')
    if os.path.exists(config_py_path):
        opencv_datas.append((config_py_path, 'cv2'))
    
    # Also collect any .py files in cv2 directory that might be needed
    for file in os.listdir(cv2_path):
        if file.endswith('.py'):
            full_path = os.path.join(cv2_path, file)
            if os.path.isfile(full_path):
                opencv_datas.append((full_path, 'cv2'))
    
    print(f"OpenCV path: {cv2_path}")
    print(f"Added OpenCV config files from: {cv2_path}")
except Exception as e:
    print(f"Warning: Could not locate OpenCV files: {e}")

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
        'PIL._imaging', 'PIL._imagingft', 'PIL._webp', 'PIL._tkinter_finder',
        # 👇 OpenCV specific imports
        'cv2.cv2',
        'numpy.core._multiarray_umath',
        'numpy.core._multiarray_tests',
        'numpy.linalg._umath_linalg',
        'numpy.random._common',
        'numpy.random.bit_generator',
        'numpy.random._bounded_integers',
        'numpy.random.mtrand',
        'numpy.random._mt19937',
        'numpy.random._pcg64',
        'numpy.random._philox',
        'numpy.random._sfc64',
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
    console=False,  # Set to True for debugging if needed
    icon='assets/logo.ico',
    onefile=True,  
)