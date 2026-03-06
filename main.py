# camera_app/main.py

import sys, os

# ── Setup bundled tool paths FIRST, before any other imports ──────────────
from utils.paths import setup_runtime_env, resource_path
setup_runtime_env()
# ──────────────────────────────────────────────────────────────────────────

from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import Qt
from controller.app_controller import AppController
from ui.styles import apply_dark_theme
from utils.logging import log
from PyQt5.QtGui import QIcon
from utils.security_pendrive import check_pendrive_key
from utils.helper import fix_orphaned_metadata
from utils.subproc import kill_orphaned_subprocesses

RESTART_EXIT_CODE = 2

def run_app():
    """Run one application cycle. Returns the exit code."""
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

    app = QApplication(sys.argv)
    app.setWindowIcon(QIcon(resource_path("assets/logo.png")))
    apply_dark_theme(app)

    # ---- Kill orphaned ffmpeg/gstreamer from previous crash ----
    try:
        kill_orphaned_subprocesses()
    except Exception as e:
        log.warning(f"Failed to kill orphaned subprocesses: {e}")
    # ------------------------------------------------------------

    # ---- Fix metadata left orphaned by previous crash/close ----
    try:
        from config.config_manager import ConfigManager as _CM
        _recording_folder = _CM().get_recording_folder()
        fix_orphaned_metadata(recordings_root=_recording_folder)
    except Exception as e:
        log.warning(f"Failed to fix orphaned metadata on startup: {e}")
    # ------------------------------------------------------------

    # ---- Security USB check (pendrive dongle) ----
    ok, err = check_pendrive_key()
    if not ok:
        from controller.app_controller import DongleWarningDialog
        dialog = DongleWarningDialog(
            error_message=(
                "No authorized security USB device was detected.\n\n"
                "Please insert the device to start the application,\n"
                "or press OK to exit."
            ),
            heading="SECURITY USB REQUIRED",
            status_text="Waiting for device to be inserted ...",
        )
        result = dialog.exec_()
        if result != dialog.Accepted:
            sys.exit(1)
        # Dongle was inserted while dialog was open — re-verify before proceeding
        ok, err = check_pendrive_key()
        if not ok:
            sys.exit(1)
    # ----------------------------------------------

    controller = AppController()

    try:
        exit_code = app.exec_()
    except Exception as e:
        log.exception("Unhandled exception occurred")
        exit_code = 1

    # Fast shutdown: signal everything to stop, don't block
    try:
        controller.shutdown()
    except Exception as e:
        log.warning(f"Shutdown error (ignored): {e}")

    return exit_code

def main():
    while True:
        exit_code = run_app()
        if exit_code == RESTART_EXIT_CODE:
            log.info("Restarting application (config changed)...")
            continue
        log.info("Exiting application.")
        os._exit(exit_code)

if __name__ == "__main__":
    main()
