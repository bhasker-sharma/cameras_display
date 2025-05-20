# camera_app/ui/dialogs.py

from PyQt5.QtWidgets import (
    QDialog, QLabel, QLineEdit, QComboBox, QPushButton,
    QVBoxLayout, QGridLayout, QDialogButtonBox
)
from PyQt5.QtCore import Qt

from PyQt5.QtWidgets import (
    QDialog, QLabel, QLineEdit, QComboBox, QPushButton,
    QVBoxLayout, QGridLayout, QDialogButtonBox, QApplication
)
from PyQt5.QtCore import Qt

class CameraConfigDialog(QDialog):
    def __init__(self, camera_count, config_manager, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Configure Camera")
        self.setFixedSize(400, 300)
        self.config_manager = config_manager

        layout = QVBoxLayout()
        form_layout = QGridLayout()

        # Camera Number
        form_layout.addWidget(QLabel("Camera Number:"), 0, 0)
        self.camera_num_combo = QComboBox()
        self.camera_num_combo.addItems([str(i) for i in range(1, camera_count + 1)])
        self.camera_num_combo.currentIndexChanged.connect(self.load_existing_config)
        form_layout.addWidget(self.camera_num_combo, 0, 1)

        # Camera Name
        form_layout.addWidget(QLabel("Camera Name:"), 1, 0)
        self.name_edit = QLineEdit()
        self.name_edit.setFocusPolicy(Qt.StrongFocus)
        form_layout.addWidget(self.name_edit, 1, 1)

        # RTSP URL
        form_layout.addWidget(QLabel("RTSP URL:"), 2, 0)
        self.rtsp_input = QLineEdit()
        self.rtsp_input.setFocusPolicy(Qt.StrongFocus)
        form_layout.addWidget(self.rtsp_input, 2, 1)

        # Enable Toggle
        form_layout.addWidget(QLabel("Enable Camera:"), 3, 0)
        self.enable_checkbox = QPushButton("Enabled")
        self.enable_checkbox.setCheckable(True)
        self.enable_checkbox.setChecked(True)
        self.enable_checkbox.setStyleSheet("""
            QPushButton {
                background-color: #555;
                color: white;
                padding: 6px 12px;
                border-radius: 4px;
            }
            QPushButton:checked {
                background-color: #007BFF;
            }
        """)
        form_layout.addWidget(self.enable_checkbox, 3, 1)

        layout.addLayout(form_layout)

        # OK/Cancel Buttons
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.save_config)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self.setLayout(layout)
        self.load_existing_config()
        self.center_dialog_on_screen()

    def load_existing_config(self):
        cam_id = int(self.camera_num_combo.currentText())
        data = self.config_manager.get_camera_config(cam_id)
        self.name_edit.setText(data.get("name", f"Camera {cam_id}"))
        self.rtsp_input.setText(data.get("rtsp", ""))
        self.enable_checkbox.setChecked(data.get("enabled", True))

    def save_config(self):
        cam_id = int(self.camera_num_combo.currentText())
        data = {
            "name": self.name_edit.text(),
            "rtsp": self.rtsp_input.text(),
            "enabled": self.enable_checkbox.isChecked()
        }
        self.config_manager.set_camera_config(cam_id, data)
        self.accept()

    def center_dialog_on_screen(self):
        screen = QApplication.primaryScreen().geometry()
        dialog_geom = self.frameGeometry()
        dialog_geom.moveCenter(screen.center())
        self.move(dialog_geom.topLeft())



class CameraCountDialog(QDialog):
    def __init__(self, valid_camera_counts=None):
        super().__init__()
        self.setWindowTitle("Select Number of Cameras")
        self.setFixedSize(300, 150)

        layout = QVBoxLayout()
        layout.addWidget(QLabel("Choose number of cameras to display:"))

        self.combo = QComboBox()
        valid_counts = valid_camera_counts or [4, 8, 12, 16, 20, 24, 32, 40, 44, 48]
        self.combo.addItems([str(c) for c in valid_counts])
        layout.addWidget(self.combo)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self.setLayout(layout)
        self.center_dialog_on_screen()

    def get_selected_count(self):
        return int(self.combo.currentText())

    def center_dialog_on_screen(self):
        screen = QApplication.primaryScreen().geometry()
        dialog_geom = self.frameGeometry()
        dialog_geom.moveCenter(screen.center())
        self.move(dialog_geom.topLeft())


