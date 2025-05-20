# camera_app/ui/styles.py

from PyQt5.QtGui import QPalette
from PyQt5.QtCore import Qt

def apply_dark_theme(app):
    app.setStyle("Fusion")
    dark_palette = QPalette()

    dark_palette.setColor(QPalette.Window, Qt.black)
    dark_palette.setColor(QPalette.WindowText, Qt.white)
    dark_palette.setColor(QPalette.Base, Qt.black)
    dark_palette.setColor(QPalette.AlternateBase, Qt.darkGray)
    dark_palette.setColor(QPalette.ToolTipBase, Qt.black)
    dark_palette.setColor(QPalette.ToolTipText, Qt.white)
    dark_palette.setColor(QPalette.Text, Qt.white)
    dark_palette.setColor(QPalette.Button, Qt.darkGray)
    dark_palette.setColor(QPalette.ButtonText, Qt.white)
    dark_palette.setColor(QPalette.BrightText, Qt.red)
    dark_palette.setColor(QPalette.Highlight, Qt.darkBlue)
    dark_palette.setColor(QPalette.HighlightedText, Qt.white)

    app.setPalette(dark_palette)

    app.setStyleSheet("""
        QMainWindow {
            background-color: #121212;
        }
        QDialog {
            background-color: #1e1e1e;
            color: white;
        }
        QLabel {
            color: white;
        }
        QComboBox, QLineEdit {
            background-color: #333;
            color: white;
            border: 1px solid #555;
            padding: 4px;
            border-radius: 4px;
        }
        QComboBox::drop-down {
            border: 0px;
        }
        QComboBox::down-arrow {
            image: url(dropdown.png);
            width: 12px;
            height: 12px;
        }
        QComboBox QAbstractItemView {
            background-color: #333;
            color: white;
        }
    """)
