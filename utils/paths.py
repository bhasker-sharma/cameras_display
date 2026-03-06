# utils/paths.py
"""
Centralized path resolver for bundled tools and read-only assets.
Handles both source runs and PyInstaller --onedir frozen EXE.

Usage in main.py (must be first, before other imports):
    from utils.paths import setup_runtime_env, resource_path
    setup_runtime_env()
"""

import os
import sys


def get_app_root() -> str:
    """
    Return the application root directory.
      Frozen EXE  → directory that contains the EXE  (sys.executable dir)
      Source run  → project root  (parent of utils/)
    """
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    # utils/paths.py lives inside utils/ → go one level up to reach project root
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def resource_path(relative: str) -> str:
    """
    Resolve path to a read-only bundled asset (e.g. 'assets/logo.png').
      Frozen --onedir : _MEIPASS == exe dir, so assets live right beside the exe.
      Source run      : resolves from project root.
    """
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative)
    return os.path.join(get_app_root(), relative)


def get_ffmpeg_path() -> str:
    """Bundled bin/ffmpeg.exe — falls back to 'ffmpeg' on system PATH."""
    bundled = os.path.join(get_app_root(), 'bin', 'ffmpeg.exe')
    return bundled if os.path.exists(bundled) else 'ffmpeg'


def get_ffprobe_path() -> str:
    """Bundled bin/ffprobe.exe — falls back to 'ffprobe' on system PATH."""
    bundled = os.path.join(get_app_root(), 'bin', 'ffprobe.exe')
    return bundled if os.path.exists(bundled) else 'ffprobe'


def get_gstreamer_root() -> str:
    """
    Resolve GStreamer root directory, checked in priority order:
      1. Bundled  gstreamer/  folder alongside the EXE
      2. GSTREAMER_1_0_ROOT_MSVC_X86_64 environment variable
      3. Default system installation path
    """
    bundled = os.path.join(get_app_root(), 'gstreamer')
    if os.path.isdir(bundled):
        return bundled

    env_root = os.environ.get('GSTREAMER_1_0_ROOT_MSVC_X86_64', '')
    if env_root and os.path.isdir(env_root):
        return env_root

    return r'C:\Program Files\gstreamer\1.0\msvc_x86_64'


def get_data_dir() -> str:
    """
    Return the writable application data directory.
      Frozen EXE  → %APPDATA%\\TuyereCameraViewer\\  (safe, always writable)
      Source run  → project root  (same folder as the source files)
    """
    if getattr(sys, 'frozen', False):
        appdata = os.environ.get('APPDATA', os.path.expanduser('~'))
        data_dir = os.path.join(appdata, 'TuyereCameraViewer')
    else:
        data_dir = get_app_root()
    os.makedirs(data_dir, exist_ok=True)
    return data_dir


def setup_runtime_env() -> None:
    """
    Configure environment variables for VLC, GStreamer, and FFmpeg.
    Call this ONCE at startup in main.py before any other imports.
    """
    root = get_app_root()

    # ── VLC ────────────────────────────────────────────────────────────────
    # python-vlc uses PYTHON_VLC_MODULE_PATH to locate libvlc.dll.
    # Bundled libvlc.dll lives directly in the app root.
    if os.path.exists(os.path.join(root, 'libvlc.dll')):
        os.environ.setdefault('PYTHON_VLC_MODULE_PATH', root)
        os.environ.setdefault('VLC_PLUGIN_PATH', os.path.join(root, 'plugins'))

    # ── GStreamer ───────────────────────────────────────────────────────────
    gst_root = get_gstreamer_root()
    gst_bin  = os.path.join(gst_root, 'bin')
    gst_libs = os.path.join(gst_root, 'lib', 'gstreamer-1.0')

    if os.path.isdir(gst_bin):
        current_path = os.environ.get('PATH', '')
        if gst_bin not in current_path:
            os.environ['PATH'] = gst_bin + os.pathsep + current_path

    if os.path.isdir(gst_libs):
        os.environ.setdefault('GST_PLUGIN_PATH_1_0', gst_libs)

    # Plugin registry must live in a writable location (_MEIPASS is read-only)
    os.environ.setdefault(
        'GST_REGISTRY_1_0',
        os.path.join(get_data_dir(), 'gst_registry.bin')
    )
