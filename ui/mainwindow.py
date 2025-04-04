import sys,json
from PyQt5.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QLabel, QStackedWidget, QGridLayout, QSizePolicy)
from PyQt5.QtCore import Qt
from ui.navbar import Navbar, ConfigDialog
from ui.navbar import load_config, save_config

class SecondWindow(QMainWindow):
    def __init__(self, start_index, rows, cols):
        super().__init__()
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
                camera_label = QLabel(f"Cam {cam_number}")
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
        
        # Central Widget
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        layout = QVBoxLayout(self.central_widget)
        
        # Navigation Bar
        self.navbar = Navbar(self)
        self.navbar.config_button.clicked.connect(self.open_config_dialog)
        
        # Main View
        self.stack = QStackedWidget()
        self.camera_grid = QWidget()
        self.grid_layout = QGridLayout(self.camera_grid)
        
        self.cam_count = load_config()["camera_count"]
        self.second_window = None
        self.update_camera_grid(self.cam_count)  # Load last saved camera grid
        
        self.stack.addWidget(self.camera_grid)
        
        layout.addWidget(self.navbar)
        layout.addWidget(self.stack)
    
    def create_camera_grid(self, start_index, rows, cols):
        # Clear existing layout
        for i in reversed(range(self.grid_layout.count())):
            widget = self.grid_layout.itemAt(i).widget()
            if widget is not None:
                widget.setParent(None)
        
        # Create grid layout
        for row in range(rows):
            for col in range(cols):
                cam_number = start_index + row * cols + col + 1
                if cam_number > self.cam_count:
                    return
                camera_label = QLabel(f"Cam {cam_number}")
                camera_label.setAlignment(Qt.AlignCenter)
                camera_label.setStyleSheet("background-color: #222; border: 1px solid #444; padding: 20px;")
                camera_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
                self.grid_layout.addWidget(camera_label, row, col)
    
    def open_config_dialog(self):
        dialog = ConfigDialog(self)
        if dialog.exec_():
            cam_count = dialog.camera_count.value()
            save_config({"camera_count": cam_count})
            self.update_camera_grid(cam_count)
    
    def update_camera_grid(self, cam_count):
        self.cam_count = cam_count
        if self.second_window:
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
            self.create_second_window(24, 4, 6)
    

    def create_second_window(self, start_index, rows, cols):
        self.second_window = SecondWindow(start_index, rows, cols)
        self.second_window.show()