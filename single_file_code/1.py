#here the code is workin gwith tthe resizing issue resolved adn the strips are too geting coloured .
import sys
import os
import json
import cv2
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QDialog, QComboBox, QDialogButtonBox, QGridLayout, QSizePolicy, QLineEdit
)
from PyQt5.QtCore import Qt, pyqtSignal, QThread, QMutex, QWaitCondition
from PyQt5.QtGui import QPixmap, QIcon, QImage

# Import logging module or provide a fallback
try:
    from backup.centralisedlogging import log
except ImportError:
    import logging
    logging.basicConfig(level=logging.INFO)
    log = logging.getLogger("CameraApp")

CAMERA_STREAM_FILE = "camera_streams.json"
CONFIG_FILE = "camera_config.json"

# Grid format: {camera_count: [(window_id, rows, cols), ...]}
GRID_LAYOUTS = {
    4: [(0, 2, 2)],
    8: [(0, 2, 4)],
    12: [(0, 3, 4)],
    16: [(0, 4, 4)],
    20: [(0, 5, 4)],
    24: [(0, 4, 6)],
    32: [(0, 4, 4), (1, 4, 4)],
    40: [(0, 5, 4), (1, 5, 4)],
    44: [(0, 5, 4), (1, 4, 6)],
    48: [(0, 4, 6), (1, 4, 6)],  # 24 + 24
}

VALID_CAMERA_COUNTS = list(GRID_LAYOUTS.keys())

# Camera status colors
STATUS_COLOR = {
    "NOT_CONFIGURED": "#2196F3",  # Blue
    "DISABLED": "#FF9800",        # Orange
    "ERROR": "#F44336",           # Red
    "CONNECTED": "#4CAF50"        # Green
}

# ========================== Camera Stream Worker Thread ==========================
class CameraStreamWorker(QThread):
    frameReady = pyqtSignal(int, object)
    connectionStatus = pyqtSignal(int, bool)
    
    def __init__(self, cam_id, rtsp_url):
        super().__init__()
        self.cam_id = cam_id
        self.rtsp_url = rtsp_url
        self.running = False
        self.mutex = QMutex( )
        self.condition = QWaitCondition()
        self.reconnect_attempts = 0
        self.max_reconnect_attempts = 5
        
    def run(self):
        self.running = True
        retry_delay = 1000

        while self.running:
            try:
                cap = cv2.VideoCapture(self.rtsp_url, cv2.CAP_FFMPEG)
                if not cap.isOpened():
                    raise Exception(f"Cannot open stream: {self.rtsp_url}")

                cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'H264'))

                self.connectionStatus.emit(self.cam_id, True)
                self.reconnect_attempts = 0
                frame_count = 0

                while self.running:
                    ret, frame = cap.read()
                    if not ret:
                        log.warning(f"Camera {self.cam_id}: frame read failed.")
                        break
                    frame_count += 1
                    if frame_count % 1 != 0:
                        continue

                    rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    self.frameReady.emit(self.cam_id, rgb_frame)
                    self.msleep(15)

                cap.release()

            except Exception as e:
                log.error(f"Camera {self.cam_id} exception: {e}")
                self.connectionStatus.emit(self.cam_id, False)
                self.reconnect_attempts += 1
                if self.reconnect_attempts > self.max_reconnect_attempts:
                    log.error(f"Camera {self.cam_id}: Max reconnect attempts")
                    break
                self.msleep(retry_delay)
                retry_delay = min(retry_delay * 2, 10000)

        log.info(f"Camera {self.cam_id} worker ended.")
        
    def stop(self):
        self.mutex.lock()
        self.running = False
        self.condition.wakeAll()
        self.mutex.unlock()
        self.wait()

# ========================== Camera Stream Config Manager ==========================
class CameraStreamConfigManager:
    def __init__(self, config_path=CAMERA_STREAM_FILE):
        self.config_path = config_path
        self.config = self.load_config()

    def load_config(self):
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, 'r') as f:
                    return json.load(f)
            except Exception:
                log.error(f"Failed to load camera stream config: {self.config_path}")
                pass
        return {}

    def save_config(self):
        try:
            with open(self.config_path, 'w') as f:
                json.dump(self.config, f, indent=4)
        except Exception as e:
            log.error(f"Failed to save camera stream config: {str(e)}")

    def get_camera_config(self, cam_id):
        return self.config.get(str(cam_id), {})

    def set_camera_config(self, cam_id, data):
        self.config[str(cam_id)] = data
        self.save_config()

# ========================== Camera config dialog ==========================
class CameraConfigDialog(QDialog):
    def __init__(self, camera_count, config_manager, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Configure Camera")
        self.setFixedSize(400, 300)
        self.config_manager = config_manager

        # Center the dialog relative to the parent
        if parent:
            parent_geometry = parent.geometry()
            self.move(
                parent_geometry.center().x() - self.width() // 2,
                parent_geometry.center().y() - self.height() // 2
            )
        layout = QVBoxLayout()

        # Camera Number
        form_layout = QGridLayout()
        form_layout.addWidget(QLabel("Camera Number:"), 0, 0)
        self.camera_num_combo = QComboBox()
        self.camera_num_combo.addItems([str(i) for i in range(1, camera_count + 1)])
        self.camera_num_combo.currentIndexChanged.connect(self.load_existing_config)
        form_layout.addWidget(self.camera_num_combo, 0, 1)

        # Camera Name
        form_layout.addWidget(QLabel("Camera Name:"), 1, 0)
        self.name_edit = QLineEdit()
        form_layout.addWidget(self.name_edit, 1, 1)

        # RTSP URL
        form_layout.addWidget(QLabel("RTSP URL:"), 2, 0)
        self.rtsp_input = QLineEdit()
        form_layout.addWidget(self.rtsp_input, 2, 1)

        # Enable Camera
        form_layout.addWidget(QLabel("Enable Camera:"), 3, 0)
        self.enable_checkbox = QPushButton("Enabled")
        self.enable_checkbox.setCheckable(True)
        self.enable_checkbox.setChecked(True)
        self.enable_checkbox.setStyleSheet("""
            QPushButton {
                background-color: #555;
                color: white;
                padding: 6px 12px;
                border-radius: 4px;
            }
            QPushButton:checked {
                background-color: #007BFF;
            }
        """)
        form_layout.addWidget(self.enable_checkbox, 3, 1)

        layout.addLayout(form_layout)

        # Buttons
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.save_config)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self.setLayout(layout)
        self.load_existing_config()

    def load_existing_config(self):
        cam_id = int(self.camera_num_combo.currentText())
        data = self.config_manager.get_camera_config(cam_id)
        self.name_edit.setText(data.get("name", f"Camera {cam_id}"))
        self.rtsp_input.setText(data.get("rtsp", ""))
        self.enable_checkbox.setChecked(data.get("enabled", True))

    def save_config(self):
        cam_id = int(self.camera_num_combo.currentText())
        data = {
            "name": self.name_edit.text(),
            "rtsp": self.rtsp_input.text(),
            "enabled": self.enable_checkbox.isChecked()
        }
        self.config_manager.set_camera_config(cam_id, data)
        self.accept()

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
                log.error(f"Failed to load config: {self.config_path}")
                pass
        return {"camera_count": 0}

    def save_config(self):
        try:
            with open(self.config_path, 'w') as f:
                json.dump(self.config, f, indent=4)
        except Exception as e:
            log.error(f"Failed to save config: {str(e)}")

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
    doubleClicked = pyqtSignal(int)

    def __init__(self, cam_id, name="Camera", logo_path="assets/logo.png"):
        super().__init__()
        self.cam_id = cam_id
        self.name = name if name else f"Camera {cam_id}"
        self.logo_path = logo_path
        self.is_streaming = False
        self.is_connected = False
        self.is_configured = False
        self.is_enabled = False
        self.stream_worker = None

        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setStyleSheet("border: 1px solid #444; background-color: #2c2c2c; border-radius: 5px;")

        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)

        # Top label - now used as status indicator
        self.title = QLabel(self.name)
        self.title.setAlignment(Qt.AlignCenter)
        # Default label is blue (not configured)
        self.title.setStyleSheet(f"color: white; background-color: {STATUS_COLOR['NOT_CONFIGURED']}; font-weight: bold; padding: 4px;")
        layout.addWidget(self.title)

        # Placeholder/logo/video content
        self.content = QLabel()
        self.content.setAlignment(Qt.AlignCenter)
        self.content.setStyleSheet("background-color: #1a1a1a; padding: 0px; margin: 0px;")
        self.content.setContentsMargins(0, 0, 0, 0)
        self.content.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Ignored)  # Prevent resizing
        layout.addWidget(self.content, stretch=1)

        self.setLayout(layout)
        self.show_placeholder()

    def mouseDoubleClickEvent(self, event):
        self.doubleClicked.emit(self.cam_id)

    def show_error_popup(self, message):
        from PyQt5.QtWidgets import QMessageBox
        msg_box = QMessageBox()
        msg_box.setIcon(QMessageBox.Warning)
        msg_box.setWindowTitle(f"Camera {self.cam_id} Error")
        msg_box.setText(message)
        msg_box.exec_()
        
    def show_placeholder(self):
        if os.path.exists(self.logo_path):
            pixmap = QPixmap(self.logo_path)
            if not pixmap.isNull():
                self.content.setPixmap(pixmap.scaled(
                    160, 120, Qt.KeepAspectRatio, Qt.SmoothTransformation))
                return
        self.content.setText("No Stream")
        self.update_status()
    
    def update_frame(self, frame):
        if frame is None or not self.isVisible():
            return
            
        height, width, channel = frame.shape
        bytes_per_line = 3 * width
        q_img = QImage(frame.data, width, height, bytes_per_line, QImage.Format_RGB888)
        pixmap = QPixmap.fromImage(q_img)
        
        # Get current content size
        content_size = self.content.size()
        
        # Scale the pixmap to fit within the content area
        scaled_pixmap = pixmap.scaled(
            content_size.width(), 
            content_size.height(),
            Qt.KeepAspectRatioByExpanding, 
            Qt.SmoothTransformation)

        # # If the scaled image is larger than the widget, crop it to fit
        if scaled_pixmap.width() > content_size.width() or scaled_pixmap.height() > content_size.height():
            # Calculate coordinates to crop from center
            x = (scaled_pixmap.width() - content_size.width()) // 2
            y = (scaled_pixmap.height() - content_size.height()) // 2
            # Crop the pixmap to the content size
            scaled_pixmap = scaled_pixmap.copy(
                x, y, 
                min(content_size.width(), scaled_pixmap.width()),
                min(content_size.height(), scaled_pixmap.height())
            )
                    
        # Set the pixmap without forcing resizing
        self.content.setPixmap(scaled_pixmap)
    
    def handle_frame(self, cam_id, frame):
        if cam_id == self.cam_id:
            self.update_frame(frame)
    
    def update_connection_status(self, cam_id, connected):
        if cam_id == self.cam_id:
            self.is_connected = connected
            self.update_status()
    
    def update_status(self):
        """Update the title bar color based on camera status"""
        # Not configured - Blue
        if not self.is_configured:
            status_color = STATUS_COLOR["NOT_CONFIGURED"]
        # Configured but not enabled - Orange 
        elif not self.is_enabled:
            status_color = STATUS_COLOR["DISABLED"]
        # Enabled but not connected - Red
        elif not self.is_connected:
            status_color = STATUS_COLOR["ERROR"]
        # Connected and streaming - Green
        else:
            status_color = STATUS_COLOR["CONNECTED"]
            
        self.title.setStyleSheet(f"color: white; background-color: {status_color}; font-weight: bold; padding: 4px;")
    
    def configure(self, rtsp_url, enabled):
        """Configure the camera with a URL and enabled state"""
        self.is_configured = bool(rtsp_url)
        self.is_enabled = enabled
        self.update_status()
    
    def start_stream(self, rtsp_url):
        if not rtsp_url:
            log.warning(f"Camera {self.cam_id}: No RTSP URL provided")
            self.configure(rtsp_url, False)
            self.show_placeholder()
            return False
        
        self.configure(rtsp_url, True)
        
        log.info(f"Starting stream for Camera {self.cam_id}: {rtsp_url}")
        
        # Stop existing stream if any
        self.stop_stream()
        
        # Create and start new worker
        self.stream_worker = CameraStreamWorker(self.cam_id, rtsp_url)
        self.stream_worker.frameReady.connect(self.handle_frame)
        self.stream_worker.connectionStatus.connect(self.update_connection_status)
        
        try:
            self.stream_worker.start()
            self.is_streaming = True
            return True
        except Exception as e:
            log.error(f"Failed to start CameraStreamWorker for Camera {self.cam_id}: {str(e)}")
            self.show_error_popup(f"Unable to start camera stream:\n{e}")
            return False
            
    def stop_stream(self):
        if hasattr(self, 'stream_worker') and self.stream_worker is not None:
            log.info(f"Stopping stream for Camera {self.cam_id}")
            self.stream_worker.stop()
            self.stream_worker.frameReady.disconnect(self.handle_frame)
            self.stream_worker.connectionStatus.disconnect(self.update_connection_status)
            self.stream_worker = None
            self.is_streaming = False
            self.is_connected = False
            self.show_placeholder()

    def update_name(self, name):
        self.name = name
        self.title.setText(name)

# ========================== Camera Window (Shared by Main + Additional) ==========================
class CameraWindow(QMainWindow):
    def __init__(self, title, camera_ids, rows, cols, stream_config, controller=None):
        super().__init__()
        self.setWindowTitle(title)
        self.setWindowIcon(QIcon("assets/logo.png") if os.path.exists("assets/logo.png") else QIcon())
        self.stream_config = stream_config

        self.controller = controller

        self.grid_layout = None
        self.focused = False
        self.focused_cam_id = None
        self.camera_ids = camera_ids
        self.rows = rows
        self.cols = cols
        self.config_manager = stream_config
        self.stream_config = stream_config
        self.controller = controller

        self.central_widget = QWidget()
        layout = QVBoxLayout()
        self.central_widget.setLayout(layout)
        self.setCentralWidget(self.central_widget)

        # Optional navbar for main window
        if controller:
            nav = QHBoxLayout()
            # title_label = QLabel("Camera Viewer")
            # title_label.setStyleSheet("color: #f0f0f0; font-size: 18px; font-weight: bold;")
            # title_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

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

            config_btn = QPushButton("Configure Camera")
            config_btn.clicked.connect(self.controller.open_camera_config)
            config_btn.setStyleSheet("""
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

            refresh_btn = QPushButton("Refresh System")
            refresh_btn.clicked.connect(self.controller.refresh_configurations)
            refresh_btn.setStyleSheet(change_btn.styleSheet())

            nav.addWidget(refresh_btn)
            # nav.addWidget(title_label)
            nav.addStretch()
            nav.addWidget(change_btn)
            nav.addWidget(config_btn)
            layout.addLayout(nav)

        self.grid_widget = QWidget()
        self.grid_layout = QGridLayout()
        self.grid_widget.setLayout(self.grid_layout)
        layout.addWidget(self.grid_widget)  # Add grid widget to main layout

        self.camera_widgets = {}

        for idx, cam_id in enumerate(camera_ids):
            r, c = divmod(idx, cols)

            # Fetch name from stream config if available
            stream_config = self.controller.stream_config.get_camera_config(cam_id) if self.controller else {}
            cam_name = stream_config.get("name", f"Camera {cam_id}")
            
            widget = CameraWidget(cam_id, name=cam_name)
            widget.doubleClicked.connect(self.toggle_focus_view)
            self.camera_widgets[cam_id] = widget
            self.grid_layout.addWidget(widget, r, c)
            
        # Set fixed size policy for grid cells
        for i in range(self.rows):
            self.grid_layout.setRowMinimumHeight(i, 180)  # Minimum height for each row
            self.grid_layout.setRowStretch(i, 1)          # Equal stretch
            
        for i in range(self.cols):
            self.grid_layout.setColumnMinimumWidth(i, 240)  # Minimum width for each column
            self.grid_layout.setColumnStretch(i, 1)         # Equal stretch

        self.showMaximized()  # or showFullScreen()
        self.initialize_streams()
    
    def initialize_streams(self):
        """Initialize camera streams based on configuration"""
        log.info(f"Initializing streams for {len(self.camera_widgets)} cameras")
        
        for cam_id, widget in self.camera_widgets.items():
            stream_config = self.config_manager.get_camera_config(cam_id)
            rtsp_url = stream_config.get("rtsp", "")
            is_enabled = stream_config.get("enabled", True)
            # Log the initialization process for debugging
            log.info(f"Initializing Camera {cam_id}: RTSP={rtsp_url}, Enabled={is_enabled}")
                   
            # Update widget config state
            widget.configure(rtsp_url, is_enabled)
            
            # Start stream if enabled and has URL
            if is_enabled and rtsp_url:
                widget.start_stream(rtsp_url)
                log.info(f"Camera {cam_id} stream initialization attempted.")
            else:
                log.info(f"Camera {cam_id} disabled or no RTSP URL specified")

    def cleanup_streams(self):
        """Stop all camera streams"""
        log.info(f"Cleaning up streams for {len(self.camera_widgets)} cameras")
        for widget in self.camera_widgets.values():
            widget.stop_stream()
            
        if hasattr(self, 'focused_widget') and self.focused_widget:
            self.focused_widget.stop_stream()

    def toggle_focus_view(self, cam_id):
        if not self.focused:
            log.info(f"[{self.windowTitle()}] Expanding Camera {cam_id} to full view.")
            self.focused = True
            self.focused_cam_id = cam_id

            self.grid_widget.hide()  # Just hide the grid

            # 🔥 Load the correct camera name from config
            stream_config = self.stream_config.get_camera_config(cam_id) 
            cam_name = stream_config.get("name", f"Camera {cam_id}")
            rtsp_url = stream_config.get("rtsp", "")
            is_enabled = stream_config.get("enabled", True)

            # Create isolated camera view
            self.focused_widget = CameraWidget(cam_id, name=cam_name)
            self.focused_widget.doubleClicked.connect(self.toggle_focus_view)
            self.centralWidget().layout().addWidget(self.focused_widget)
            
            # Configure and start stream if needed
            self.focused_widget.configure(rtsp_url, is_enabled)
            if is_enabled and rtsp_url:
                self.focused_widget.start_stream(rtsp_url)

        else:
            log.info(f"[{self.windowTitle()}] Restoring grid view from Camera {self.focused_cam_id}.")
            self.focused = False
            
            if hasattr(self, "focused_widget"):
                self.focused_widget.stop_stream()
                self.centralWidget().layout().removeWidget(self.focused_widget)
                self.focused_widget.deleteLater()
                self.focused_widget = None

            self.focused_cam_id = None
            self.grid_widget.show()  # Show the original grid

    def refresh_widgets(self):
        """Refresh camera widget names and streams"""
        for cam_id, widget in self.camera_widgets.items():
            # Get updated config
            stream_config = self.stream_config.get_camera_config(cam_id)
            cam_name = stream_config.get("name", f"Camera {cam_id}")
            rtsp_url = stream_config.get("rtsp", "")
            is_enabled = stream_config.get("enabled", True)
            
            # Update widget name
            widget.update_name(cam_name)
            # Update configuration state
            widget.configure(rtsp_url, is_enabled)
            
            # Restart stream if needed
            if widget.is_streaming:
                widget.stop_stream()
                
            if is_enabled and rtsp_url:
                widget.start_stream(rtsp_url)
                
        # Handle focused widget if it exists
        if self.focused and hasattr(self, 'focused_widget') and self.focused_widget:
            stream_config = self.stream_config.get_camera_config(self.focused_cam_id) 
            cam_name = stream_config.get("name", f"Camera {self.focused_cam_id}")
            rtsp_url = stream_config.get("rtsp", "")
            is_enabled = stream_config.get("enabled", True)
            
            self.focused_widget.update_name(cam_name)
            self.focused_widget.configure(rtsp_url, is_enabled)
            
            if self.focused_widget.is_streaming:
                self.focused_widget.stop_stream()
                
            if is_enabled and rtsp_url:
                self.focused_widget.start_stream(rtsp_url)
    
    def closeEvent(self, event):
        """Handle window close event - clean up resources"""
        self.cleanup_streams()
        super().closeEvent(event)

# ========================== Camera Controller ==========================
class AppController:
    def __init__(self):
        self.config_mgr = ConfigManager()
        self.stream_config = CameraStreamConfigManager()
        self.windows = {}
        self.camera_count = self.config_mgr.get_camera_count()

        if self.camera_count == 0:
            self.change_camera_count()

        self.initialize_windows()

    def initialize_windows(self):
        # Clear any existing windows
        for window in self.windows.values():
            window.close()
        self.windows.clear()

        self.camera_count = self.config_mgr.get_camera_count()
        if self.camera_count == 0:
            self.camera_count = 4  # Default to 4 cameras
            self.config_mgr.set_camera_count(self.camera_count)

        # Create windows according to grid layout
        layouts = GRID_LAYOUTS.get(self.camera_count, [(0, 2, 2)])  # Default to 2x2 grid
        cam_ids = list(range(1, self.camera_count + 1))

        for window_id, rows, cols in layouts:
            cam_id_start = sum(layout[1] * layout[2] for layout in layouts[:layouts.index((window_id, rows, cols))])
            window_cam_ids = cam_ids[cam_id_start:cam_id_start + rows * cols]

            is_main = window_id == 0
            title = "Camera Viewer" if is_main else f"Camera Viewer (Window {window_id + 1})"
            window = CameraWindow(
                title, window_cam_ids, rows, cols,
                self.stream_config,  # 🔥 Always pass stream config
                self if is_main else None  # Controller only if main window
            )
            self.windows[window_id] = window

    def change_camera_count(self):
        dialog = CameraCountDialog()
        if dialog.exec_():
            old_count = self.camera_count
            new_count = dialog.get_selected_count()
            log.info(f"Changing camera count from {old_count} to {new_count}")

            # Update config with new count
            self.config_mgr.set_camera_count(new_count)

            # Re-initialize windows with new camera count
            self.initialize_windows()

    def open_camera_config(self):
        dialog = CameraConfigDialog(self.camera_count, self.stream_config)
        if dialog.exec_():
            log.info("Camera configuration updated")
            self.refresh_configurations()

    def refresh_configurations(self):
        for window in self.windows.values():
            window.refresh_widgets()
        log.info("Camera configurations refreshed")

# ========================== Main Function ==========================
def main():
    # Enable high DPI scaling
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

    # Create the application
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    
    # Set dark theme for entire app
    dark_palette = app.palette()
    dark_palette.setColor(dark_palette.Window, Qt.black)
    dark_palette.setColor(dark_palette.WindowText, Qt.white)
    dark_palette.setColor(dark_palette.Base, Qt.black)
    dark_palette.setColor(dark_palette.AlternateBase, Qt.darkGray)
    dark_palette.setColor(dark_palette.ToolTipBase, Qt.black)
    dark_palette.setColor(dark_palette.ToolTipText, Qt.white)
    dark_palette.setColor(dark_palette.Text, Qt.white)
    dark_palette.setColor(dark_palette.Button, Qt.darkGray)
    dark_palette.setColor(dark_palette.ButtonText, Qt.white)
    dark_palette.setColor(dark_palette.BrightText, Qt.red)
    dark_palette.setColor(dark_palette.Highlight, Qt.darkBlue)
    dark_palette.setColor(dark_palette.HighlightedText, Qt.white)
    app.setPalette(dark_palette)
    
    # Create stylesheets
    app.setStyleSheet("""
        QMainWindow {
            background-color: #121212;
        }
        QDialog {
            background-color: #1e1e1e;
            color: white;
        }
        QLabel {
            color: white;
        }
        QComboBox, QLineEdit {
            background-color: #333;
            color: white;
            border: 1px solid #555;
            padding: 4px;
            border-radius: 4px;
        }
        QComboBox::drop-down {
            border: 0px;
        }
        QComboBox::down-arrow {
            image: url(dropdown.png);
            width: 12px;
            height: 12px;
        }
        QComboBox QAbstractItemView {
            background-color: #333;
            color: white;
        }
    """)
    
    # Create app controller
    controller = AppController()
    
    # Run the app
    sys.exit(app.exec_())

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        log.exception("Unhandled exception occurred")
        from PyQt5.QtWidgets import QMessageBox
        msg_box = QMessageBox()
        msg_box.setIcon(QMessageBox.Critical)
        msg_box.setWindowTitle("Application Error")
        msg_box.setText("An unexpected error occurred.")
        msg_box.setInformativeText(str(e))
        msg_box.exec_()