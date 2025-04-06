import sys
import json
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout,QHBoxLayout, QPushButton, QLabel,
    QGridLayout, QDialog, QSpinBox, QFormLayout, QMenuBar, QAction,QMessageBox,QComboBox,QLineEdit,QCheckBox
)
from PyQt5.QtCore import Qt
import cv2


# Base application functionality class
class Baseapp():
    def __init__(self):
        self.config_file = "config.json"
        self.load_config()
        self.save_config()
    
    def load_config(self):
        try:
            with open(self.config_file, "r") as file:
                self.config = json.load(file)
        except (FileNotFoundError, json.JSONDecodeError):
            self.config = {"camera_count": 24}
    
    def save_config(self):
        with open(self.config_file, "w") as file:
            json.dump(self.config, file)

# Camera configuration dialog
class ConfigDialog(QDialog):
    def __init__(self, base_app):
        super().__init__()
        self.base_app = base_app
        self.setWindowTitle("Configure Camera")
        self.setLayout(QFormLayout())

        # Dropdown to select camera number
        self.camera_number_dropdown = QComboBox()
        camera_count = self.base_app.config.get("camera_count", 24)
        self.camera_number_dropdown.addItems([str(i + 1) for i in range(camera_count)])
        self.layout().addRow("Camera Number:", self.camera_number_dropdown)

        # Input field for camera name
        self.camera_name_input = QLineEdit()
        self.layout().addRow("Camera Name:", self.camera_name_input)

        # Input field for RTSP link
        self.rtsp_link_input = QLineEdit()
        self.layout().addRow("RTSP Link:", self.rtsp_link_input)

        # Checkbox to enable/disable the camera
        self.enable_checkbox = QCheckBox("Enable Camera")
        self.layout().addWidget(self.enable_checkbox)

        # Test connection button
        test_button = QPushButton("Test Connection")
        test_button.clicked.connect(self.test_connection)
        self.layout().addWidget(test_button)

        # OK button to save configuration
        ok_button = QPushButton("OK")
        ok_button.clicked.connect(self.save_configuration)
        self.layout().addWidget(ok_button)

    def test_connection(self):
        # Test the RTSP connection
        rtsp_link = self.rtsp_link_input.text()
        if not rtsp_link:
            QMessageBox.warning(self, "Error", "Please enter an RTSP link.")
            return

        cap = cv2.VideoCapture(rtsp_link)
        if cap.isOpened():
            QMessageBox.information(self, "Success", "Connection successful!")
        else:
            QMessageBox.critical(self, "Error", "Failed to connect to the camera.")
        cap.release()

    def save_configuration(self):
        # Save the camera configuration to the JSON file
        camera_number = int(self.camera_number_dropdown.currentText())
        camera_name = self.camera_name_input.text()
        rtsp_link = self.rtsp_link_input.text()
        enabled = self.enable_checkbox.isChecked()

        if not camera_name or not rtsp_link:
            QMessageBox.warning(self, "Error", "Please fill in all fields.")
            return

        # Update the configuration in the JSON file
        if "cameras" not in self.base_app.config:
            self.base_app.config["cameras"] = {}

        self.base_app.config["cameras"][camera_number] = {
            "name": camera_name,
            "rtsp_link": rtsp_link,
            "enabled": enabled
        }
        self.base_app.save_config()
        QMessageBox.information(self, "Success", "Camera configuration saved successfully!")
        self.accept()

# Configuration dialog to set the number of cameras
class SystemConfigDialog(QDialog):
    def __init__(self, base_app, camera_window):
        super().__init__()
        self.base_app = base_app
        self.camera_window = camera_window
        self.setWindowTitle("System Configuration")
        self.setLayout(QFormLayout())

        # SpinBox to set the number of cameras
        self.camera_count_spinbox = QSpinBox()
        self.camera_count_spinbox.setMinimum(1)
        self.camera_count_spinbox.setMaximum(48)
        self.camera_count_spinbox.setValue(self.base_app.config.get("camera_count", 24))
        self.layout().addRow("Number of Cameras:", self.camera_count_spinbox)

        # Save button
        save_button = QPushButton("Save")
        save_button.clicked.connect(self.save_config)
        self.layout().addWidget(save_button)

    def save_config(self):
        # Update the configuration and save it
        self.base_app.config["camera_count"] = self.camera_count_spinbox.value()
        self.base_app.save_config()
        self.camera_window.update_grid()
        self.accept()


# Camera window class
class CameraWindow(QWidget):
    def __init__(self, base_app):
        super().__init__()
        self.base_app = base_app
        self.setWindowTitle("Camera Window")
        self.layout = QGridLayout()
        self.setLayout(self.layout)
        self.second_window = None
        self.full_screen_label = None  # To track the full-screen camera
        self.setStyleSheet("background-color: #2b2b2b; color: white;")  # Dark theme
        self.update_grid()

    def update_grid(self):
        # Clear the grid layout
        for i in reversed(range(self.layout.count())):
            widget = self.layout.itemAt(i).widget()
            if widget:
                widget.setParent(None)

        # Close the second window if it exists
        if self.second_window:
            self.second_window.close()
            self.second_window = None

        # Add camera labels to the grid
        camera_count = self.base_app.config.get("camera_count", 24)
        if camera_count <= 4:
            self.create_camera_grid(0, 1, 4)
        elif camera_count <= 20:
            self.create_camera_grid(0, 4, 5)
        elif camera_count <= 24:
            self.create_camera_grid(0, 4, 6)
        elif camera_count <= 28:
            self.create_camera_grid(0, 4, 7)
        elif camera_count <= 32:
            self.create_camera_grid(0, 4, 4)
            self.create_second_window(16, 4, 4)
        elif camera_count <= 40:
            self.create_camera_grid(0, 4, 5)
            self.create_second_window(20, 4, 5)
        elif camera_count <= 48:
            self.create_camera_grid(0, 4, 6)
            self.create_second_window(24, 4, 6)

    def create_camera_grid(self, start_index, rows, cols):
        camera_count = self.base_app.config.get("camera_count", 24)
        for i in range(start_index, min(start_index + rows * cols, camera_count)):
            cam_label = CameraLabel(i + 1, self)
            self.layout.addWidget(cam_label, (i - start_index) // cols, (i - start_index) % cols)

    def create_second_window(self, start_index, rows, cols):
        self.second_window = QWidget()
        self.second_window.setWindowTitle("Additional Cameras")
        layout = QGridLayout()
        self.second_window.setLayout(layout)
        self.second_window.setStyleSheet("background-color: #2b2b2b; color: white;")  # Dark theme

        camera_count = self.base_app.config.get("camera_count", 24)
        for i in range(start_index, min(start_index + rows * cols, camera_count)):
            cam_label = CameraLabel(i + 1, self)
            layout.addWidget(cam_label, (i - start_index) // cols, (i - start_index) % cols)

        self.second_window.show()

    def show_full_screen_camera(self, cam_number):
        if self.full_screen_label is None:
            self.full_screen_label = QLabel(f"Camera {cam_number} - Full Screen")
            self.full_screen_label.setStyleSheet("background-color: black; color: white; font-size: 24px;")
            self.full_screen_label.setAlignment(Qt.AlignCenter)
            self.full_screen_label.showFullScreen()
            self.full_screen_label.mouseDoubleClickEvent = self.exit_full_screen

    def exit_full_screen(self, event):
        if self.full_screen_label:
            self.full_screen_label.close()
            self.full_screen_label = None


# Camera label class
class CameraLabel(QLabel):
    def __init__(self, cam_number, parent_window):
        super().__init__(f"Camera {cam_number}")
        self.cam_number = cam_number
        self.parent_window = parent_window
        self.setStyleSheet("border: 1px solid white; padding: 10px; background-color: #3c3c3c; color: white;")
        self.setAlignment(Qt.AlignCenter)

    def mouseDoubleClickEvent(self, event):
        self.parent_window.show_full_screen_camera(self.cam_number)


# Main application window
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Camera Display")
        self.base_app = Baseapp()

        # Create the camera window
        self.camera_window = CameraWindow(self.base_app)
        self.setCentralWidget(self.camera_window)

        # Create the menu bar
        menu_bar = QMenuBar(self)
        menu_bar.setStyleSheet("background-color: #2b2b2b; color: white;")
        self.setMenuBar(menu_bar)

        # Add company name to the left
        company_name = QLabel("Company Name")
        company_name.setStyleSheet("color: white; font-size: 16px; padding-left: 10px;")
        company_name.setAlignment(Qt.AlignLeft)

        # Create a layout for the menu bar
        menu_layout = QHBoxLayout()
        menu_layout.addWidget(company_name)
        menu_layout.addStretch()

        # Add buttons to the right
        config_button = QPushButton("Config")
        recordings_button = QPushButton("Recordings")
        logs_button = QPushButton("Logs")
        system_config_button = QPushButton("System Config")
        system_config_button.clicked.connect(self.open_system_config_dialog)
        config_button.clicked.connect(self.open_config_dialog)

        for button in [config_button, recordings_button, logs_button, system_config_button]:
            button.setStyleSheet("background-color: #3c3c3c; color: white; border: none; padding: 5px 10px;")
            menu_layout.addWidget(button)

        # Set the custom layout to the menu bar
        menu_widget = QWidget()
        menu_widget.setLayout(menu_layout)
        menu_bar.setCornerWidget(menu_widget, Qt.TopLeftCorner)

        # Start in full-screen mode
        self.showMaximized()

    def open_system_config_dialog(self):
        dialog = SystemConfigDialog(self.base_app, self.camera_window)
        dialog.exec_()

    def open_config_dialog(self):
        dialog = ConfigDialog(self.base_app)
        dialog.exec_()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    main_window = MainWindow()
    main_window.show()
    sys.exit(app.exec_())