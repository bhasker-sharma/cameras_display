#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Camera Monitoring System - Main Application
"""

import sys
import json
import os
import logging
import time
import threading
from datetime import datetime
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QGridLayout, QDialog, QSpinBox, QFormLayout, QMessageBox, QComboBox,
    QLineEdit, QCheckBox, QFrame, QSizePolicy
)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QObject, QSize
from PyQt5.QtGui import QFont, QImage, QPixmap, QIcon, QColor, QPainter, QBrush
import cv2
import numpy as np
import base64

# Logger class with singleton pattern
class Logger:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(Logger, cls).__new__(cls)
            cls._instance.logger = logging.getLogger("CameraApp")
            cls._instance.logger.setLevel(logging.DEBUG)

            if not cls._instance.logger.handlers:
                formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

                ch = logging.StreamHandler()
                ch.setFormatter(formatter)
                cls._instance.logger.addHandler(ch)

                if not os.path.exists("logs"):
                    os.makedirs("logs")
                    
                fh = logging.FileHandler("logs/camera_app.log")
                fh.setFormatter(formatter)
                cls._instance.logger.addHandler(fh)

                cls._instance.logger.info("Logger initialized.")
        
        return cls._instance.logger

# Camera Stream class to handle RTSP connections
class CameraStream(QObject):
    frame_ready = pyqtSignal(np.ndarray)
    connection_changed = pyqtSignal(bool)

    def __init__(self, rtsp_link):
        super().__init__()
        self.logger = Logger()
        self.rtsp_link = rtsp_link
        self.capture = None
        self.is_running = False
        self.connected = False
        self.thread = None
        self.frame_interval = 0.03  # ~30 fps
        self.logger.info(f"CameraStream initialized for {self.rtsp_link}")

    def start(self):
        if self.is_running:
            self.logger.warning("Camera stream is already running.")
            return
        self.is_running = True
        self.thread = threading.Thread(target=self.run)
        self.thread.daemon = True
        self.thread.start()
        self.logger.info(f"Started camera stream thread for {self.rtsp_link}")

    def stop(self):
        self.logger.debug(f"Stopping stream for {self.rtsp_link}")
        self.is_running = False
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=1.0)
        if self.capture:
            self.capture.release()
            self.capture = None
        self.logger.info(f"Stopped camera stream for {self.rtsp_link}")

    def run(self):
        self.logger.debug(f"Entering run loop for {self.rtsp_link}")
        retry_count = 0
        max_retries = 3
        reconnect_delay = 2

        while self.is_running:
            try:
                # Initialize capture if needed
                if self.capture is None:
                    self.logger.debug(f"Creating new capture for {self.rtsp_link}")
                    self.capture = cv2.VideoCapture(self.rtsp_link)
                    self.capture.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                    
                    if not self.capture.isOpened():
                        self.logger.error(f"Failed to open capture for {self.rtsp_link}")
                        raise Exception("Failed to open capture")

                # Read frame
                ret, frame = self.capture.read()
                if not ret or frame is None:
                    self.logger.warning(f"Failed to read frame from {self.rtsp_link}")
                    raise Exception("Failed to read frame")

                # Update connection status if needed
                if not self.connected:
                    self.logger.info(f"Successfully connected to {self.rtsp_link}")
                    self.connected = True
                    self.connection_changed.emit(True)
                    retry_count = 0

                # Emit the frame
                self.frame_ready.emit(frame)
                
                # Control frame rate
                time.sleep(self.frame_interval)

            except Exception as e:
                self.logger.error(f"Stream error for {self.rtsp_link}: {str(e)}")
                
                # Handle connection loss
                if self.connected:
                    self.connected = False
                    self.connection_changed.emit(False)

                # Clean up capture
                if self.capture:
                    self.capture.release()
                    self.capture = None

                # Handle retries
                retry_count += 1
                if retry_count >= max_retries:
                    self.logger.error(f"Max retries ({max_retries}) reached for {self.rtsp_link}")
                    time.sleep(reconnect_delay * 2)
                    retry_count = 0
                else:
                    self.logger.info(f"Retrying in {reconnect_delay}s (attempt {retry_count}/{max_retries})")
                    time.sleep(reconnect_delay)

        self.logger.debug(f"Exiting run loop for {self.rtsp_link}")
        if self.connected:
            self.connected = False
            self.connection_changed.emit(False)

    def test_connection(self):
        try:
            cap = cv2.VideoCapture(self.rtsp_link)
            if not cap.isOpened():
                return False
            ret, frame = cap.read()
            cap.release()
            return bool(ret)
        except Exception as e:
            self.logger.error(f"Error testing connection: {e}") 
            return False

# Base App class to handle configuration and resources
class BaseApp:
    def __init__(self):
        self.config_file = "config.json"
        self.logger = Logger()
        self.load_config()
        self.logo_pixmap = self.create_logo()
        self.transparent_logo = self.create_transparent_logo()
    
    def load_config(self):
        try:
            with open(self.config_file, "r") as file:
                self.config = json.load(file)
                self.logger.info(f"Configuration loaded from {self.config_file}")
        except (FileNotFoundError, json.JSONDecodeError):
            self.config = {"camera_count": 24, "cameras": {}}
            self.save_config()
    
    def save_config(self):
        try:
            with open(self.config_file, "w") as file:
                json.dump(self.config, file, indent=4)
                self.logger.info(f"Configuration saved to {self.config_file}")
            return True
        except Exception as e:
            self.logger.error(f"Error saving configuration: {e}")
            return False
    
    def get_camera_config(self, camera_number):
        return self.config.get("cameras", {}).get(str(camera_number), None)
    
    def create_logo(self):
        """Create a blue camera logo as QPixmap"""
        width, height = 160, 120
        pixmap = QPixmap(width, height)
        pixmap.fill(Qt.transparent)
        
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # Background blue rectangle
        painter.setBrush(QBrush(QColor(0, 102, 204)))  # Blue color
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(10, 10, width-20, height-20, 10, 10)
        
        # Camera lens
        painter.setBrush(QBrush(QColor(255, 255, 255)))  # White color
        painter.drawEllipse(width//2-20, height//2-20, 40, 40)
        
        # Camera lens hole
        painter.setBrush(QBrush(QColor(0, 102, 204)))  # Blue color
        painter.drawEllipse(width//2-10, height//2-10, 20, 20)
        
        # Draw "TIPL" text
        painter.setPen(QColor(255, 255, 255))
        font = QFont("Arial", 10, QFont.Bold)
        painter.setFont(font)
        painter.drawText(width//2-15, 20, "TIPL")
        
        painter.end()
        return pixmap
    
    def create_transparent_logo(self):
        """Create a transparent version of the logo"""
        pixmap = QPixmap(self.logo_pixmap.size())
        pixmap.fill(Qt.transparent)
        
        painter = QPainter(pixmap)
        painter.setOpacity(0.3)  # 30% opacity
        painter.drawPixmap(0, 0, self.logo_pixmap)
        painter.end()
        
        return pixmap

# Camera configuration dialog
class ConfigDialog(QDialog):
    def __init__(self, base_app):
        super().__init__()
        self.base_app = base_app
        self.logger = Logger()
        self.setWindowTitle("Configure Camera")
        self.resize(500, 300)
        
        # Apply dark theme styling
        self.setStyleSheet("""
            QDialog { 
                background-color: #2D2D30; 
                color: #FFFFFF;
            }
            QLabel { 
                color: #FFFFFF; 
                font-size: 12px;
            }
            QLineEdit, QComboBox, QSpinBox { 
                background-color: #3E3E42; 
                color: #FFFFFF; 
                border: 1px solid #555555; 
                padding: 5px; 
                border-radius: 3px;
            }
            QPushButton { 
                background-color: #0E639C; 
                color: #FFFFFF; 
                border: none; 
                padding: 8px 16px; 
                border-radius: 3px;
            }
            QPushButton:hover { 
                background-color: #1177BB; 
            }
            QPushButton:pressed { 
                background-color: #0D5A8C; 
            }
            QCheckBox { 
                color: #FFFFFF; 
            }
        """)
        
        # Create the layout
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(15)
        
        # Create the form layout
        form_layout = QFormLayout()
        form_layout.setSpacing(10)
        
        # Dropdown to select camera number
        self.camera_number_dropdown = QComboBox()
        camera_count = self.base_app.config.get("camera_count", 24)
        self.camera_number_dropdown.addItems([str(i + 1) for i in range(camera_count)])
        form_layout.addRow("Camera Number:", self.camera_number_dropdown)

        # Input field for camera name
        self.camera_name_input = QLineEdit()
        form_layout.addRow("Camera Name:", self.camera_name_input)

        # Input field for RTSP link
        self.rtsp_link_input = QLineEdit()
        self.rtsp_link_input.setPlaceholderText("rtsp://username:password@camera_ip:port/stream")
        form_layout.addRow("RTSP Link:", self.rtsp_link_input)

        # Checkbox to enable/disable the camera
        self.enable_checkbox = QCheckBox("Enable Camera")
        form_layout.addRow("", self.enable_checkbox)

        main_layout.addLayout(form_layout)
        
        # Create the buttons layout
        buttons_layout = QHBoxLayout()
        
        # Test connection button
        test_button = QPushButton("Test Connection")
        test_button.clicked.connect(self.test_connection)
        buttons_layout.addWidget(test_button)

        # Space between buttons
        buttons_layout.addStretch()
        
        # Cancel button
        cancel_button = QPushButton("Cancel")
        cancel_button.clicked.connect(self.reject)
        buttons_layout.addWidget(cancel_button)      

        # Save button
        save_button = QPushButton("Save Configuration")
        save_button.clicked.connect(self.save_configuration)
        buttons_layout.addWidget(save_button)

        main_layout.addLayout(buttons_layout)
        self.camera_number_dropdown.currentIndexChanged.connect(self.load_camera_config)
        self.load_camera_config()

    def load_camera_config(self):
        try:
            camera_number = int(self.camera_number_dropdown.currentText())
            camera_config = self.base_app.get_camera_config(camera_number)

            if camera_config:
                self.camera_name_input.setText(camera_config.get("name", ""))
                self.rtsp_link_input.setText(camera_config.get("rtsp_link", ""))
                self.enable_checkbox.setChecked(camera_config.get("enabled", False))
            else:
                self.camera_name_input.setText(f"Camera {camera_number}")
                self.rtsp_link_input.clear()
                self.enable_checkbox.setChecked(False)
        except Exception as e:
            self.logger.error(f"Error loading camera configuration: {str(e)}")

    def test_connection(self):
        rtsp_link = self.rtsp_link_input.text()
        if not rtsp_link:
            QMessageBox.warning(self, "Error", "Please enter an RTSP link.")
            return

        # Create testing message dialog
        msg_box = QMessageBox(self)
        msg_box.setWindowTitle("Testing Connection")
        msg_box.setText("Testing connection, please wait...")
        msg_box.setStandardButtons(QMessageBox.NoButton)
        msg_box.show()
        QApplication.processEvents()

        # Test the connection
        stream = CameraStream(rtsp_link)
        result = stream.test_connection()

        # Close the dialog and show the result
        msg_box.close()

        if result:
            QMessageBox.information(self, "Connection Test", "Connection successful!")
        else:
            QMessageBox.warning(self, "Connection Test", "Failed to connect to the camera.")

    def save_configuration(self):
        try:
            camera_number = self.camera_number_dropdown.currentText()
            camera_name = self.camera_name_input.text()
            rtsp_link = self.rtsp_link_input.text()
            enabled = self.enable_checkbox.isChecked()

            # Basic validation
            if not camera_name:
                QMessageBox.warning(self, "Error", "Please enter a camera name.")
                return

            if enabled and not rtsp_link:
                QMessageBox.warning(self, "Error", "Please enter an RTSP link for enabled cameras.")
                return

            # Update configuration
            if "cameras" not in self.base_app.config:
                self.base_app.config["cameras"] = {}

            self.base_app.config["cameras"][camera_number] = {
                "name": camera_name,
                "rtsp_link": rtsp_link,
                "enabled": enabled
            }

            # Save configuration to file
            if self.base_app.save_config():
                QMessageBox.information(self, "Success", "Camera configuration saved successfully!")
                self.accept()
            else:
                QMessageBox.critical(self, "Error", "Failed to save configuration.")

        except Exception as e:
            self.logger.error(f"Error saving camera configuration: {str(e)}")
            QMessageBox.critical(self, "Error", f"An error occurred: {str(e)}")

# System configuration dialog
class SystemConfigDialog(QDialog):
    def __init__(self, base_app, parent=None):
        super().__init__(parent)
        self.base_app = base_app
        self.logger = Logger()
        self.setWindowTitle("System Configuration")
        self.resize(500, 300)
        
        # Apply dark theme styling
        self.setStyleSheet("""
            QDialog { 
                background-color: #2D2D30; 
                color: #FFFFFF;
            }
            QLabel { 
                color: #FFFFFF; 
                font-size: 12px;
            }
            QLineEdit, QComboBox, QSpinBox { 
                background-color: #3E3E42; 
                color: #FFFFFF; 
                border: 1px solid #555555; 
                padding: 5px; 
                border-radius: 3px;
            }
            QPushButton { 
                background-color: #0E639C; 
                color: #FFFFFF; 
                border: none; 
                padding: 8px 16px; 
                border-radius: 3px;
            }
            QPushButton:hover { 
                background-color: #1177BB; 
            }
            QPushButton:pressed { 
                background-color: #0D5A8C; 
            }
        """)
        
        # Main layout
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(15)
        
        # Form layout
        form_layout = QFormLayout()
        form_layout.setSpacing(10)
        
        # Camera count spinner
        self.camera_count_spinner = QSpinBox()
        self.camera_count_spinner.setMinimum(1)
        self.camera_count_spinner.setMaximum(48)
        self.camera_count_spinner.setValue(self.base_app.config.get("camera_count", 24))
        form_layout.addRow("Number of Cameras:", self.camera_count_spinner)
        
        main_layout.addLayout(form_layout)
        
        # Add information about window layouts
        info_label = QLabel(
            "The system will automatically configure the windows based on camera count:\n\n"
            "• For 1-4 cameras: Single row grid\n"
            "• For 5-20 cameras: 4×5 grid in one window\n"
            "• For 21-24 cameras: 4×6 grid in one window\n"
            "• For 25-28 cameras: 4×7 grid in one window\n"
            "• For 29-32 cameras: Two 4×4 grids (two windows)\n"
            "• For 33-40 cameras: Two 4×5 grids (two windows)\n"
            "• For 41-48 cameras: Two 4×6 grids (two windows)\n"
        )
        info_label.setWordWrap(True)
        info_label.setStyleSheet("background-color: #3E3E42; padding: 10px; border-radius: 5px;")
        main_layout.addWidget(info_label)
        
        main_layout.addStretch()
        
        # Buttons layout
        buttons_layout = QHBoxLayout()
        buttons_layout.addStretch()
        
        # Cancel button
        cancel_button = QPushButton("Cancel")
        cancel_button.clicked.connect(self.reject)
        buttons_layout.addWidget(cancel_button)
        
        # Save button
        save_button = QPushButton("Save")
        save_button.clicked.connect(self.save_system_config)
        buttons_layout.addWidget(save_button)
        
        main_layout.addLayout(buttons_layout)

    def save_system_config(self):
        try:
            # Update camera count
            self.base_app.config["camera_count"] = self.camera_count_spinner.value()
            
            # Save configuration
            if self.base_app.save_config():
                QMessageBox.information(self, "Success", "System configuration saved successfully!")
                self.accept()
            else:
                QMessageBox.critical(self, "Error", "Failed to save configuration.")
                
        except Exception as e:
            self.logger.error(f"Error saving system configuration: {str(e)}")
            QMessageBox.critical(self, "Error", f"An error occurred: {str(e)}")

# Individual camera display widget
class CameraWidget(QWidget):
    double_clicked = pyqtSignal(int)  # Signal for double-click with camera ID
    
    def __init__(self, camera_number, base_app, parent=None):
        super().__init__(parent)
        self.camera_number = camera_number
        self.base_app = base_app
        self.logger = Logger()
        self.stream = None
        self.connected = False
        
        # Set size policy to expand in both directions
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setMinimumSize(160, 120)
        
        # Initialize camera config
        self.camera_config = self.base_app.get_camera_config(camera_number)
        
        # Create layout
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(2, 2, 2, 2)
        self.layout.setSpacing(2)
        
        # Status strip (colored bar)
        self.status_strip = QFrame()
        self.status_strip.setFixedHeight(12)  # Height of the status bar
        self.layout.addWidget(self.status_strip)
        
        # Camera display area
        self.display_area = QLabel()
        self.display_area.setAlignment(Qt.AlignCenter)
        self.display_area.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        
        # Set transparent logo as background for non-configured cameras
        if not self.camera_config or not self.camera_config.get("enabled", False):
            self.display_area.setPixmap(self.base_app.transparent_logo.scaled(
                self.display_area.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))
        
        self.layout.addWidget(self.display_area, 1)  # Add with stretch factor of 1
        
        # Camera name label - small strip at bottom
        self.name_label = QLabel(self.get_display_name())
        self.name_label.setAlignment(Qt.AlignCenter)
        self.name_label.setStyleSheet("color: white; background-color: #1E1E1E; font-weight: bold; font-size: 10px; padding: 2px;")
        self.name_label.setFixedHeight(20)  # Fixed height for name label
        self.layout.addWidget(self.name_label)
        
        # Style the widget
        self.setStyleSheet("""
            QWidget {
                border: 1px solid #555555;
                background-color: #000000;
            }
        """)
        
        # Update status display
        self.update_status_display()
        
        # Start camera if enabled
        if self.camera_config and self.camera_config.get("enabled", False):
            self.start_camera()
    
    def get_display_name(self):
        if self.camera_config and self.camera_config.get("name"):
            return self.camera_config.get("name")
        return f"Camera {self.camera_number}"
    
    def update_status_display(self):
        # Update the status strip color and display message
        if not self.camera_config or not self.camera_config.get("rtsp_link"):
            # Blue for not configured
            self.status_strip.setStyleSheet("background-color: #0066cc;")
            self.display_area.setText("Not Configured")
        elif not self.camera_config.get("enabled", False):
            # Orange for disabled
            self.status_strip.setStyleSheet("background-color: #FFA500;")
            self.display_area.setText("Disabled")
        elif not self.connected:
            # Red for no signal
            self.status_strip.setStyleSheet("background-color: #FF0000;")
            self.display_area.setText("No Signal")
        else:
            # Green for connected
            self.status_strip.setStyleSheet("background-color: #00FF00;")
    
    def start_camera(self):
        # Start the camera stream
        if not self.camera_config or not self.camera_config.get("enabled", False):
            return
        
        rtsp_link = self.camera_config.get("rtsp_link", "")
        if not rtsp_link:
            self.logger.warning(f"No RTSP link for camera {self.camera_number}")
            return
        
        self.logger.info(f"Starting camera {self.camera_number} with link {rtsp_link}")
        
        try:
            self.stream = CameraStream(rtsp_link)
            self.stream.frame_ready.connect(self.update_frame)
            self.stream.connection_changed.connect(self.connection_changed)
            self.stream.start()
        except Exception as e:
            self.logger.error(f"Error starting camera {self.camera_number}: {str(e)}")
    
    def stop_camera(self):
        # Stop the camera stream
        if self.stream:
            try:
                self.stream.frame_ready.disconnect(self.update_frame)
                self.stream.connection_changed.disconnect(self.connection_changed)
                self.stream.stop()
                self.stream = None
                self.connected = False
                self.update_status_display()
            except Exception as e:
                self.logger.error(f"Error stopping camera {self.camera_number}: {str(e)}")
    
    def update_frame(self, frame):
        # Update the camera display with a new frame
        try:
            # Convert to QImage then QPixmap
            h, w, ch = frame.shape
            bytes_per_line = ch * w
            convert_to_qt_format = QImage(frame.data, w, h, bytes_per_line, QImage.Format_RGB888).rgbSwapped()
            pixmap = QPixmap.fromImage(convert_to_qt_format)
            
            # Scale to fit while maintaining aspect ratio
            scaled_pixmap = pixmap.scaled(
                self.display_area.width(), 
                self.display_area.height(),
                Qt.KeepAspectRatio, 
                Qt.SmoothTransformation
            )
            
            # Set the pixmap
            self.display_area.setPixmap(scaled_pixmap)
        except Exception as e:
            self.logger.error(f"Error updating frame for camera {self.camera_number}: {str(e)}")
    
    def connection_changed(self, connected):
        # Handle connection status changes
        self.connected = connected
        self.update_status_display()
        
        if connected:
            self.logger.info(f"Camera {self.camera_number} connected")
        else:
            self.logger.warning(f"Camera {self.camera_number} disconnected")
    
    def resizeEvent(self, event):
        # Handle resize events
        super().resizeEvent(event)
        
        # If no stream active and not showing a frame, make sure logo is properly sized
        if (not self.stream or not self.connected) and self.base_app.transparent_logo:
            self.display_area.setPixmap(self.base_app.transparent_logo.scaled(
                self.display_area.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))
    
    def mouseDoubleClickEvent(self, event):
        # Handle double-click events
        self.double_clicked.emit(self.camera_number)

# Main window
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.logger = Logger()
        self.logger.info("Starting Camera Monitoring System")
        
        # Initialize base app
        self.base_app = BaseApp()
        
        # Set window properties
        self.setWindowTitle("Camera Monitoring System")
        self.resize(1280, 800)
        
        # Set black background for the whole app
        self.setStyleSheet("background-color: #000000;")
        
        # Create central widget
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        
        # Main vertical layout
        self.main_layout = QVBoxLayout(self.central_widget)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)
        
        # Create menu bar
        self.create_menu_bar()
        
        # Container for either grid view or fullscreen view
        self.content_widget = QWidget()
        self.content_layout = QVBoxLayout(self.content_widget)
        self.content_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.addWidget(self.content_widget)
        
        # Create grid layout for cameras
        self.grid_layout = QGridLayout()
        self.grid_layout.setSpacing(8)
        self.grid_layout.setContentsMargins(8, 8, 8, 8)
        self.content_layout.addLayout(self.grid_layout)
        
        # Camera widgets dictionary
        self.camera_widgets = {}
        
        # Second window
        self.second_window = None
        
        # Fullscreen mode
        self.fullscreen_widget = None
        self.is_fullscreen = False
        
        # Update camera grid
        self.update_camera_grid()
    
    def create_menu_bar(self):
        # Create custom menu bar
        menu_bar = QWidget()
        menu_bar.setFixedHeight(50)
        menu_bar.setStyleSheet("""
            QWidget {
                background-color: #1E1E1E;
                border-bottom: 1px solid #555555;
            }
            QPushButton {
                background-color: #0066cc;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #0077ee;
            }
            QLabel {
                color: white;
                font-size: 16px;
                font-weight: bold;
            }
        """)
        
        # Layout for menu bar
        menu_layout = QHBoxLayout(menu_bar)
        menu_layout.setContentsMargins(10, 5, 10, 5)
        
        # Company name
        company_label = QLabel("TIPL Toshniwal Industries Pvt Ltd")
        menu_layout.addWidget(company_label)
        
        # Add spacer
        menu_layout.addStretch()
        
        # Config button
        config_button = QPushButton("Camera Config")
        config_button.clicked.connect(self.open_camera_config)
        menu_layout.addWidget(config_button)
        
        # System config button
        system_button = QPushButton("System Config")
        system_button.clicked.connect(self.open_system_config)
        menu_layout.addWidget(system_button)
        
        # Add menu bar to main layout
        self.main_layout.addWidget(menu_bar)
    
    def update_camera_grid(self):
        # Clear existing cameras
        self.clear_cameras()
        
        # Close second window if it exists
        if self.second_window:
            self.second_window.close()
            self.second_window = None
        
        # Get camera count
        camera_count = self.base_app.config.get("camera_count", 24)
        
        # Configure grid based on camera count
        if camera_count <= 4:
            # Single row for 1-4 cameras
            self.create_camera_grid(1, 4, 0, camera_count)
        elif camera_count <= 20:
            # 4x5 grid for 5-20 cameras
            self.create_camera_grid(4, 5, 0, camera_count)
        elif camera_count <= 24:
            # 4x6 grid for 21-24 cameras
            self.create_camera_grid(4, 6, 0, camera_count)
        elif camera_count <= 28:
            # 4x7 grid for 25-28 cameras
            self.create_camera_grid(4, 7, 0, camera_count)
        elif camera_count <= 32:
            # Two 4x4 grids for 29-32 cameras
            self.create_camera_grid(4, 4, 0, 16)
            self.create_second_window(4, 4, 16, camera_count - 16)
        elif camera_count <= 40:
            # Two 4x5 grids for 33-40 cameras
            self.create_camera_grid(4, 5, 0, 20)
            self.create_second_window(4, 5, 20, camera_count - 20)
        elif camera_count <= 48:
            # Two 4x6 grids for 41-48 cameras
            self.create_camera_grid(4, 6, 0, 24)
            self.create_second_window(4, 6, 24, camera_count - 24)
    
    def clear_cameras(self):
        # Stop and remove all cameras
        for camera in self.camera_widgets.values():
            camera.stop_camera()
        
        # Clear the grid layout
        while self.grid_layout.count():
            item = self.grid_layout.takeAt(0)
            if item.widget():
                item.widget().setParent(None)
        
        self.camera_widgets.clear()
    
    def create_camera_grid(self, rows, cols, start_index, count):
        # Create a grid of cameras
        self.logger.info(f"Creating grid: {rows}x{cols}, start={start_index}, count={count}")
        
        for i in range(min(count, rows * cols)):
            camera_number = start_index + i + 1
            row = i // cols
            col = i % cols
            
            # Create camera widget
            camera_widget = CameraWidget(camera_number, self.base_app)
            camera_widget.double_clicked.connect(self.handle_camera_double_click)
            
            # Add to grid and dictionary
            self.grid_layout.addWidget(camera_widget, row, col)
            self.camera_widgets[camera_number] = camera_widget
    
    def create_second_window(self, rows, cols, start_index, count):
        # Create a second window for additional cameras
        self.logger.info(f"Creating second window: {rows}x{cols}, start={start_index}, count={count}")
        
        self.second_window = QMainWindow()
        self.second_window.setWindowTitle("Additional Cameras")
        self.second_window.resize(1024, 768)
        self.second_window.setStyleSheet("background-color: #000000;")
        
        # Create central widget and layout
        central_widget = QWidget()
        self.second_window.setCentralWidget(central_widget)
        
        # Create grid layout
        grid_layout = QGridLayout(central_widget)
        grid_layout.setSpacing(8)
        grid_layout.setContentsMargins(8, 8, 8, 8)
        
        # Add cameras to grid
        for i in range(min(count, rows * cols)):
            camera_number = start_index + i + 1
            row = i // cols
            col = i % cols
            
            # Create camera widget
            camera_widget = CameraWidget(camera_number, self.base_app)
            camera_widget.double_clicked.connect(self.handle_camera_double_click)
            
            # Add to grid and dictionary
            grid_layout.addWidget(camera_widget, row, col)
            self.camera_widgets[camera_number] = camera_widget
        
        # Show the window
        self.second_window.show()
    
    def handle_camera_double_click(self, camera_number):
        # Toggle fullscreen for a camera
        if self.is_fullscreen:
            self.exit_fullscreen()
        else:
            self.show_fullscreen(camera_number)
    
    def show_fullscreen(self, camera_number):
        # Show a camera in fullscreen
        self.logger.info(f"Showing camera {camera_number} in fullscreen")
        
        # Hide the grid layout
        for i in range(self.grid_layout.count()):
            item = self.grid_layout.itemAt(i)
            if item.widget():
                item.widget().hide()
        
        # Create fullscreen widget
        self.fullscreen_widget = CameraWidget(camera_number, self.base_app)
        self.fullscreen_widget.double_clicked.connect(self.exit_fullscreen)
        
        # Add to content layout
        self.content_layout.addWidget(self.fullscreen_widget)
        
        self.is_fullscreen = True
    
    def exit_fullscreen(self):
        # Exit fullscreen mode
        if self.fullscreen_widget:
            self.fullscreen_widget.stop_camera()
            self.content_layout.removeWidget(self.fullscreen_widget)
            self.fullscreen_widget.deleteLater()
            self.fullscreen_widget = None
        
        # Show the grid layout
        for i in range(self.grid_layout.count()):
            item = self.grid_layout.itemAt(i)
            if item.widget():
                item.widget().show()
        
        self.is_fullscreen = False
    
    def open_camera_config(self):
        # Open camera configuration dialog
        dialog = ConfigDialog(self.base_app)
        if dialog.exec_():
            # Update cameras if config changed
            self.update_camera_grid()
    
    def open_system_config(self):
        # Open system configuration dialog
        dialog = SystemConfigDialog(self.base_app)
        if dialog.exec_():
            # Update cameras if config changed
            self.update_camera_grid()
    
    def closeEvent(self, event):
        # Clean up when window is closed
        self.logger.info("Closing main window")
        
        # Stop all camera streams
        for camera in self.camera_widgets.values():
            camera.stop_camera()
        
        # Close second window if it exists
        if self.second_window:
            self.second_window.close()
        
        # Accept the event
        event.accept()


if __name__ == "__main__":
    try:
        # Create application
        app = QApplication(sys.argv)
        
        # Create and show main window
        main_window = MainWindow()
        main_window.show()
        
        # Run application
        sys.exit(app.exec_())
    except Exception as e:
        logger = Logger()
        logger.error(f"Unhandled exception: {str(e)}", exc_info=True)
        
        # Show error dialog if possible
        if 'app' in locals():
            QMessageBox.critical(None, "Error", f"An unhandled exception occurred: {str(e)}")