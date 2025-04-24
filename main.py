import sys
import os
import json
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QDialog, QComboBox, QDialogButtonBox, QGridLayout, QSizePolicy
)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QPixmap, QIcon
from centralisedlogging import log


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
    48: [(0, 4, 6), (1, 4, 6)],  # 24 + 24
}

VALID_CAMERA_COUNTS = list(GRID_LAYOUTS.keys())


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
        self.name = f"{name} {cam_id}"
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
            title_label = QLabel("Camera Viewer")
            title_label.setStyleSheet("color: #f0f0f0; font-size: 18px; font-weight: bold;")
            title_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

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
            nav.addWidget(title_label)
            nav.addStretch()
            nav.addWidget(change_btn)
            layout.addLayout(nav)

        self.grid_widget = QWidget()
        self.grid_layout = QGridLayout()
        self.grid_widget.setLayout(self.grid_layout)
        layout.addWidget(self.grid_widget)  # Add grid widget to main layout

        self.camera_widgets = {}

        for idx, cam_id in enumerate(camera_ids):
            r, c = divmod(idx, cols)
            widget = CameraWidget(cam_id)
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

            # Create isolated camera view
            self.focused_widget = CameraWidget(cam_id)
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
