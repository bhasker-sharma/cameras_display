#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import json
import os
import logging
import time
import threading
from datetime import datetime
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QGridLayout, QDialog, QSpinBox, QFormLayout, QMenuBar, QAction, QMessageBox, QComboBox,
    QLineEdit, QCheckBox, QFrame, QSizePolicy, QDialogButtonBox, QTabWidget
)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QObject, QSize, QThread
from PyQt5.QtGui import QFont, QImage, QPixmap, QIcon, QColor
import cv2
import numpy as np

# Configure the logger class
class Logger:
    LEVELS = {
        'debug': logging.DEBUG,
        'info': logging.INFO,
        'warning': logging.WARNING,
        'error': logging.ERROR,
        'critical': logging.CRITICAL
    }
    
    @staticmethod
    def setup(level='info', log_file='camera_system.log'):
        """Setup the logger with specified level and file"""
        numeric_level = Logger.LEVELS.get(level.lower(), logging.INFO)
        
        # Create logs directory if it doesn't exist
        log_dir = 'logs'
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)
        
        log_path = os.path.join(log_dir, log_file)
        
        # Configure logging
        logging.basicConfig(
            level=numeric_level,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_path),
                logging.StreamHandler()
            ]
        )
        
        logging.info(f"Logging initialized at level: {level}, log file: {log_path}")
    
    @staticmethod
    def get_logger(name):
        """Get a named logger"""
        return logging.getLogger(name)

# Initialize the logger
Logger.setup(level='debug')
logger = Logger.get_logger('main')

# Camera streaming class to handle camera feeds
class CameraStream(QObject):
    """Class to handle video streaming from camera sources"""
    
    # Signal emitted when a new frame is ready
    frame_ready = pyqtSignal(np.ndarray)
    
    # Signal emitted when connection status changes
    connection_changed = pyqtSignal(bool)
    
    def __init__(self, rtsp_url):
        super().__init__()
        self.logger = Logger.get_logger('CameraStream')
        self.rtsp_url = rtsp_url
        self.capture = None
        self.running = False
        self.connected = False
        self.thread = None
    
    def start(self):
        """Start the camera stream in a separate thread"""
        if self.running:
            self.logger.warning("Stream already running")
            return
            
        self.running = True
        self.thread = threading.Thread(target=self._stream_thread)
        self.thread.daemon = True
        self.thread.start()
        self.logger.info(f"Started camera stream with URL: {self.rtsp_url}")
    
    def stop(self):
        """Stop the camera stream"""
        self.running = False
        if self.thread:
            self.thread.join(timeout=1.0)
        if self.capture:
            self.capture.release()
            self.capture = None
        self.logger.info("Stopped camera stream")
    
    def _stream_thread(self):
        """Thread function for streaming camera feed"""
        retry_count = 0
        max_retries = 5
        reconnect_wait = 2  # seconds
        
        while self.running:
            try:
                # Open the camera stream
                if self.capture is None:
                    self.logger.info(f"Connecting to camera: {self.rtsp_url}")
                    self.capture = cv2.VideoCapture(self.rtsp_url)
                    
                # Check if camera is opened successfully
                if not self.capture.isOpened():
                    raise ConnectionError(f"Could not open camera stream: {self.rtsp_url}")
                
                # If we get here, connection is successful
                if not self.connected:
                    self.connected = True
                    self.connection_changed.emit(True)
                    self.logger.info("Camera connected successfully")
                
                # Reset retry count on successful connection
                retry_count = 0
                
                # Read a frame
                ret, frame = self.capture.read()
                
                if not ret:
                    raise ConnectionError("Failed to read frame from camera")
                
                # Emit the frame
                self.frame_ready.emit(frame)
                
                # Small sleep to prevent high CPU usage
                time.sleep(0.03)  # ~30fps
                
            except ConnectionError as e:
                if self.connected:
                    self.connected = False
                    self.connection_changed.emit(False)
                    self.logger.error(f"Camera disconnected: {str(e)}")
                
                # Release the capture and try to reconnect
                if self.capture:
                    self.capture.release()
                    self.capture = None
                
                retry_count += 1
                if retry_count > max_retries:
                    self.logger.error(f"Max retries ({max_retries}) reached, stopping stream")
                    self.running = False
                    break
                
                self.logger.info(f"Retrying connection in {reconnect_wait} seconds (attempt {retry_count}/{max_retries})")
                time.sleep(reconnect_wait)
            
            except Exception as e:
                self.logger.error(f"Error in stream thread: {str(e)}")
                time.sleep(1)  # Prevent rapid retries on error
    
    def is_connected(self):
        """Check if the camera is connected"""
        return self.connected
    
    def test_connection(self):
        """Test if the camera can be connected"""
        try:
            test_capture = cv2.VideoCapture(self.rtsp_url)
            if not test_capture.isOpened():
                return False
                
            # Try to read a frame
            ret, _ = test_capture.read()
            test_capture.release()
            return ret
        except Exception as e:
            self.logger.error(f"Error testing connection: {str(e)}")
            return False


# Base application functionality class
class BaseApp:
    def __init__(self):
        self.logger = Logger.get_logger('BaseApp')
        self.config_file = "config.json"
        self.load_config()
        self.save_config()
    
    def load_config(self):
        """Load configuration from JSON file"""
        try:
            with open(self.config_file, "r") as file:
                self.config = json.load(file)
                self.logger.info(f"Loaded configuration from {self.config_file}")
        except (FileNotFoundError, json.JSONDecodeError) as e:
            self.logger.warning(f"Config file not found or invalid: {str(e)}, creating default")
            # Default configuration with no cameras
            self.config = {
                "camera_count": 24,
                "cameras": {}
            }
    
    def save_config(self):
        """Save configuration to JSON file"""
        try:
            with open(self.config_file, "w") as file:
                json.dump(self.config, file, indent=4)
                self.logger.info(f"Saved configuration to {self.config_file}")
            return True
        except Exception as e:
            self.logger.error(f"Error saving configuration: {str(e)}")
            return False
    
    def get_camera_config(self, camera_number):
        """Get configuration for a specific camera"""
        cameras = self.config.get("cameras", {})
        return cameras.get(str(camera_number))


# Camera configuration dialog with improved styling
class ConfigDialog(QDialog):
    def __init__(self, base_app):
        super().__init__()
        self.logger = Logger.get_logger('ConfigDialog')
        self.base_app = base_app
        self.setWindowTitle("Configure Camera")
        self.resize(500, 400)  # Make dialog larger
        
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
            QCheckBox::indicator { 
                width: 15px; 
                height: 15px; 
            }
            QCheckBox::indicator:unchecked { 
                border: 1px solid #555555; 
                background-color: #3E3E42; 
            }
            QCheckBox::indicator:checked { 
                border: 1px solid #555555; 
                background-color: #0E639C; 
            }
            QGroupBox { 
                border: 1px solid #555555; 
                border-radius: 3px; 
                margin-top: 10px; 
                color: #FFFFFF; 
                font-weight: bold;
            }
            QGroupBox::title { 
                subcontrol-origin: margin; 
                left: 10px; 
                padding: 0 3px 0 3px; 
            }
        """)
        
        # Create a main layout
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(15)
        
        # Create a form layout
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
        
        # Add the form layout to the main layout
        main_layout.addLayout(form_layout)
        
        # Create buttons layout
        buttons_layout = QHBoxLayout()
        
        # Test connection button
        test_button = QPushButton("Test Connection")
        test_button.clicked.connect(self.test_connection)
        buttons_layout.addWidget(test_button)
        
        # Spacer
        buttons_layout.addStretch()
        
        # Cancel button
        cancel_button = QPushButton("Cancel")
        cancel_button.clicked.connect(self.reject)
        buttons_layout.addWidget(cancel_button)
        
        # OK button to save configuration
        ok_button = QPushButton("Save Configuration")
        ok_button.clicked.connect(self.save_configuration)
        buttons_layout.addWidget(ok_button)
        
        # Add buttons layout to main layout
        main_layout.addLayout(buttons_layout)
        
        # Connect signals
        self.camera_number_dropdown.currentIndexChanged.connect(self.load_camera_config)
        
        # Load initial camera configuration
        self.load_camera_config()

    def load_camera_config(self):
        """Load existing camera configuration when a camera is selected"""
        try:
            camera_number = int(self.camera_number_dropdown.currentText())
            camera_config = self.base_app.get_camera_config(camera_number)
            
            if camera_config:
                self.logger.info(f"Loading configuration for camera {camera_number}")
                self.camera_name_input.setText(camera_config.get("name", f"Camera {camera_number}"))
                self.rtsp_link_input.setText(camera_config.get("rtsp_link", ""))
                self.enable_checkbox.setChecked(camera_config.get("enabled", False))
            else:
                # Clear fields for new camera
                self.logger.info(f"No existing configuration for camera {camera_number}")
                self.camera_name_input.setText(f"Camera {camera_number}")
                self.rtsp_link_input.clear()
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
        
        # Status strip at the top (colored bar)
        self.status_strip = QFrame()
        self.status_strip.setFixedHeight(12)
        layout.addWidget(self.status_strip)
        
        # Camera display area
        self.display_label = QLabel("No Signal")
        self.display_label.setAlignment(Qt.AlignCenter)
        self.display_label.setStyleSheet("background-color: #1E1E1E; color: white;")
        self.display_label.setFixedSize(160, 120)
        layout.addWidget(self.display_label)
        
        # Camera name label
        self.name_label = QLabel(self.getDisplayName())
        self.name_label.setAlignment(Qt.AlignCenter)
        self.name_label.setStyleSheet("padding: 2px; background-color: rgba(0, 0, 0, 120); color: white;font-weight: bold")
        layout.addWidget(self.name_label)
        
        # Style the widget
        self.setStyleSheet("""
            QWidget {
                border: 1px solid #555555;
                background-color: #2D2D30;
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
        
        #use a flow layout that maintain fixed-size widgets in a grid
        self.layout = QGridLayout()
        self.layout.setSpacing(8)
        self.setContentsMargins(10,10,10,10)#add some margins
        # Set a fixed size for grid cells
        self.layout.setHorizontalSpacing(10)
        self.layout.setVerticalSpacing(10)
        
        self.setLayout(self.layout)
        self.second_window = None
        self.full_screen_camera = None  # Track full-screen camera
        self.camera_widgets = {}  # Keep track of created camera widgets
        
        # Apply dark theme
        self.setStyleSheet("""
            QWidget {
                background-color: #2b2b2b;
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
                background-color: #2b2b2b;
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
        
        # Get the camera widget
        camera_widget = self.camera_widgets.get(camera_number)
        if not camera_widget:
            self.logger.warning(f"Camera widget {camera_number} not found")
            return
        
        # Create a new window for full screen view
        self.full_screen_camera = QWidget()
        self.full_screen_camera.setWindowTitle(f"Camera {camera_number} - Full Screen")
        self.full_screen_camera.setWindowFlags(Qt.Window)
        
        # Create a new camera widget for the full screen view
        layout = QVBoxLayout(self.full_screen_camera)
        layout.setContentsMargins(0, 0, 0, 0)
        
        fs_camera_widget = CameraWidget(camera_number, self.base_app, self.full_screen_camera)
        layout.addWidget(fs_camera_widget)
        
        # Handle double-click to exit full screen
        fs_camera_widget.double_clicked.connect(self.exit_full_screen)
        
        # Show in full screen
        self.full_screen_camera.showFullScreen()
    
    def exit_full_screen(self, camera_number):
        """Exit full screen mode"""
        if self.full_screen_camera:
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