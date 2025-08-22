# camera_app/main.py

import sys,os
from PyQt5.QtWidgets import QApplication, QMessageBox
from PyQt5.QtCore import Qt
from controller.app_controller import AppController
from ui.styles import apply_dark_theme
from utils.logging import log
from PyQt5.QtGui import QIcon
from utils.security_pendrive import check_pendrive_key

def main():
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

    app = QApplication(sys.argv)
    app.setWindowIcon(QIcon("assets/logo.png"))
    apply_dark_theme(app)
    
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
        controller.stop_all_recordings()  # Ensure this is called on normal close
        sys.exit(exit_code)
    except SystemExit:
        log.info("SystemExit caught — shutting down hard.")
        controller.stop_all_recordings()  # Ensure this is called on crash too
        os._exit(0)
    except Exception as e:
        log.exception("Unhandled exception occurred")
        controller.stop_all_recordings()  # Catch-all shutdown protection
        msg_box = QMessageBox()
        msg_box.setIcon(QMessageBox.Critical)
        msg_box.setWindowTitle("Application Error")
        msg_box.setText("An unexpected error occurred.")
        msg_box.setInformativeText(str(e))
        msg_box.exec_()

if __name__ == "__main__":
    main()
