import sys
import os
import json
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QDialog, QComboBox, QDialogButtonBox, QGridLayout, QSizePolicy,QLineEdit
)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QPixmap, QIcon
from centralisedlogging import log

CAMERA_STREAM_FILE = "camera_streams.json"
CONFIG_FILE = "camera_config.json"

# Grid format: {camera_count: [(window_id, rows, cols), ...]}
GRID_LAYOUTS = {
    4: [(0, 2, 2)],
    8: [(0, 2, 4)],
    12: [(0, 3, 4)],
    16: [(0, 4, 4)],
    20: [(0,5,4)],
    24: [(0, 4, 6)],
    32: [(0,4,4),(1,4,4)],
    40: [(0,5,4),(1,5,4)],
    44: [(0,5,4),(1,4,6)],
    48: [(0, 4, 6), (1, 4, 6)],  # 24 + 24
}

VALID_CAMERA_COUNTS = list(GRID_LAYOUTS.keys())

# ========================== Camera Stream ==========================
class CameraStreamConfigManager:
    def __init__(self, config_path=CAMERA_STREAM_FILE):
        self.config_path = config_path
        self.config = self.load_config()

    def load_config(self):
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, 'r') as f:
                    return json.load(f)
            except Exception:
                pass
        return {}

    def save_config(self):
        with open(self.config_path, 'w') as f:
            json.dump(self.config, f, indent=4)

    def get_camera_config(self, cam_id):
        return self.config.get(str(cam_id), {})

    def set_camera_config(self, cam_id, data):
        self.config[str(cam_id)] = data
        self.save_config()

# ========================== Camera config dialog ==========================
class CameraConfigDialog(QDialog):
    def __init__(self, camera_count, config_manager):
        super().__init__()
        self.setWindowTitle("Configure Camera")
        self.setFixedSize(400, 300)
        self.config_manager = config_manager

        layout = QVBoxLayout()

        # Camera Number
        form_layout = QGridLayout()
        form_layout.addWidget(QLabel("Camera Number:"), 0, 0)
        self.camera_num_combo = QComboBox()
        self.camera_num_combo.addItems([str(i) for i in range(1, camera_count + 1)])
        self.camera_num_combo.currentIndexChanged.connect(self.load_existing_config)
        form_layout.addWidget(self.camera_num_combo, 0, 1)

        # Camera Name
        form_layout.addWidget(QLabel("Camera Name:"), 1, 0)
        self.name_edit = QLineEdit()
        form_layout.addWidget(self.name_edit, 1, 1)

        # RTSP URL
        form_layout.addWidget(QLabel("RTSP URL:"), 2, 0)
        self.rtsp_input = QLineEdit()
        form_layout.addWidget(self.rtsp_input, 2, 1)

        # Enable Camera
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

        # Buttons
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.save_config)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self.setLayout(layout)
        self.load_existing_config()

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

# ========================== Config Manager ==========================
class ConfigManager:
    def __init__(self, config_path=CONFIG_FILE):
        self.config_path = config_path
        self.config = self.load_config()

    def load_config(self):
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, 'r') as f:
                    return json.load(f)
            except Exception:
                pass
        return {"camera_count": 0}

    def save_config(self):
        with open(self.config_path, 'w') as f:
            json.dump(self.config, f, indent=4)

    def get_camera_count(self):
        return self.config.get("camera_count", 0)

    def set_camera_count(self, count):
        self.config["camera_count"] = count
        self.save_config()


# ========================== Camera Count Dialog ==========================
class CameraCountDialog(QDialog):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Select Number of Cameras")
        self.setFixedSize(300, 150)
        layout = QVBoxLayout()
        layout.addWidget(QLabel("Choose number of cameras to display:"))

        self.combo = QComboBox()
        self.combo.addItems([str(c) for c in VALID_CAMERA_COUNTS])
        layout.addWidget(self.combo)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self.setLayout(layout)

    def get_selected_count(self):
        return int(self.combo.currentText())


# ========================== Camera Widget ==========================
class CameraWidget(QWidget):
    doubleClicked =  pyqtSignal(int)

    def __init__(self, cam_id, name="Camera", logo_path="assets/logo.png"):
        super().__init__()
        self.cam_id = cam_id
        self.name = name if name else f"Camera {cam_id}"
        self.logo_path = logo_path

        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setStyleSheet("border: 1px solid #444; background-color: #2c2c2c; border-radius: 5px;")

        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)

        # Top label
        self.title = QLabel(self.name)
        self.title.setAlignment(Qt.AlignCenter)
        self.title.setStyleSheet("color: white; background-color: #444; font-weight: bold; padding: 4px;")
        layout.addWidget(self.title)

        # Placeholder/logo
        self.content = QLabel()
        self.content.setAlignment(Qt.AlignCenter)
        self.content.setStyleSheet("background-color: #1a1a1a;")
        layout.addWidget(self.content, stretch=1)

        self.setLayout(layout)
        self.show_placeholder()

    def mouseDoubleClickEvent(self, event):
        self.doubleClicked.emit(self.cam_id)
    
    def show_placeholder(self):
        if os.path.exists(self.logo_path):
            pixmap = QPixmap(self.logo_path)
            if not pixmap.isNull():
                self.content.setPixmap(pixmap.scaled(
                    160, 120, Qt.KeepAspectRatio, Qt.SmoothTransformation))
                return
        self.content.setText("No Stream")


# ========================== Camera Window (Shared by Main + Additional) ==========================
class CameraWindow(QMainWindow):
    def __init__(self, title, camera_ids, rows, cols, config_manager, controller=None):
        super().__init__()
        self.setWindowTitle(title)
        self.setWindowIcon(QIcon("assets/logo.png") if os.path.exists("assets/logo.png") else QIcon())
        self.grid_layout = None
        self.focused = False
        self.focused_cam_id = None
        self.camera_ids = camera_ids
        self.rows = rows
        self.cols = cols
        self.config_manager = config_manager
        self.controller = controller

        self.central_widget = QWidget()
        layout = QVBoxLayout()
        self.central_widget.setLayout(layout)
        self.setCentralWidget(self.central_widget)

        # Optional navbar for main window
        if controller:
            nav = QHBoxLayout()
            # title_label = QLabel("Camera Viewer")
            # title_label.setStyleSheet("color: #f0f0f0; font-size: 18px; font-weight: bold;")
            # title_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

            change_btn = QPushButton("Change Camera Count")
            change_btn.clicked.connect(self.controller.change_camera_count)
            change_btn.setStyleSheet("""
                QPushButton {
                    background-color: #555;
                    color: white;
                    padding: 6px 14px;
                    border-radius: 4px;
                }
                QPushButton:hover {
                    background-color: #777;
                }
            """)

            config_btn = QPushButton("Configure Camera")
            config_btn.clicked.connect(self.controller.open_camera_config)
            config_btn.setStyleSheet("""
                QPushButton {
                    background-color: #555;
                    color: white;
                    padding: 6px 14px;
                    border-radius: 4px;
                }
                QPushButton:hover {
                    background-color: #777;
                }
            """)

            refresh_btn = QPushButton("Refresh System")
            refresh_btn.clicked.connect(self.controller.refresh_configurations)
            refresh_btn.setStyleSheet(change_btn.styleSheet())

            nav.addWidget(refresh_btn)
            # nav.addWidget(title_label)
            nav.addStretch()
            nav.addWidget(change_btn)
            nav.addWidget(config_btn)
            layout.addLayout(nav)

        self.grid_widget = QWidget()
        self.grid_layout = QGridLayout()
        self.grid_widget.setLayout(self.grid_layout)
        layout.addWidget(self.grid_widget)  # Add grid widget to main layout

        self.camera_widgets = {}

        for idx, cam_id in enumerate(camera_ids):
            r, c = divmod(idx, cols)

            # Fetch name from stream config if available
            stream_config = self.controller.stream_config.get_camera_config(cam_id) if self.controller else {}
            cam_name = stream_config.get("name", f"Camera {cam_id}")
            
            widget = CameraWidget(cam_id,name=cam_name)
            widget.doubleClicked.connect(self.toggle_focus_view)
            self.camera_widgets[cam_id] = widget
            self.grid_layout.addWidget(widget, r, c)
            self.grid_layout.setRowStretch(r, 1)
            self.grid_layout.setColumnStretch(c, 1)

        self.showMaximized()  # or showFullScreen()

    def toggle_focus_view(self, cam_id):
        if not self.focused:
            log.info(f"[{self.windowTitle()}] Expanding Camera {cam_id} to full view.")
            self.focused = True
            self.focused_cam_id = cam_id

            self.grid_widget.hide()  # Just hide the grid

            # 🔥 Load the correct camera name from config
            stream_config = self.controller.stream_config.get_camera_config(cam_id) if self.controller else {}
            cam_name = stream_config.get("name", f"Camera {cam_id}")

            # Create isolated camera view
            self.focused_widget = CameraWidget(cam_id , name = cam_name)
            self.focused_widget.doubleClicked.connect(self.toggle_focus_view)
            self.centralWidget().layout().addWidget(self.focused_widget)

        else:
            log.info(f"[{self.windowTitle()}] Restoring grid view from Camera {self.focused_cam_id}.")
            self.focused = False
            self.focused_cam_id = None

            if hasattr(self, "focused_widget"):
                self.centralWidget().layout().removeWidget(self.focused_widget)
                self.focused_widget.deleteLater()

            self.grid_widget.show()  # Show the original grid

    def refresh_widgets(self):
        for cam_id, widget in self.camera_widgets.items():
            stream_config = self.controller.stream_config.get_camera_config(cam_id) if self.controller else {}
            cam_name = stream_config.get("name", f"Camera {cam_id}")
            widget.title.setText(cam_name)

    def clear_layout(self, layout):
        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                item.widget().setParent(None)
            elif item.layout():
                self.clear_layout(item.layout())

# ========================== App Controller ==========================
class AppController:
    def __init__(self):
        self.config = ConfigManager()
        self.stream_config = CameraStreamConfigManager()

        self.camera_count = self.config.get_camera_count()
        if self.camera_count not in GRID_LAYOUTS:
            self.ask_for_camera_count()

        self.windows = []
        self.launch_windows()

    def ask_for_camera_count(self):
        dialog = CameraCountDialog()
        if dialog.exec_() == QDialog.Accepted:
            self.camera_count = dialog.get_selected_count()
            self.config.set_camera_count(self.camera_count)
        else:
            sys.exit()

    def open_camera_config(self):
        dialog = CameraConfigDialog(self.camera_count, self.stream_config)
        dialog.exec_()

    def refresh_configurations(self):
        log.info("Refreshing camera configurations...")
        self.stream_config.config = self.stream_config.load_config()

        for window in self.windows:
            window.refresh_widgets()
    
    def launch_windows(self):
        layouts = GRID_LAYOUTS[self.camera_count]
        all_camera_ids = list(range(1, self.camera_count + 1))
        current_index = 0 

        for window_id, rows, cols in layouts:
            cam_per_window =  rows * cols       
            cam_ids = all_camera_ids[current_index:current_index + cam_per_window]

            is_main = (window_id == 0)
            window = CameraWindow(
                title="Camera Viewer" if is_main else "Additional Window",
                camera_ids=cam_ids,
                rows=rows,
                cols=cols,
                config_manager=self.config,
                controller=self if is_main else None
            )
            self.windows.append(window)
            current_index += cam_per_window

    def change_camera_count(self):
        dialog = CameraCountDialog()
        if dialog.exec_() == QDialog.Accepted:
            self.camera_count = dialog.get_selected_count()
            self.config.set_camera_count(self.camera_count)

            # Close all existing windows and restart
            for win in self.windows:
                win.close()
            self.windows = []
            self.launch_windows()


# ========================== Main Entry ==========================
def main():
    app = QApplication(sys.argv)
    app.setStyleSheet("""
        QWidget { background-color: #232323; color: #e0e0e0; font-family: Arial; font-size: 13px; }
        QLabel { color: #f0f0f0; }
    """)
    controller = AppController()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
