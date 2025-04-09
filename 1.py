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

class Logger:
    def __init__(self):
        self.logger =  logging.getLogger("CameraApp")
        self.logger.setLevel(logging.DEBUG)


        if not self.logger.handlers:
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

            ch = logging.StreamHandler()
            #ch.setLevel(logging.DEBUG)
            ch.setFormatter(formatter)
            self.logger.addHandler(ch)

            fh = logging.FileHandler("camera_app.log")
            #fh.setLevel(logging.DEBUG)
            fh.setFormatter(formatter)
            self.logger.addHandler(fh)

            self.logger.info("Logger initialized.")


#camera streaming class to handle camera feed
class CameraStream(QObject):
    frame_ready = pyqtSignal(np.ndarray)
    connection_changed = pyqtSignal(bool)

    def __init__(self, rtsp_link):
        super().__init__()
        self.logger = Logger().logger
        self.rtsp_link = rtsp_link
        self.capture = None
        self.is_running = False
        self.connected = False
        self.thread = None
        self.frame_interval = 0.001 #10fps per second
        self.logger.info(f"CameraStream initialized for {self.rtsp_link}")

    def start(self):
        if self.is_running:
            self.logger.warning("Camera stream is already running.")
            return
        self.is_running = True
        self.thread = threading.Thread(target=self.run)
        self.thread.daemon = True  # Make thread daemon so it closes with main program
        self.thread.start()
        self.logger.info(f"Started camera stream thread for {self.rtsp_link}")

    def stop(self):
        self.logger.debug(f"Stopping stream for {self.rtsp_link}")
        self.is_running = False
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=1.0)  # Wait for thread to finish
        if self.capture:
            self.capture.release()
            self.capture = None
        self.logger.info(f"Stopped camera stream for {self.rtsp_link}")

    def run(self):
        self.logger.debug(f"Entering run loop for {self.rtsp_link}")
        retry_count = 0
        max_retries = 3  # Increased retries
        reconnect_delay = 2

        while self.is_running:
            try:
                # Initialize capture if needed
                if self.capture is None:
                    self.logger.debug(f"Creating new capture for {self.rtsp_link}")
                    self.capture = cv2.VideoCapture(self.rtsp_link)
                    # Optimize buffer size and other properties
                    self.capture.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                    self.capture.set(cv2.CAP_PROP_FRAME_WIDTH, 640)  # Reduce resolution
                    self.capture.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)  # Reduce resolution
                    
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
                    retry_count = 0  # Reset retry count on successful connection

                # Resize frame to reduce processing load
                frame = cv2.resize(frame, (640, 480))
                self.frame_ready.emit(frame)
                
                # Reduced frame rate to save CPU
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
                    break

                self.logger.info(f"Retrying connection in {reconnect_delay} seconds (attempt {retry_count}/{max_retries})")
                time.sleep(reconnect_delay)

        self.logger.debug(f"Exiting run loop for {self.rtsp_link}")
        if self.connected:
            self.connected = False
            self.connection_changed.emit(False)


    def test_connection(self):
        # Test the RTSP connection
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




# Base application functionality class
class Baseapp():
    def __init__(self):
        self.config_file = "config.json"
        self.logger = Logger().logger
        self.load_config()
        self.save_config()
        
    
    def load_config(self):
        try:
            with open(self.config_file, "r") as file:
                self.config = json.load(file)
                self.logger.info(f"Configuration loaded successfully from{self.config_file}.")
        except (FileNotFoundError, json.JSONDecodeError):
            self.config = {"camera_count": 24, "cameras":{}}
    
    def save_config(self):
        try:
            with open(self.config_file, "w") as file:
                json.dump(self.config, file)
                self.logger.info(f"Configuration saved successfully to {self.config_file}.")
        except Exception as e:
            self.logger.error(f"Error saving configuration: {e}")
            return False
        return True
    
    def get_Camera_config(self, camera_number):
        # Get the camera configuration for the given camera number
        return self.config.get("cameras", {}).get(camera_number, None)

# Camera configuration dialog
class ConfigDialog(QDialog):
    def __init__(self, base_app):
        super().__init__()
        self.base_app = base_app
        self.logger = Logger().logger
        self.setWindowTitle("Configure Camera")
        self.resize(400, 300)
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
        #create the layout
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(15)
        #create the form layout
        form_layout = QFormLayout(self)
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
        form_layout.addRow("" , self.enable_checkbox)

        main_layout.addLayout(form_layout)
        #create the buttons layout
        buttons_layout = QHBoxLayout()
        
        # Test connection button
        test_button = QPushButton("Test Connection")
        test_button.clicked.connect(self.test_connection)
        self.layout().addWidget(test_button)

        #space between buttons
        buttons_layout.addStretch()
        
        #cancel button to close the dialog
        cancel_button = QPushButton("Cancel")
        cancel_button.clicked.connect(self.reject)
        buttons_layout.addWidget(cancel_button)      

        # OK button to save configuration
        ok_button = QPushButton("Save Configuration")
        ok_button.clicked.connect(self.save_configuration)
        buttons_layout.addWidget(ok_button)

        main_layout.addLayout(buttons_layout)
        self.camera_number_dropdown.currentIndexChanged.connect(self.load_camera_config)
        self.load_camera_config()


    def load_camera_config(self):
        # Load the camera configuration for the selected camera number
        try:
            camera_number = int(self.camera_number_dropdown.currentText())
            camera_config = self.base_app.get_Camera_config(camera_number)

            if camera_config:
                self.camera_name_input.setText(camera_config.get("name", ""))
                self.rtsp_link_input.setText(camera_config.get("rtsp_link", ""))
                self.enable_checkbox.setChecked(camera_config.get("enabled", False))
            else:
                # Clear fields for new camera
                self.logger.info(f"No existing configuration for camera {camera_number}")
                self.camera_name_input.setText(f"camera {camera_number}")
                self.rtsp_link_input.clear()
                self.enable_checkbox.setChecked(False)
        except Exception as e:
            self.logger.error(f"Error loading camera configuration: {str(e)}")


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
        try:

            camera_number = int(self.camera_number_dropdown.currentText())
            camera_name = self.camera_name_input.text()
            rtsp_link = self.rtsp_link_input.text()
            enabled = self.enable_checkbox.isChecked()

            self.logger.debug(f"Saving config for camera {camera_number}:")
            self.logger.debug(f"Name: {camera_name}")
            self.logger.debug(f"RTSP: {rtsp_link}")
            self.logger.debug(f"Enabled: {enabled}")

            if not camera_name or not rtsp_link:
                self.logger.warning("Missing required fields")
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
            if self.base_app.save_config():
                self.logger.info(f"Configuration saved successfully for camera {camera_number}")
                QMessageBox.information(self, "Success", "Camera configuration saved successfully!")
                # Trigger camera grid update after saving configuration
                if isinstance(self.parent(), MainWindow):
                    self.logger.debug("Updating camera grid after configuration save")
                    self.parent().camera_window.update_grid()                
                self.accept()
            else:
                QMessageBox.critical(self, "Error", "Failed to save configuration.")
        except Exception as e:
            self.logger.error(f"Error saving camera configuration: {str(e)}")
            QMessageBox.critical(self, "Error", f"Failed to save configuration: {str(e)}")

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
        self.logger = Logger().logger
        self.setWindowTitle("Camera Window")

        self.layout = QGridLayout()
        self.layout.setSpacing(2) # Add fixed spacing between camera cells
        self.layout.setContentsMargins(2, 2, 2, 2)# Add margins around the grid

        # Set stretch factors to maintain grid proportions
        for i in range(10):  # Reasonable number of columns
            self.layout.setColumnStretch(i, 1)
            self.layout.setRowStretch(i, 1)

        self.setLayout(self.layout)
        self.second_window = None
        self.full_screen_label = None  # To track the full-screen camera
        self.setStyleSheet("background-color: #2b2b2b; color: white;")  # Dark theme
        self.update_grid()

    def update_grid(self):
        self.logger.debug("Starting camera grid update")
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
        self.logger.debug(f"Creating camera grid: start={start_index}, rows={rows}, cols={cols}")
        camera_count = self.base_app.config.get("camera_count", 24)
        for i in range(start_index, min(start_index + rows * cols, camera_count)):
            self.logger.debug(f"Creating CameraLabel for camera {i + 1}")
            cam_label = CameraLabel(i + 1, self)
            self.layout.addWidget(cam_label, (i - start_index) // cols, (i - start_index) % cols)

    def create_second_window(self, start_index, rows, cols):
        self.second_window = QWidget()
        self.second_window.setWindowTitle("Additional Cameras")
        layout = QGridLayout()
        layout.setSpacing(2)  # Match main window spacing
        layout.setContentsMargins(2, 2, 2, 2)  # Match main window margins
        self.second_window.setLayout(layout)
        
        # Apply same dark theme as main window
        self.second_window.setStyleSheet("""
            QWidget {
                background-color: #2b2b2b;
                color: white;
            }
        """)

        camera_count = self.base_app.config.get("camera_count", 24)
        for i in range(start_index, min(start_index + rows * cols, camera_count)):
            self.logger.debug(f"Creating CameraLabel for second window camera {i + 1}")
            cam_label = CameraLabel(i + 1, self)
            row = (i - start_index) // cols
            col = (i - start_index) % cols
            layout.addWidget(cam_label, row, col)

        # Set a minimum size for the second window
        self.second_window.setMinimumSize(800, 600)
        self.second_window.show()

    def show_full_screen_camera(self, cam_number, original_label):
        if self.full_screen_label is None:
            # Create new CameraLabel for fullscreen
            self.full_screen_label = CameraLabel(cam_number, self)
            self.full_screen_label.setWindowFlags(Qt.Window)
            
            # Copy stream from original label
            if original_label.stream:
                self.full_screen_label.stream = original_label.stream
                self.full_screen_label.stream.frame_ready.connect(self.full_screen_label.update_frame)
                self.full_screen_label.stream.connection_changed.connect(self.full_screen_label.update_status)
            
            # Set fullscreen properties
            self.full_screen_label.setWindowState(Qt.WindowFullScreen)
            self.full_screen_label.video_label.setFixedSize(self.screen().size())
            self.full_screen_label.show()
            
            # Connect double click to exit
            self.full_screen_label.mouseDoubleClickEvent = self.exit_full_screen
            self.logger.debug(f"Showing camera {cam_number} in full screen")

    def exit_full_screen(self, event):
        if self.full_screen_label:
            # Disconnect stream before closing
            if self.full_screen_label.stream:
                self.full_screen_label.stream.frame_ready.disconnect(self.full_screen_label.update_frame)
                self.full_screen_label.stream.connection_changed.disconnect(self.full_screen_label.update_status)
                self.full_screen_label.stream = None
            self.full_screen_label.close()
            self.full_screen_label = None
            self.logger.debug("Exited full screen mode")


# Camera label class
class CameraLabel(QWidget):
    def __init__(self, cam_number, parent_window):
        super().__init__()
        self.logger = Logger().logger
        self.logger.debug(f"initializing CameraLabel for camera {cam_number}")
        self.cam_number = cam_number
        self.parent_window = parent_window
        self.stream = None

        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.setStyleSheet("background-color: #2b2b2b; color: white;")  # Dark theme
        self.setMinimumSize(320, 240)  # Set minimum size for the camera cell
        
        # Set fixed size for the camera cell
        self.setFixedSize(320, 240)  # Adjust these values as needed
        
        # Get camera configuration
        camera_config = self.parent_window.base_app.get_Camera_config(cam_number)
        self.logger.debug(f"Camera configuration for camera {cam_number}: {camera_config}")
        
        # Create layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(1, 1, 1, 1)
        layout.setSpacing(1)

        # Status strip for camera state
        self.status_strip = QLabel()
        self.status_strip.setFixedHeight(5)
        layout.addWidget(self.status_strip)

        # Video display label
        self.video_label = QLabel()
        self.video_label.setFixedSize(318, 210) 
        self.video_label.setStyleSheet("background-color: #3c3c3c; border: 1px solid white;")
        self.video_label.setAlignment(Qt.AlignCenter)
        self.video_label.setScaledContents(True)  # This ensures the video fits within the label
        layout.addWidget(self.video_label)

        # Camera name/number label
        name = f"Camera {cam_number}"
        if camera_config:
            name = camera_config.get("name", name)
        self.name_label = QLabel(name)
        self.name_label.setStyleSheet("color: white; font-size: 12px;")
        self.name_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.name_label)

        # Start streaming if camera is configured and enabled
        if camera_config and camera_config.get("enabled", False):
            self.logger.debug(f"Camera {cam_number} is configured and enabled, starting stream")
            rtsp_link = camera_config.get("rtsp_link")
            if rtsp_link:
                self.start_streaming(rtsp_link)
            else:
                self.logger.error(f"Camera {cam_number} is enabled but has no RTSP link")

    def start_streaming(self, rtsp_link):
        self.logger.debug(f"Starting stream for camera {self.cam_number} with link {rtsp_link}")
        if self.stream is None:
            self.stream = CameraStream(rtsp_link)
            self.stream.frame_ready.connect(self.update_frame)
            self.stream.connection_changed.connect(self.update_status)
            self.stream.start()
            self.logger.info(f"Stream started for camera {self.cam_number}")

    def stop_streaming(self):
        if self.stream:
            self.stream.stop()
            self.stream = None

    def update_frame(self, frame):
        self.logger.debug(f"Updating frame for camera {self.cam_number}")
        try:
            # Scale down frame if it's too large
            if frame.shape[0] > 480 or frame.shape[1] > 640:
                frame = cv2.resize(frame, (640, 480))
            height, width = frame.shape[:2]
            bytes_per_line = 3 * width
            q_img = QImage(frame.data, width, height, bytes_per_line, QImage.Format_RGB888).rgbSwapped()
            pixmap = QPixmap.fromImage(q_img)

            # Scale pixmap based on label size
            target_size = self.video_label.size()
            if isinstance(self.parent(), QWidget) and self.parent().windowState() & Qt.WindowFullScreen:
                # Use larger resolution for fullscreen
                target_size = self.parent().size()

            scaled_pixmap = pixmap.scaled(self.video_label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.video_label.setPixmap(scaled_pixmap)
            self.logger.debug(f"Frame updated successfully for camera {self.cam_number}")
        except Exception as e:
            self.logger.error(f"Error updating frame for camera {self.cam_number}: {str(e)}")

    def update_status(self, connected):
        if connected:
            self.logger.info(f"Camera {self.cam_number} connected successfully")
            self.status_strip.setStyleSheet("background-color: green;")
        else:
            self.logger.warning(f"Camera {self.cam_number} disconnected")
            self.status_strip.setStyleSheet("background-color: red;")

    def mouseDoubleClickEvent(self, event):
        self.parent_window.show_full_screen_camera(self.cam_number,self)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        # Update the video frame scaling when the widget is resized
        if self.video_label.pixmap():
            scaled_pixmap = self.video_label.pixmap().scaled(
                self.video_label.size(),
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation
            )
            self.video_label.setPixmap(scaled_pixmap)


# Main application window
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.logger = Logger().logger
        self.logger.debug("Initializing MainWindow")
        self.setWindowTitle("Camera Display")
        # Set dark theme for entire window
        self.setStyleSheet("""
            QMainWindow {
                background-color: #2b2b2b;
            }
            QWidget {
                background-color: #2b2b2b;
                color: white;
            }
            QPushButton {
                background-color: #3c3c3c;
                color: white;
                border: none;
                padding: 5px 10px;
            }
            QPushButton:hover {
                background-color: #4c4c4c;
            }
            QMenuBar {
                background-color: #2b2b2b;
                color: white;
            }
            QMenuBar::item {
                background-color: #2b2b2b;
                color: white;
            }
        """)
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
        self.logger.debug("Opening configuration dialog")
        dialog = ConfigDialog(self.base_app)
        if dialog.exec_() == QDialog.Accepted:
            self.logger.debug("Configuration dialog accepted, updating camera grid")
            self.camera_window.update_grid()
    
    def closeEvent(self, event):
        # Stop all camera streams before closing
        for i in range(self.camera_window.layout.count()):
            widget = self.camera_window.layout.itemAt(i).widget()
            if isinstance(widget, CameraLabel):
                widget.stop_streaming()
        event.accept()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    main_window = MainWindow()
    main_window.show()
    sys.exit(app.exec_())