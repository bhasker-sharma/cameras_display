# camera_app/main.py

import sys,os
from PyQt5.QtWidgets import QApplication, QMessageBox
from PyQt5.QtCore import Qt
from controller.app_controller import AppController
from ui.styles import apply_dark_theme
from utils.logging import log
from PyQt5.QtGui import QIcon

def main():
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

    app = QApplication(sys.argv)
    app.setWindowIcon(QIcon("assets/logo.png"))
    apply_dark_theme(app)

    controller = AppController()

    try:
        sys.exit(app.exec_())
    except SystemExit:
        log.info("SystemExit caught — shutting down hard.")
        os._exit(0)
    except Exception as e:
        log.exception("Unhandled exception occurred")
        msg_box = QMessageBox()
        msg_box.setIcon(QMessageBox.Critical)
        msg_box.setWindowTitle("Application Error")
        msg_box.setText("An unexpected error occurred.")
        msg_box.setInformativeText(str(e))
        msg_box.exec_()

if __name__ == "__main__":
    main()
