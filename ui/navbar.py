from PyQt5.QtWidgets import QWidget, QHBoxLayout, QLabel, QPushButton, QPushButton, QDialog, QSpinBox, QFormLayout
from PyQt5.QtCore import Qt
import json

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

class Navbar(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("background-color: #1E1E1E; padding: 10px;")
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 5, 10, 5)
        
        # Company Name
        self.company_label = QLabel("Company Name")
        self.company_label.setStyleSheet("font-size: 18px; color: white;")
        layout.addWidget(self.company_label)
        
        # Spacer
        layout.addStretch()
        
        # Navigation Buttons
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
        self.camera_count.setValue(load_config()["camera_count"])  # Load last saved config
        layout.addRow("Number of Cameras:", self.camera_count)
        
        self.ok_button = QPushButton("OK")
        self.ok_button.setStyleSheet("background-color: #333; color: white; padding: 8px; border-radius: 5px;")
        self.ok_button.clicked.connect(self.accept)
        layout.addRow(self.ok_button)
        
        self.setLayout(layout)
