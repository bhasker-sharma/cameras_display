#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Camera Monitoring System - Main Application
"""

import sys
import json
import os
import logging
from datetime import datetime

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QDialog, QGridLayout, QFrame, QMessageBox,
    QFormLayout, QLineEdit, QCheckBox, QComboBox, QTabWidget, QSpinBox
)
from PyQt5.QtCore import Qt, QObject, QThread, pyqtSignal, QTimer, QSize
from PyQt5.QtGui import QImage, QPixmap, QKeyEvent
import cv2
import numpy as np


# Set up logging
class Logger:
    """Centralized logger for the application"""
    
    _instance = None
    _initialized = False
    _log_level = logging.DEBUG
    _log_file = "logs/camera_system.log"
    
    @classmethod
    def initialize(cls, log_level=logging.DEBUG, log_file=None):
        """Initialize the logging system"""
        cls._log_level = log_level
        if log_file:
            cls._log_file = log_file
            
        # Create logs directory if it doesn't exist
        log_dir = os.path.dirname(cls._log_file)
        if log_dir and not os.path.exists(log_dir):
            os.makedirs(log_dir)
            
        # Configure logging
        logging.basicConfig(
            level=cls._log_level,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(cls._log_file),
                logging.StreamHandler()
            ]
        )
        
        logging.info(f"Logging initialized at level: {logging.getLevelName(cls._log_level)}, log file: {cls._log_file}")
        cls._initialized = True
    
    @classmethod
    def get_logger(cls, name):
        """Get a logger with the specified name"""
        if not cls._initialized:
            cls.initialize()
        return logging.getLogger(name)


# Camera stream class
class CameraStream(QObject):
    """Class for handling camera streaming"""
    
    # Signals
    frame_ready = pyqtSignal(np.ndarray)
    connection_changed = pyqtSignal(bool)
    
    def __init__(self, rtsp_url):
        super().__init__()
        self.logger = Logger.get_logger('CameraStream')
        self.rtsp_url = rtsp_url
        self.running = False
        self.paused = False
        self.connected = False
        self.thread = None
        self.cap = None
        
    def start(self):
        """Start the camera stream"""
        if self.thread and self.thread.isRunning():
            return
            
        self.running = True
        self.paused = False
        
        # Create a thread for the camera stream
        self.thread = QThread()
        self.moveToThread(self.thread)
        self.thread.started.connect(self._process_frames)
        self.thread.start()
        
    def stop(self):
        """Stop the camera stream"""
        self.running = False
        if self.thread and self.thread.isRunning():
            self.thread.quit()
            self.thread.wait()
        self.release_camera()
        
    def pause(self):
        """Pause the camera stream"""
        self.paused = True
        
    def resume(self):
        """Resume the camera stream"""
        self.paused = False
        
    def release_camera(self):
        """Release the camera resource"""
        if self.cap:
            self.cap.release()
            self.cap = None
        
    def test_connection(self):
        """Test the camera connection"""
        try:
            cap = cv2.VideoCapture(self.rtsp_url)
            if not cap.isOpened():
                self.logger.warning(f"Failed to open camera: {self.rtsp_url}")
                return False
                
            ret, frame = cap.read()
            cap.release()
            
            if not ret or frame is None:
                self.logger.warning(f"Failed to read frame from camera: {self.rtsp_url}")
                return False
                
            self.logger.info(f"Successfully connected to camera: {self.rtsp_url}")
            return True
        except Exception as e:
            self.logger.error(f"Error testing camera connection: {str(e)}")
            return False
    
    def _process_frames(self):
        """Process frames from the camera stream"""
        retry_count = 0
        max_retries = 5
        retry_delay = 2  # seconds
        
        while self.running:
            try:
                # If paused, wait and continue
                if self.paused:
                    QThread.msleep(100)
                    continue
                    
                # Create a new capture if needed
                if self.cap is None:
                    self.logger.info(f"Opening camera: {self.rtsp_url}")
                    self.cap = cv2.VideoCapture(self.rtsp_url)
                    
                # Check if camera is opened
                if not self.cap.isOpened():
                    if self.connected:
                        self.connected = False
                        self.connection_changed.emit(False)
                        self.logger.warning(f"Lost connection to camera: {self.rtsp_url}")
                    
                    retry_count += 1
                    if retry_count > max_retries:
                        QThread.sleep(retry_delay)
                        retry_count = 0
                        # Try to reopen the camera
                        self.release_camera()
                    continue
                
                # Read a frame
                ret, frame = self.cap.read()
                
                if not ret or frame is None:
                    if self.connected:
                        self.connected = False
                        self.connection_changed.emit(False)
                        self.logger.warning(f"Failed to read frame from camera: {self.rtsp_url}")
                    
                    retry_count += 1
                    if retry_count > max_retries:
                        QThread.sleep(retry_delay)
                        retry_count = 0
                        # Try to reopen the camera
                        self.release_camera()
                    continue
                
                # Reset retry count on success
                retry_count = 0
                
                # Update connection status if needed
                if not self.connected:
                    self.connected = True
                    self.connection_changed.emit(True)
                    self.logger.info(f"Connected to camera: {self.rtsp_url}")
                
                # Emit the frame
                self.frame_ready.emit(frame)
                
                # Small delay to prevent high CPU usage
                QThread.msleep(30)  # ~30 fps
                
            except Exception as e:
                self.logger.error(f"Error in camera stream: {str(e)}")
                if self.connected:
                    self.connected = False
                    self.connection_changed.emit(False)
                
                # Release the camera and retry
                self.release_camera()
                QThread.sleep(retry_delay)
        
        # Cleanup
        self.release_camera()
        

# Base application class
class BaseApp:
    """Base application class for managing configuration"""
    
    def __init__(self, config_file="config.json"):
        self.logger = Logger.get_logger('BaseApp')
        self.config_file = config_file
        self.config = self.load_config()
        
    def load_config(self):
        """Load the configuration from the JSON file"""
        self.logger.info(f"Loading configuration from {self.config_file}")
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r') as f:
                    config = json.load(f)
                self.logger.info("Configuration loaded successfully")
                return config
            else:
                self.logger.warning(f"Configuration file not found, creating default configuration")
                return self.create_default_config()
        except Exception as e:
            self.logger.error(f"Error loading configuration: {str(e)}")
            return self.create_default_config()
            
    def create_default_config(self):
        """Create a default configuration"""
        config = {
            "camera_count": 24,
            "cameras": {}
        }
        
        # Save the default configuration
        self.save_config(config)
        return config
        
    def save_config(self, config=None):
        """Save the configuration to the JSON file"""
        if config is None:
            config = self.config
            
        try:
            with open(self.config_file, 'w') as f:
                json.dump(config, f, indent=4)
            self.logger.info("Configuration saved successfully")
            return True
        except Exception as e:
            self.logger.error(f"Error saving configuration: {str(e)}")
            return False
            
    def get_camera_config(self, camera_number):
        """Get the configuration for a specific camera"""
        camera_number = str(camera_number)
        if "cameras" in self.config and camera_number in self.config["cameras"]:
            return self.config["cameras"][camera_number]
        return None
        

# Camera configuration dialog
class ConfigDialog(QDialog):
    def __init__(self, base_app):
        super().__init__()
        self.logger = Logger.get_logger('ConfigDialog')
        self.base_app = base_app
        self.setWindowTitle("Camera Configuration")
        self.resize(500, 400)
        
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
            QLineEdit, QComboBox { 
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
                spacing: 5px;
            }
            QCheckBox::indicator {
                width: 15px;
                height: 15px;
            }
            QCheckBox::indicator:checked {
                background-color: #0E639C;
                border: 2px solid #FFFFFF;
            }
        """)
        
        # Main layout
        main_layout = QVBoxLayout(self)
        form_layout = QFormLayout()
        form_layout.setSpacing(10)
        
        # Camera number dropdown
        self.camera_number_dropdown = QComboBox()
        for i in range(1, self.base_app.config.get("camera_count", 24) + 1):
            self.camera_number_dropdown.addItem(str(i))
        self.camera_number_dropdown.currentIndexChanged.connect(self.load_camera_config)
        form_layout.addRow("Camera Number:", self.camera_number_dropdown)
        
        # Camera name input
        self.camera_name_input = QLineEdit()
        form_layout.addRow("Camera Name:", self.camera_name_input)
        
        # RTSP link input
        self.rtsp_link_input = QLineEdit()
        form_layout.addRow("RTSP Link:", self.rtsp_link_input)
        
        # Enable checkbox
        self.enable_checkbox = QCheckBox("Enable Camera")
        form_layout.addRow("", self.enable_checkbox)
        
        # Add form layout to main layout
        main_layout.addLayout(form_layout)
        
        # Add horizontal layout for buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        # Test connection button
        test_button = QPushButton("Test Connection")
        test_button.clicked.connect(self.test_connection)
        button_layout.addWidget(test_button)
        
        # Cancel button
        cancel_button = QPushButton("Cancel")
        cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(cancel_button)
        
        # Save button
        save_button = QPushButton("Save")
        save_button.clicked.connect(self.save_configuration)
        button_layout.addWidget(save_button)
        
        # Add button layout to main layout
        main_layout.addLayout(button_layout)
        
        # Load initial camera configuration
        self.load_camera_config()
        
    def load_camera_config(self):
        """Load the camera configuration into the form"""
        try:
            camera_number = int(self.camera_number_dropdown.currentText())
            camera_config = self.base_app.get_camera_config(camera_number)
            
            if camera_config:
                self.camera_name_input.setText(camera_config.get("name", ""))
                self.rtsp_link_input.setText(camera_config.get("rtsp_link", ""))
                self.enable_checkbox.setChecked(camera_config.get("enabled", False))
            else:
                self.camera_name_input.setText(f"Camera {camera_number}")
                self.rtsp_link_input.setText("")
                self.enable_checkbox.setChecked(False)
        except Exception as e:
            self.logger.error(f"Error loading camera configuration: {str(e)}")
            
    def test_connection(self):
        """Test the RTSP connection"""
        rtsp_link = self.rtsp_link_input.text().strip()
        if not rtsp_link:
            QMessageBox.warning(self, "Error", "Please enter an RTSP link.")
            return

        # Create a progress dialog instead of a message box
        from PyQt5.QtWidgets import QProgressDialog
        progress = QProgressDialog("Testing connection to camera...", "Cancel", 0, 0, self)
        progress.setWindowTitle("Testing Connection")
        progress.setModal(True)
        progress.setCancelButton(None)  # Remove cancel button
        progress.setWindowModality(Qt.WindowModal)  # Make it block only its parent window
        progress.show()
        QApplication.processEvents()  # Make sure the dialog is displayed

        # Test the connection in a way that doesn't block the UI
        def do_test():
            try:
                stream = CameraStream(rtsp_link)
                return stream.test_connection()
            except Exception as e:
                self.logger.error(f"Error testing connection: {str(e)}")
                return None

        # Test connection
        success = do_test()
        
        # Always ensure we close the progress dialog
        progress.close()
        progress.deleteLater()

        # Handle the result
        if success is None:
            QMessageBox.critical(self, "Error", "An error occurred while testing the connection.\nPlease check your network and camera settings.")
        elif success:
            QMessageBox.information(self, "Success", "Connection successful!")
        else:
            QMessageBox.critical(self, "Error", "Failed to connect to the camera.\nPlease check the URL and ensure the camera is online.")

    def save_configuration(self):
        """Save the camera configuration to the JSON file"""
        try:
            camera_number = int(self.camera_number_dropdown.currentText())
            camera_name = self.camera_name_input.text().strip()
            rtsp_link = self.rtsp_link_input.text().strip()
            enabled = self.enable_checkbox.isChecked()
            
            # Basic validation
            if not camera_name:
                QMessageBox.warning(self, "Error", "Please enter a camera name.")
                return
            
            if enabled and not rtsp_link:
                QMessageBox.warning(self, "Error", "Please enter an RTSP link for enabled cameras.")
                return
            
            # Update the configuration in the JSON file
            if "cameras" not in self.base_app.config:
                self.base_app.config["cameras"] = {}
            
            self.base_app.config["cameras"][str(camera_number)] = {
                "name": camera_name,
                "rtsp_link": rtsp_link,
                "enabled": enabled
            }
            
            if self.base_app.save_config():
                self.logger.info(f"Saved configuration for camera {camera_number}")
                QMessageBox.information(self, "Success", "Camera configuration saved successfully!")
                self.accept()
            else:
                QMessageBox.critical(self, "Error", "Failed to save configuration.")
        except Exception as e:
            self.logger.error(f"Error saving camera configuration: {str(e)}")
            QMessageBox.critical(self, "Error", f"An error occurred:\n{str(e)}")


# System configuration dialog
class SystemConfigDialog(QDialog):
    def __init__(self, base_app, camera_window):
        super().__init__()
        self.logger = Logger.get_logger('SystemConfigDialog')
        self.base_app = base_app
        self.camera_window = camera_window
        self.setWindowTitle("System Configuration")
        self.resize(500, 400)
        
        # Apply dark theme styling (same as ConfigDialog)
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
            QTabWidget::pane { 
                border: 1px solid #555555; 
                background-color: #2D2D30;
            }
            QTabBar::tab { 
                background-color: #3E3E42; 
                color: #FFFFFF; 
                border: 1px solid #555555; 
                border-bottom: none; 
                padding: 5px 10px; 
                border-top-left-radius: 3px; 
                border-top-right-radius: 3px;
            }
            QTabBar::tab:selected { 
                background-color: #0E639C; 
            }
        """)
        
        # Main layout
        main_layout = QVBoxLayout(self)
        
        # Tab widget for different settings
        tab_widget = QTabWidget()
        
        # General settings tab
        general_tab = QWidget()
        general_layout = QVBoxLayout(general_tab)
        
        # Form layout for camera count
        form_layout = QFormLayout()
        form_layout.setSpacing(10)
        
        # SpinBox to set the number of cameras
        self.camera_count_spinbox = QSpinBox()
        self.camera_count_spinbox.setMinimum(1)
        self.camera_count_spinbox.setMaximum(48)
        self.camera_count_spinbox.setValue(self.base_app.config.get("camera_count", 24))
        form_layout.addRow("Number of Cameras:", self.camera_count_spinbox)
        
        # Add form layout to general tab
        general_layout.addLayout(form_layout)
        
        # Information label about camera layout
        info_label = QLabel(
            "The system will automatically configure the grid layout based on camera count:\n\n"
            "• For 1-4 cameras: Single row grid\n"
            "• For 5-20 cameras: 4×5 grid\n"
            "• For 21-24 cameras: 4×6 grid\n"
            "• For 25-28 cameras: 4×7 grid\n"
            "• For 29-32 cameras: Two 4×4 grids\n"
            "• For 33-40 cameras: Two 4×5 grids\n"
            "• For 41-48 cameras: Two 4×6 grids"
        )
        info_label.setWordWrap(True)
        info_label.setStyleSheet("padding: 10px; background-color: #3E3E42; border-radius: 3px;")
        general_layout.addWidget(info_label)
        
        # Add stretch to push content to the top
        general_layout.addStretch()
        
        # Add tab to tab widget
        tab_widget.addTab(general_tab, "General Settings")
        
        # Add tab widget to main layout
        main_layout.addWidget(tab_widget)
        
        # Dialog buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        # Cancel button
        cancel_button = QPushButton("Cancel")
        cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(cancel_button)
        
        # Save button
        save_button = QPushButton("Save Configuration")
        save_button.clicked.connect(self.save_config)
        button_layout.addWidget(save_button)
        
        # Add button layout to main layout
        main_layout.addLayout(button_layout)

    def save_config(self):
        """Update the configuration and save it"""
        try:
            # Update the camera count
            self.base_app.config["camera_count"] = self.camera_count_spinbox.value()
            
            if self.base_app.save_config():
                self.logger.info(f"Updated system configuration: camera_count={self.camera_count_spinbox.value()}")
                
                # Update the camera grid
                self.camera_window.update_grid()
                
                QMessageBox.information(self, "Success", "System configuration saved successfully!")
                self.accept()
            else:
                QMessageBox.critical(self, "Error", "Failed to save configuration.")
        except Exception as e:
            self.logger.error(f"Error saving system configuration: {str(e)}")
            QMessageBox.critical(self, "Error", f"An error occurred:\n{str(e)}")


# Single camera display widget with status strip
class CameraWidget(QWidget):
    """Widget to display a single camera feed with status information"""
    
    # Signal emitted when camera is double-clicked
    double_clicked = pyqtSignal(int)
    
    def __init__(self, camera_number, base_app, parent=None):
        super().__init__(parent)
        self.logger = Logger.get_logger(f'CameraWidget_{camera_number}')
        self.camera_number = camera_number
        self.base_app = base_app
        self.stream = None
        self.last_frame = None
        self.connected = False
        
        # Get camera configuration
        self.camera_config = self.base_app.get_camera_config(camera_number)
        
        # Setup UI
        self.setupUI()
        
        # Update status
        self.updateStatus()
        
        # Start camera if enabled
        if self.camera_config and self.camera_config.get("enabled", False):
            self.startCamera()
    
    def setupUI(self):
        """Set up the UI components"""
        # Main layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(3, 3, 3, 3)
        layout.setSpacing(2)
        
        # Status strip at the top (colored bar) - Enlarged to 12px height
        self.status_strip = QFrame()
        self.status_strip.setFixedHeight(12)
        layout.addWidget(self.status_strip)
        
        # Camera display area
        self.display_label = QLabel("No Signal")
        self.display_label.setAlignment(Qt.AlignCenter)
        self.display_label.setStyleSheet("background-color: #1E1E1E; color: white;")
        # Fixed size for the display area to maintain consistent grid appearance
        self.display_label.setFixedSize(160, 120)
        layout.addWidget(self.display_label)
        
        # Camera name label (simplified to a smaller strip)
        self.name_label = QLabel(self.getDisplayName())
        self.name_label.setAlignment(Qt.AlignCenter)
        self.name_label.setStyleSheet("color: white; font-weight: bold; font-size: 10px; background-color: #1E1E1E; padding: 2px;")
        self.name_label.setFixedHeight(20)  # Make the label smaller
        layout.addWidget(self.name_label)
        
        # Style the widget
        self.setStyleSheet("""
            QWidget {
                border: 1px solid #555555;
                background-color: #1E1E1E;
            }
        """)
    
    def getDisplayName(self):
        """Get the display name for the camera"""
        if self.camera_config and self.camera_config.get("name"):
            return self.camera_config.get("name")
        return f"Camera {self.camera_number}"
    
    def updateStatus(self):
        """Update the status strip color and display message"""
        if not self.camera_config:
            # Blue - Not configured
            self.status_strip.setStyleSheet("background-color: #0066cc;")
            self.display_label.setText("Not Configured")
            return
            
        if not self.camera_config.get("rtsp_link"):
            # Blue - Not configured (no RTSP link)
            self.status_strip.setStyleSheet("background-color: #0066cc;")
            self.display_label.setText("Not Configured")
            return
            
        if not self.camera_config.get("enabled", False):
            # Orange - Configured but not enabled
            self.status_strip.setStyleSheet("background-color: #FFA500;")
            self.display_label.setText("Disabled")
            return
            
        if not self.connected:
            # Red - Enabled but not connected
            self.status_strip.setStyleSheet("background-color: #FF0000;")
            self.display_label.setText("No Signal")
            return
            
        # Green - Connected and streaming
        self.status_strip.setStyleSheet("background-color: #00FF00;")
    
    def startCamera(self):
        """Start the camera stream"""
        if not self.camera_config or not self.camera_config.get("enabled", False):
            return
            
        rtsp_url = self.camera_config.get("rtsp_link", "")
        if not rtsp_url:
            self.logger.warning(f"No RTSP URL for camera {self.camera_number}")
            return
            
        try:
            # Create and start the camera stream
            self.stream = CameraStream(rtsp_url)
            self.stream.frame_ready.connect(self.updateFrame)
            self.stream.connection_changed.connect(self.connectionChanged)
            self.stream.start()
        except Exception as e:
            self.logger.error(f"Error starting camera {self.camera_number}: {str(e)}")
    
    def stopCamera(self):
        """Stop the camera stream"""
        if self.stream:
            try:
                self.stream.frame_ready.disconnect(self.updateFrame)
                self.stream.connection_changed.disconnect(self.connectionChanged)
                self.stream.stop()
                self.stream = None
                self.connected = False
                self.updateStatus()
            except Exception as e:
                self.logger.error(f"Error stopping camera {self.camera_number}: {str(e)}")
    
    def updateFrame(self, frame):
        """Update the display with a new frame"""
        try:
            # Convert the frame to Qt format
            self.last_frame = frame.copy()
            h, w, ch = frame.shape
            bytes_per_line = ch * w
            convert_to_qt_format = QImage(frame.data, w, h, bytes_per_line, QImage.Format_RGB888).rgbSwapped()
            pixmap = QPixmap.fromImage(convert_to_qt_format)
            
            # Scale pixmap to fit the label while maintaining aspect ratio
            scaled_pixmap = pixmap.scaled(
                self.display_label.size(),
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation
            )
            
            # Update the label
            self.display_label.setPixmap(scaled_pixmap)
        except Exception as e:
            self.logger.error(f"Error updating frame for camera {self.camera_number}: {str(e)}")
    
    def connectionChanged(self, connected):
        """Handle connection status changes"""
        self.connected = connected
        self.updateStatus()
        
        if connected:
            self.logger.info(f"Camera {self.camera_number} connected")
        else:
            self.logger.warning(f"Camera {self.camera_number} disconnected")
    
    def mouseDoubleClickEvent(self, event):
        """Handle mouse double-click events"""
        if event.button() == Qt.LeftButton:
            self.double_clicked.emit(self.camera_number)
    
    def resizeEvent(self, event):
        """Handle resize events to scale the video frame"""
        super().resizeEvent(event)
        if self.last_frame is not None:
            self.updateFrame(self.last_frame)


# Camera grid window
class CameraWindow(QWidget):
    def __init__(self, base_app):
        super().__init__()
        self.logger = Logger.get_logger('CameraWindow')
        self.base_app = base_app
        self.setWindowTitle("Camera Window")
        
        # Use a FlowLayout that maintains fixed-size widgets
        self.layout = QGridLayout()
        self.layout.setSpacing(8)  # Increased spacing for better appearance
        self.layout.setContentsMargins(10, 10, 10, 10)  # Add some margins
        
        # Set a fixed size for grid cells
        self.layout.setHorizontalSpacing(10)
        self.layout.setVerticalSpacing(10)
        
        self.setLayout(self.layout)
        self.second_window = None
        self.full_screen_camera = None  # Track full-screen camera
        self.camera_widgets = {}  # Keep track of created camera widgets
        
        # Apply dark theme - BLACK background for main window
        self.setStyleSheet("""
            QWidget {
                background-color: #000000;
                color: white;
            }
        """)
        
        # Setup the grid
        self.update_grid()
    
    def update_grid(self):
        """Update the camera grid layout"""
        self.logger.info("Updating camera grid")
        
        # Stop all camera streams
        for widget in self.camera_widgets.values():
            widget.stopCamera()
        
        # Clear the grid layout
        self.clearLayout()
        self.camera_widgets.clear()

        # Close the second window if it exists
        if self.second_window:
            self.second_window.close()
            self.second_window = None

        # Create the camera grid(s)
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
    
    def clearLayout(self):
        """Clear all widgets from the layout"""
        while self.layout.count():
            item = self.layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.setParent(None)
    
    def create_camera_grid(self, start_index, rows, cols):
        """Create a grid of camera widgets"""
        self.logger.info(f"Creating camera grid: start={start_index}, rows={rows}, cols={cols}")
        camera_count = self.base_app.config.get("camera_count", 24)
        
        for i in range(start_index, min(start_index + rows * cols, camera_count)):
            camera_number = i + 1
            widget = CameraWidget(camera_number, self.base_app, self)
            self.camera_widgets[camera_number] = widget
            widget.double_clicked.connect(self.show_full_screen_camera)
            self.layout.addWidget(widget, (i - start_index) // cols, (i - start_index) % cols)
    
    def create_second_window(self, start_index, rows, cols):
        """Create a second window for additional cameras"""
        self.logger.info(f"Creating second window: start={start_index}, rows={rows}, cols={cols}")
        
        self.second_window = QWidget()
        self.second_window.setWindowTitle("Additional Cameras")
        
        # Use the same improved grid layout for the second window
        layout = QGridLayout()
        layout.setSpacing(8)  # Increased spacing for better appearance
        layout.setContentsMargins(10, 10, 10, 10)  # Add some margins
        
        # Set a fixed size for grid cells
        layout.setHorizontalSpacing(10)
        layout.setVerticalSpacing(10)
        
        self.second_window.setLayout(layout)
        
        # Apply dark theme
        self.second_window.setStyleSheet("""
            QWidget {
                background-color: #000000;
                color: white;
            }
        """)

        camera_count = self.base_app.config.get("camera_count", 24)
        for i in range(start_index, min(start_index + rows * cols, camera_count)):
            camera_number = i + 1
            widget = CameraWidget(camera_number, self.base_app, self.second_window)
            self.camera_widgets[camera_number] = widget
            widget.double_clicked.connect(self.show_full_screen_camera)
            layout.addWidget(widget, (i - start_index) // cols, (i - start_index) % cols)

        self.second_window.show()
    
    def show_full_screen_camera(self, camera_number):
        """Show a camera in full screen mode"""
        self.logger.info(f"Showing camera {camera_number} in full screen")
        
        # If already showing a full screen camera, close it
        if self.full_screen_camera:
            self.full_screen_camera.close()
            self.full_screen_camera = None
            return
        
        # Get the camera configuration
        camera_config = self.base_app.get_camera_config(camera_number)
        if not camera_config:
            self.logger.warning(f"Camera {camera_number} not configured")
            return
        
        # Create a new window for full screen view
        self.full_screen_camera = QWidget()
        self.full_screen_camera.setWindowTitle(f"Camera {camera_number} - {camera_config.get('name', f'Camera {camera_number}')}")
        self.full_screen_camera.setWindowFlags(Qt.Window)
        
        # Create layout for full screen view - simple and clean
        layout = QVBoxLayout(self.full_screen_camera)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Status strip at the top
        status_strip = QFrame()
        status_strip.setFixedHeight(12)
        if not camera_config.get("enabled", False):
            status_strip.setStyleSheet("background-color: #FFA500;")  # Orange
        elif not self.camera_widgets[camera_number].connected:
            status_strip.setStyleSheet("background-color: #FF0000;")  # Red
        else:
            status_strip.setStyleSheet("background-color: #00FF00;")  # Green
        layout.addWidget(status_strip)
        
        # Camera display - just a QLabel that takes up all available space
        display_label = QLabel()
        display_label.setAlignment(Qt.AlignCenter)
        display_label.setStyleSheet("background-color: #000000;")
        layout.addWidget(display_label)
        
        # Simple small label at the bottom
        name_label = QLabel(camera_config.get("name", f"Camera {camera_number}"))
        name_label.setAlignment(Qt.AlignCenter)
        name_label.setStyleSheet("background-color: #1E1E1E; color: white; font-weight: bold; padding: 5px;")
        name_label.setFixedHeight(30)
        layout.addWidget(name_label)
        
        # Set up camera stream
        if camera_config.get("enabled", False):
            rtsp_url = camera_config.get("rtsp_link", "")
            if rtsp_url:
                try:
                    # Create and start the camera stream
                    stream = CameraStream(rtsp_url)
                    
                    # Function to update the frame
                    def update_frame(frame):
                        try:
                            # Convert the frame to Qt format
                            h, w, ch = frame.shape
                            bytes_per_line = ch * w
                            convert_to_qt_format = QImage(frame.data, w, h, bytes_per_line, QImage.Format_RGB888).rgbSwapped()
                            pixmap = QPixmap.fromImage(convert_to_qt_format)
                            
                            # Scale pixmap to fit the label while maintaining aspect ratio
                            scaled_pixmap = pixmap.scaled(
                                display_label.size(),
                                Qt.KeepAspectRatio,
                                Qt.SmoothTransformation
                            )
                            
                            # Update the label
                            display_label.setPixmap(scaled_pixmap)
                        except Exception as e:
                            self.logger.error(f"Error updating fullscreen frame: {str(e)}")
                    
                    # Connect signals
                    stream.frame_ready.connect(update_frame)
                    
                    # Track the stream for cleanup
                    self.full_screen_camera.stream = stream
                    
                    # Start the stream
                    stream.start()
                except Exception as e:
                    self.logger.error(f"Error starting full screen camera: {str(e)}")
                    display_label.setText("No Signal")
            else:
                display_label.setText("No Signal")
        else:
            display_label.setText("Disabled")
        
        # Handle double-click to exit full screen
        self.full_screen_camera.mouseDoubleClickEvent = lambda event: self.exit_full_screen(camera_number) if event.button() == Qt.LeftButton else None
        
        # Show in full screen
        self.full_screen_camera.showFullScreen()
    
    def exit_full_screen(self, camera_number):
        """Exit full screen mode"""
        if self.full_screen_camera:
            # Stop the stream if it exists
            if hasattr(self.full_screen_camera, 'stream'):
                self.full_screen_camera.stream.stop()
            
            self.full_screen_camera.close()
            self.full_screen_camera = None
    
    def closeEvent(self, event):
        """Handle close event"""
        # Stop all camera streams
        for widget in self.camera_widgets.values():
            widget.stopCamera()
        
        # Close the second window if it exists
        if self.second_window:
            self.second_window.close()
        
        # Close the full screen camera if it exists
        if self.full_screen_camera:
            if hasattr(self.full_screen_camera, 'stream'):
                self.full_screen_camera.stream.stop()
            self.full_screen_camera.close()
        
        super().closeEvent(event)


# Main application window
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.logger = Logger.get_logger('MainWindow')
        self.logger.info("Initializing main window")
        self.setWindowTitle("Camera Monitoring System")
        self.base_app = BaseApp()

        # Create the camera window
        self.camera_window = CameraWindow(self.base_app)
        self.setCentralWidget(self.camera_window)

        # Create the menu bar with improved styling
        self.createMenuBar()

        # Start in maximized mode
        self.showMaximized()
        self.logger.info("Main window initialized")
    
    def createMenuBar(self):
        """Create the menu bar with company name and buttons"""
        # Create a custom widget for the menu bar
        menu_bar = QWidget()
        menu_bar.setFixedHeight(50)
        menu_bar.setStyleSheet("""
            QWidget {
                background-color: #1E1E1E;
                border-bottom: 1px solid #3E3E42;
            }
            QPushButton {
                background-color: #0E639C;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 3px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #1177BB;
            }
            QPushButton:pressed {
                background-color: #0D5A8C;
            }
            QLabel {
                color: white;
                font-size: 16px;
                font-weight: bold;
            }
        """)
        
        # Create layout for the menu bar
        menu_layout = QHBoxLayout(menu_bar)
        menu_layout.setContentsMargins(10, 5, 10, 5)
        
        # Add company name to the left
        company_name = QLabel("TIPL Toshniwal Industries Pvt Ltd")
        company_name.setStyleSheet("color: white; font-size: 16px; padding-left: 10px;")
        menu_layout.addWidget(company_name)
        
        # Add spacer to push buttons to the right
        menu_layout.addStretch()
        
        # Create and add buttons
        config_button = QPushButton("Config")
        config_button.clicked.connect(self.open_config_dialog)
        
        recordings_button = QPushButton("Recordings")
        recordings_button.clicked.connect(self.open_recordings)
        
        logs_button = QPushButton("Logs")
        logs_button.clicked.connect(self.open_logs)
        
        system_config_button = QPushButton("System Config")
        system_config_button.clicked.connect(self.open_system_config_dialog)
        
        for button in [config_button, recordings_button, logs_button, system_config_button]:
            menu_layout.addWidget(button)
        
        # Set the menu bar widget as the menuBar
        self.setMenuWidget(menu_bar)
    
    def open_system_config_dialog(self):
        """Open the system configuration dialog"""
        dialog = SystemConfigDialog(self.base_app, self.camera_window)
        dialog.exec_()
    
    def open_config_dialog(self):
        """Open the camera configuration dialog"""
        dialog = ConfigDialog(self.base_app)
        if dialog.exec_() == QDialog.Accepted:
            # If configuration was changed, update the camera grid
            self.camera_window.update_grid()
    
    def open_recordings(self):
        """Open the recordings dialog (placeholder)"""
        QMessageBox.information(self, "Recordings", "Recordings feature is not implemented yet.")
    
    def open_logs(self):
        """Open the logs dialog (placeholder)"""
        QMessageBox.information(self, "Logs", "Logs feature is not implemented yet.")
    
    def closeEvent(self, event):
        """Handle window close event"""
        # Make sure to close all created windows and stop all streams
        self.logger.info("Closing main window")
        event.accept()


if __name__ == "__main__":
    try:
        # Create the application
        app = QApplication(sys.argv)
        
        # Set application style
        app.setStyle("Fusion")
        
        # Create and show the main window
        main_window = MainWindow()
        main_window.show()
        
        # Start the event loop
        sys.exit(app.exec_())
    except Exception as e:
        logger = Logger.get_logger('main')
        logger.critical(f"Unhandled exception: {str(e)}", exc_info=True)
        # Show error dialog
        if 'app' in locals():
            QMessageBox.critical(None, "Critical Error", f"An unhandled exception occurred:\n{str(e)}")