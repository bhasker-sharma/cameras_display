import sys
import json
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QStackedWidget, QGridLayout, QSizePolicy, QDialog, QSpinBox, QFormLayout
)
from PyQt5.QtCore import Qt

CONFIG_FILE = "config.json"

def load_config():
    try:
        with open(CONFIG_FILE, "r") as file:
            return json.load(file)
    except (FileNotFoundError, json.JSONDecodeError):
        return {"camera_count": 24}

def save_config(config):
    with open(CONFIG_FILE, "w") as file:
        json.dump(config, file)

class CameraLabel(QLabel):
    def __init__(self, cam_number, parent=None):
        super().__init__(parent)
        self.cam_number = cam_number
        self.parent = parent
        self.setText(f"Cam {cam_number}")
        self.setAlignment(Qt.AlignCenter)
        self.setStyleSheet("background-color: #222; border: 1px solid #444; padding: 20px;")
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

    def mouseDoubleClickEvent(self, event):
        self.parent.toggle_camera_view(self.cam_number)

class Navbar(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("background-color: #1E1E1E; padding: 10px;")
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 5, 10, 5)
        
        self.company_label = QLabel("Company Name")
        self.company_label.setStyleSheet("font-size: 18px; color: white;")
        layout.addWidget(self.company_label)
        
        layout.addStretch()
        
        self.config_button = QPushButton("System Configuration")
        self.recordings_button = QPushButton("View Recordings")
        self.health_button = QPushButton("System Health & Logs")
        
        for button in [self.config_button, self.recordings_button, self.health_button]:
            button.setStyleSheet("background-color: #333; color: white; padding: 10px; border-radius: 5px;")
            layout.addWidget(button)

        self.setLayout(layout)

class ConfigDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("System Configuration")
        self.setStyleSheet("background-color: #1E1E1E; color: white;")
        self.setGeometry(300, 200, 400, 200)
        
        layout = QFormLayout()
        
        self.camera_count = QSpinBox()
        self.camera_count.setRange(1, 48)
        self.camera_count.setValue(load_config()["camera_count"])
        layout.addRow("Number of Cameras:", self.camera_count)
        
        self.ok_button = QPushButton("OK")
        self.ok_button.setStyleSheet("background-color: #333; color: white; padding: 8px; border-radius: 5px;")
        self.ok_button.clicked.connect(self.accept)
        layout.addRow(self.ok_button)
        
        self.setLayout(layout)

class SecondWindow(QMainWindow):
    def __init__(self, start_index, rows, cols,parent):
        super().__init__()
        self.parent = parent
        self.setWindowTitle("Second Camera Window")
        self.setGeometry(800, 100, 1200, 800)
        self.setStyleSheet("background-color: #121212; color: white;")
        
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        layout = QVBoxLayout(self.central_widget)
        
        self.camera_grid = QWidget()
        self.grid_layout = QGridLayout(self.camera_grid)
        self.create_camera_grid(start_index, rows, cols)
        
        layout.addWidget(self.camera_grid)
    
    def create_camera_grid(self, start_index, rows, cols):
        for row in range(rows):
            for col in range(cols):
                cam_number = start_index + row * cols + col + 1
                if cam_number > 48:
                    return
                camera_label = CameraLabel(cam_number, self.parent)
                camera_label.setAlignment(Qt.AlignCenter)
                camera_label.setStyleSheet("background-color: #222; border: 1px solid #444; padding: 20px;")
                camera_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
                self.grid_layout.addWidget(camera_label, row, col)

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Camera Monitoring System")
        self.setGeometry(100, 100, 1200, 800)
        self.setStyleSheet("background-color: #121212; color: white;")
        self.expanded_camera_number = None
        
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        layout = QVBoxLayout(self.central_widget)
        
        self.navbar = Navbar(self)
        self.navbar.config_button.clicked.connect(self.open_config_dialog)
        
        self.stack = QStackedWidget()
        self.camera_grid = QWidget()
        self.grid_layout = QGridLayout(self.camera_grid)
        
        self.cam_count = load_config()["camera_count"]
        self.second_window = None
        self.update_camera_grid(self.cam_count)
        
        self.stack.addWidget(self.camera_grid)
        
        layout.addWidget(self.navbar)
        layout.addWidget(self.stack)
        self.showFullScreen()

    def create_camera_grid(self, start_index, rows, cols):
        for i in reversed(range(self.grid_layout.count())):
            widget = self.grid_layout.itemAt(i).widget()
            if widget is not None:
                widget.setParent(None)
        
        for row in range(rows):
            for col in range(cols):
                cam_number = start_index + row * cols + col + 1
                if cam_number > self.cam_count:
                    return
                camera_label = CameraLabel(cam_number, self)
                self.grid_layout.addWidget(camera_label, row, col)

    def toggle_camera_view(self, cam_number):
        if self.expanded_camera_number == cam_number:
            self.update_camera_grid(self.cam_count)
            self.showNormal()
            self.expanded_camera_number = None
        else:
            self.expand_camera(cam_number)

    def expand_camera(self, cam_number):
        for i in reversed(range(self.grid_layout.count())):
            widget = self.grid_layout.itemAt(i).widget()
            if widget is not None:
                widget.setParent(None)

        camera_label = CameraLabel(cam_number, self)
        camera_label.setStyleSheet("background-color: #222; border: 1px solid #444; padding: 50px; font-size: 24px;")
        self.grid_layout.addWidget(camera_label, 0, 0)

        self.showFullScreen()
        self.expanded_camera_number = cam_number

    def open_config_dialog(self):
        dialog = ConfigDialog(self)
        if dialog.exec_():
            cam_count = dialog.camera_count.value()
            save_config({"camera_count": cam_count})
            self.update_camera_grid(cam_count)

    def update_camera_grid(self, cam_count):
        self.cam_count = cam_count
        self.expanded_camera_number = None
        self.showNormal()

        # Only recreate the second window if the camera count changes
        if self.second_window and self.second_window.isVisible():
            self.second_window.close()
            self.second_window = None

        if cam_count <= 20:
            self.create_camera_grid(0, 4, 5)
        elif cam_count <= 24:
            self.create_camera_grid(0, 4, 6)
        elif cam_count <= 28:
            self.create_camera_grid(0, 4, 7)
        elif cam_count <= 32:
            self.create_camera_grid(0, 4, 4)
            self.create_second_window(16, 4, 4)
        elif cam_count <= 40:
            self.create_camera_grid(0, 4, 5)
            self.create_second_window(20, 4, 5)
        else:
            self.create_camera_grid(0, 4, 6)
            if not self.second_window:
                self.create_second_window(24, 4, 6)

    def create_second_window(self, start_index, rows, cols):
        if self.second_window:
            self.second_window.close()
            self.second_window = None
        self.second_window = SecondWindow(start_index, rows, cols,self)
        self.second_window.show()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())
