# camera_app/main.py

import sys,os
from PyQt5.QtWidgets import QApplication, QMessageBox
from PyQt5.QtCore import Qt
from controller.app_controller import AppController
from ui.styles import apply_dark_theme
from utils.logging import log
from PyQt5.QtGui import QIcon
from utils.security_pendrive import check_pendrive_key
from utils.helper import fix_orphaned_metadata

def main():
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

    app = QApplication(sys.argv)
    app.setWindowIcon(QIcon("assets/logo.png"))
    apply_dark_theme(app)

    # ---- Fix metadata left orphaned by previous crash/close ----
    try:
        fix_orphaned_metadata()
    except Exception as e:
        log.warning(f"Failed to fix orphaned metadata on startup: {e}")
    # ------------------------------------------------------------

    # ---- Security USB check (pendrive dongle) ----
    ok, err = check_pendrive_key()
    if not ok:
        m = QMessageBox()
        m.setIcon(QMessageBox.Critical)
        m.setWindowTitle("Security USB Required")
        m.setText(err or "Authorization failed.")
        m.exec_()
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

    log.info("Exiting application.")
    os._exit(exit_code)

if __name__ == "__main__":
    main()
