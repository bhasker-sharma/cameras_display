import sys
import os
import json
from PyQt5 import QtWidgets, uic
from PyQt5.QtWidgets import QMainWindow, QApplication, QWidget, QDialog, QGridLayout
from PyQt5.QtCore import Qt,pyqtSignal
from centralisedlogging import Logger  # Your logging module

log = Logger.get_logger()

# ------------- System Config Manager
class SystemConfigManager:
    def __init__(self, path="config.json"):
        self.path = path
        self.config = {
            "camera_count": 8
        }
        self.load_config()

    def load_config(self):
        if not os.path.exists(self.path):
            log.warning("Config file not found. Using default config.")
            self.save_config()
        else:
            try:
                with open(self.path, "r") as file:
                    self.config = json.load(file)
                    log.info(f"Configuration loaded: {self.config}")
            except Exception as e:
                log.error(f"Error loading config: {e}")

    def save_config(self):
        try:
            with open(self.path, "w") as file:
                json.dump(self.config, file, indent=4)
                log.info("Configuration saved successfully.")
        except Exception as e:
            log.error(f"Error saving config: {e}")

    def get_camera_count(self):
        return self.config.get("camera_count", 8)

    def set_camera_count(self, count):
        self.config["camera_count"] = count
        log.debug(f"Camera count set to {count}")
        self.save_config()

# ------------- Camera Cell Widget
class CameraCellWidget(QWidget):
    double_clicked = pyqtSignal(int)

    def __init__(self, cam_number):
        super().__init__()
        self.cam_number = cam_number
        uic.loadUi("camera_cell.ui", self)

        log.debug(f"Creating camera cell for Camera {cam_number}")

        name_label = self.findChild(QtWidgets.QLabel, "nameLabel")
        if name_label:
            name_label.setText(f"Camera: {cam_number}")
        else:
            log.error("CameraCellWidget: 'nameLabel' not found")

        video_label = self.findChild(QtWidgets.QLabel, "videoLabel")
        if video_label:
            video_label.setStyleSheet("""
                background-image: url("D:/pyqttuyere_cam/assets/logo.png");
                background-repeat: no-repeat;
                background-position: center;
                background-color: rgba(0, 0, 0, 200);
            """)
        else:
            log.warning("CameraCellWidget: 'videoLabel' not found")

    def mouseDoubleClickEvent(self, event):
        log.debug(f"double-clicked on camera {self.cam_number}")
        self.double_clicked.emit(self.cam_number)

# ------------- System Config Dialog
class SystemConfigDialog(QDialog):
    def __init__(self, config_manager):
        super().__init__()
        uic.loadUi("system_config.ui", self)
        self.config_manager = config_manager

        self.combo_box = self.findChild(QtWidgets.QComboBox, "cameraCountcomboBox")
        self.buttonBox = self.findChild(QtWidgets.QDialogButtonBox, "buttonBox")

        self.combo_box.addItems([str(n) for n in range(8, 49, 4)])
        self.combo_box.setCurrentText(str(self.config_manager.get_camera_count()))

        self.buttonBox.accepted.connect(self.accept)
        self.buttonBox.rejected.connect(self.reject)

        log.info("SystemConfigDialog initialized.")

    def get_selected_camera_count(self):
        value = int(self.combo_box.currentText())
        log.debug(f"Selected camera count: {value}")
        return value

# ------------- Main Window
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        uic.loadUi("main_window.ui", self)
        log.info("MainWindow initialized.")

        self.config_manager = SystemConfigManager()
        self.additional_window = None
        self.additional_window_geometry = None
        self.fullscreen_widget = None
        self.fullscreen_mode = False

        cam_count = self.config_manager.get_camera_count()

        self.system_config_btn = self.findChild(QtWidgets.QPushButton, "systemConfigBtn")
        self.central_grid = self.findChild(QWidget, "centralGridWidget")

        if self.central_grid.layout() is None:
            self.grid_layout = QGridLayout()
            self.central_grid.setLayout(self.grid_layout)
        else:
            self.grid_layout = self.central_grid.layout()

        self.system_config_btn.clicked.connect(self.open_system_config)

        self.update_camera_cells(cam_count)

    def open_system_config(self):
        log.debug("Opening System Config Dialog")
        dialog = SystemConfigDialog(self.config_manager)
        if dialog.exec_() == QDialog.Accepted:
            selected_count = dialog.get_selected_camera_count()
            self.config_manager.set_camera_count(selected_count)
            self.update_camera_cells(selected_count)

    def update_camera_cells(self, cam_count):
        log.debug(f"Updating camera grid to {cam_count} cameras.")

        # Clear old widgets
        while self.grid_layout.count():
            child = self.grid_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        # Close additional window
        if self.additional_window:
            self.additional_window_geometry = self.additional_window.geometry()
            self.additional_window.close()
            self.additional_window = None
            log.info("Second window closed.")

        # Grid config
        if cam_count <= 16:
            cols = 4
            main_cams = cam_count
            second_cams = 0
        elif cam_count <= 24:
            cols = 6
            main_cams = cam_count
            second_cams = 0
        else:
            cols = 4
            main_cams = cam_count // 2
            second_cams = cam_count - main_cams

        # Load cameras into grid
        for i in range(main_cams):
            row = i // cols
            col = i % cols
            cam_widget = CameraCellWidget(i + 1)
            cam_widget.double_clicked.connect(self.handle_camera_double_click)
            self.grid_layout.addWidget(cam_widget, row, col)

        # Create second screen if needed
        if second_cams > 0:
            self.create_additional_window(main_cams + 1, cam_count, cols)

    def create_additional_window(self, start_cam, end_cam, cols):
        log.info(f"Creating second window for cameras {start_cam} to {end_cam}.")

        self.additional_window = QMainWindow()
        self.additional_window.setWindowTitle("Additional Cameras")
        self.additional_window.setStyleSheet(self.styleSheet())
        self.additional_window.resize(1024, 768)

        if self.additional_window_geometry:
            self.additional_window.setGeometry(self.additional_window_geometry)

        container = QWidget()
        grid_layout = QGridLayout(container)
        grid_layout.setContentsMargins(8, 8, 8, 8)
        grid_layout.setSpacing(6)

        for i, cam_number in enumerate(range(start_cam, end_cam + 1)):
            row = i // cols
            col = i % cols
            cam_widget = CameraCellWidget(cam_number)
            cam_widget.double_clicked.connect(self.handle_camera_double_click)
            grid_layout.addWidget(cam_widget, row, col)

        self.additional_window.setCentralWidget(container)
        self.additional_window.show()

    def handle_camera_double_click(self, cam_number):
        if self.fullscreen_mode:
            self.exit_fullscreen()
        else:
            self.show_camera_fullscreen(cam_number)

    def show_camera_fullscreen(self, cam_number):
        log.info(f"Showing camera {cam_number} in fullscreen mode.")

        if self.additional_window:
            self.additional_window.hide()

        self.fullscreen_widget = CameraCellWidget(cam_number)
        self.fullscreen_widget.double_clicked.connect(self.handle_camera_double_click)

        self.setCentralWidget(self.fullscreen_widget)
        self.showFullScreen()
        self.fullscreen_mode = True

    def exit_fullscreen(self):
        log.info("Exiting fullscreen mode.")

        self.showNormal()

        if self.fullscreen_widget:
            self.fullscreen_widget.deleteLater()
            self.fullscreen_widget = None

        # Reload original UI safely
        uic.loadUi("main_window.ui", self)
        log.debug("UI reloaded after exiting fullscreen.")

        # Reconnect UI elements
        self.system_config_btn = self.findChild(QtWidgets.QPushButton, "systemConfigBtn")
        self.central_grid = self.findChild(QWidget, "centralGridWidget")

        if self.central_grid.layout() is None:
            self.grid_layout = QGridLayout()
            self.central_grid.setLayout(self.grid_layout)
        else:
            self.grid_layout = self.central_grid.layout()

        self.system_config_btn.clicked.connect(self.open_system_config)

        cam_count = self.config_manager.get_camera_count()
        self.update_camera_cells(cam_count)

        if self.additional_window:
            self.additional_window.show()

        self.fullscreen_mode = False


# ------------- Run the Application
if __name__ == "__main__":
    app = QApplication(sys.argv)
    log.info("Application started.")
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())
