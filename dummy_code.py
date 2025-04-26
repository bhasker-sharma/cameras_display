import os
os.environ["OPENCV_VIDEOIO_PRIORITY_MSMF"] = "0"
os.environ["QT_QPA_PLATFORM_PLUGIN_PATH"] = ""

import sys
import cv2
import json
from math import ceil, sqrt
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QGridLayout, QLabel,
    QVBoxLayout, QPushButton, QHBoxLayout, QSizePolicy,
    QDialog, QComboBox, QMessageBox, QLineEdit
)
from PyQt5.QtGui import QImage, QPixmap
from PyQt5.QtCore import Qt, QTimer, QThread, pyqtSignal


class VideoStreamWorker(QThread):
    frame_received = pyqtSignal(QImage)

    def __init__(self, rtsp_link):
        super().__init__()
        self.rtsp_link = rtsp_link
        self.running = True

    def run(self):
        pipeline = f"rtspsrc location={self.rtsp_link} latency=0 ! decodebin ! videoconvert ! appsink"
        cap = cv2.VideoCapture(pipeline, cv2.CAP_GSTREAMER)

        if not cap.isOpened():
            print(f"Cannot open RTSP stream: {self.rtsp_link}")
            return

        while self.running:
            ret, frame = cap.read()
            if not ret:
                print(f"Failed frame from {self.rtsp_link}")
                self.msleep(100)
                continue

            frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            h, w, ch = frame.shape
            bytes_per_line = ch * w
            q_img = QImage(frame.data, w, h, bytes_per_line, QImage.Format_RGB888)
            self.frame_received.emit(q_img)

            self.msleep(30)  # ~30fps

        cap.release()

    def stop(self):
        self.running = False
        self.wait()


class CameraWidget(QWidget):
    doubleClicked = pyqtSignal(int)

    def __init__(self, cam_id, rtsp_link=None):
        super().__init__()
        self.cam_id = cam_id
        self.rtsp_link = rtsp_link
        self.worker = None

        self.setup_ui()

        if self.rtsp_link:
            self.start_stream()

    def setup_ui(self):
        self.setMinimumSize(200, 200)
        self.setStyleSheet("border: 2px solid #444; border-radius: 6px;")
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.header = QLabel(f"Camera {self.cam_id}")
        self.header.setFixedHeight(20)
        self.header.setAlignment(Qt.AlignCenter)
        self.header.setStyleSheet("""
            background-color: #2c3e50;
            color: white;
            font-size: 10px;
            padding: 0px;
            font-weight: bold;
        """)
        layout.addWidget(self.header)

        self.placeholder = QLabel("Camera Feed Placeholder")
        self.placeholder.setAlignment(Qt.AlignCenter)
        self.placeholder.setStyleSheet("background-color: #bdc3c7; color: #333;")
        layout.addWidget(self.placeholder)

        self.setLayout(layout)

    def start_stream(self):
        self.worker = VideoStreamWorker(self.rtsp_link)
        self.worker.frame_received.connect(self.update_frame)
        self.worker.start()

    def update_frame(self, q_img):
        self.placeholder.setPixmap(QPixmap.fromImage(q_img).scaled(
            self.placeholder.width(), self.placeholder.height(), Qt.KeepAspectRatio
        ))

    def closeEvent(self, event):
        if self.worker:
            self.worker.stop()
        super().closeEvent(event)

    def mouseDoubleClickEvent(self, event):
        self.doubleClicked.emit(self.cam_id)


class ClosableMainWindow(QMainWindow):
    window_closed = pyqtSignal()

    def closeEvent(self, event):
        self.window_closed.emit()
        super().closeEvent(event)


class MainWindow(ClosableMainWindow):
    def __init__(self, camera_ids):
        super().__init__()
        self.setWindowTitle("Main Window (Controls + Cameras)")
        self.camera_ids = camera_ids
        self.focused = False
        self.focused_cam_id = None
        self.all_camera_widgets = {}
        self.config_manager = CameraConfigurationManager()

        central_widget = QWidget()
        self.main_layout = QVBoxLayout()

        # === TOP NAV BAR ===
        self.top_bar = QHBoxLayout()
        company_label = QLabel("Toshniwal Industries Pvt. Ltd.")
        company_label.setStyleSheet("font-weight: bold; font-size: 16px; color: #2c3e50;")
        company_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.top_bar.addWidget(company_label)
        self.top_bar.addStretch()

        for i in range(1, 5):
            if i == 2:
                btn = QPushButton("Configure Camera")
            else:
                btn = QPushButton(f"Option {i}")
            btn.setFixedHeight(28)
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #3498db;
                    color: white;
                    padding: 4px 10px;
                    border-radius: 4px;
                }
                QPushButton:hover {
                    background-color: #2980b9;
                }
            """)
            self.top_bar.addWidget(btn)

            # 👇 Hook Option 2
            if i == 2:
                btn.clicked.connect(self.open_camera_config_dialog)


        self.camera_section = QVBoxLayout()
        self.camera_grid = self.create_camera_grid(camera_ids)
        self.camera_section.addLayout(self.camera_grid)

        self.main_layout.addLayout(self.top_bar)
        self.main_layout.addLayout(self.camera_section)

        central_widget.setLayout(self.main_layout)
        self.setCentralWidget(central_widget)
        self.adjustSize()

    def create_camera_grid(self, camera_ids):
        grid = QGridLayout()
        rows, cols = calculate_grid_layout(len(camera_ids))
        for idx, cam_id in enumerate(camera_ids):
            r, c = divmod(idx, cols)

            # 🛠 Fetch saved config
            config = self.config_manager.get_camera_config(cam_id)
            rtsp_link = config.get('rtsp_link') if config else None
            name = config.get('name') if config else None

            # 🛠 Pass RTSP to CameraWidget
            cam_widget = CameraWidget(cam_id, rtsp_link)
            if name:
                cam_widget.header.setText(name)

            cam_widget.doubleClicked.connect(self.focus_camera)
            self.all_camera_widgets[cam_id] = cam_widget
            grid.addWidget(cam_widget, r, c)
        return grid


    def focus_camera(self, cam_id):
        if self.focused and self.focused_cam_id == cam_id:
            self.restore_camera_grid()
            self.focused = False
            self.focused_cam_id = None
            return

        self.focused = True
        self.focused_cam_id = cam_id
        self.clear_layout(self.camera_section)

        zoomed_widget = self.clone_camera_widget(self.all_camera_widgets[cam_id])
        zoomed_widget.doubleClicked.connect(self.focus_camera)
        self.camera_section.addWidget(zoomed_widget)

        if not self.isMaximized():
            self.adjustSize()

    def restore_camera_grid(self):
        self.clear_layout(self.camera_section)
        self.camera_grid = self.create_camera_grid(self.camera_ids)
        self.camera_section.addLayout(self.camera_grid)

        if not self.isMaximized():
            self.adjustSize()


    def clear_layout(self, layout):
        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
            elif item.layout():
                self.clear_layout(item.layout())

    def clone_camera_widget(self, cam_widget):
        # Get the config for the cam_id
        config = self.config_manager.get_camera_config(cam_widget.cam_id)
        rtsp_link = config.get('rtsp_link') if config else None
        name = config.get('name') if config else None

        new_widget = CameraWidget(cam_widget.cam_id, rtsp_link)
        if name:
            new_widget.header.setText(name)

        return new_widget


    def open_camera_config_dialog(self):
        dialog = ConfigureCameraDialog(len(self.camera_ids), self.config_manager, self)
        if dialog.exec_() == QDialog.Accepted:
            # After saving config, update the widgets if necessary
            for cam_id, cam_widget in self.all_camera_widgets.items():
                config = self.config_manager.get_camera_config(cam_id)
                if config and config.get("name"):
                    cam_widget.header.setText(config["name"])


class CameraDisplayWindow(ClosableMainWindow):
    def __init__(self, camera_ids):
        super().__init__()
        self.setWindowTitle("Secondary Camera Window")
        self.camera_ids = camera_ids
        self.focused = False
        self.focused_cam_id = None
        self.all_camera_widgets = {}
        self.config_manager = CameraConfigurationManager()


        central_widget = QWidget()
        self.main_layout = QVBoxLayout()
        self.camera_section = QVBoxLayout()

        self.camera_grid = self.create_camera_grid(camera_ids)
        self.camera_section.addLayout(self.camera_grid)

        self.main_layout.addLayout(self.camera_section)
        central_widget.setLayout(self.main_layout)
        self.setCentralWidget(central_widget)
        self.adjustSize()


    def create_camera_grid(self, camera_ids):
        grid = QGridLayout()
        rows, cols = calculate_grid_layout(len(camera_ids))
        for idx, cam_id in enumerate(camera_ids):
            r, c = divmod(idx, cols)

            # 🛠 Fetch saved config
            config = self.config_manager.get_camera_config(cam_id)
            rtsp_link = config.get('rtsp_link') if config else None
            name = config.get('name') if config else None

            # 🛠 Pass RTSP to CameraWidget
            cam_widget = CameraWidget(cam_id, rtsp_link)
            if name:
                cam_widget.header.setText(name)

            cam_widget.doubleClicked.connect(self.focus_camera)
            self.all_camera_widgets[cam_id] = cam_widget
            grid.addWidget(cam_widget, r, c)
        return grid


    def focus_camera(self, cam_id):
        if self.focused and self.focused_cam_id == cam_id:
            self.restore_camera_grid()
            self.focused = False
            self.focused_cam_id = None
            return

        self.focused = True
        self.focused_cam_id = cam_id
        was_maximized = self.isMaximized()

        self.clear_layout(self.camera_section)

        zoomed_widget = self.clone_camera_widget(self.all_camera_widgets[cam_id])
        zoomed_widget.doubleClicked.connect(self.focus_camera)
        self.camera_section.addWidget(zoomed_widget)

        if not was_maximized:
            self.adjustSize()
        else:
            self.showMaximized()  # 🛠️ Fix for Windows

    def restore_camera_grid(self):
        was_maximized = self.isMaximized()

        self.clear_layout(self.camera_section)
        self.camera_grid = self.create_camera_grid(self.camera_ids)
        self.camera_section.addLayout(self.camera_grid)

        if not was_maximized:
            self.adjustSize()
        else:
            self.showMaximized()  # 🛠️ Ensure full-screen stays

    def clear_layout(self, layout):
        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
            elif item.layout():
                self.clear_layout(item.layout())

    def clone_camera_widget(self, cam_widget):
        # Get the config for the cam_id
        config = self.config_manager.get_camera_config(cam_widget.cam_id)
        rtsp_link = config.get('rtsp_link') if config else None
        name = config.get('name') if config else None

        new_widget = CameraWidget(cam_widget.cam_id, rtsp_link)
        if name:
            new_widget.header.setText(name)

        return new_widget


def create_camera_grid(camera_ids):
    rows, cols = calculate_grid_layout(len(camera_ids))
    grid = QGridLayout()
    for idx, cam_id in enumerate(camera_ids):
        r, c = divmod(idx, cols)
        grid.addWidget(CameraWidget(cam_id), r, c)
    return grid


def calculate_grid_layout(n):
    cols = ceil(sqrt(n))
    rows = ceil(n / cols)
    return rows, cols


class AppController:
    def __init__(self, camera_count):
        self.camera_count = camera_count
        self.windows = []

        if camera_count <= 24:
            main_cams = list(range(1, camera_count + 1))
            self.main_window = MainWindow(main_cams)
            self.windows.append(self.main_window)
        else:
            all_ids = list(range(1, camera_count + 1))
            mid = ceil(camera_count / 2)
            main_cams = all_ids[:mid]
            secondary_cams = all_ids[mid:]

            self.main_window = MainWindow(main_cams)
            self.display_window = CameraDisplayWindow(secondary_cams)

            self.windows.extend([self.main_window, self.display_window])

            # Link close signals so closing one closes both
            self.main_window.window_closed.connect(self.close_all)
            self.display_window.window_closed.connect(self.close_all)

        # Show windows normally (with title bar/buttons)
        for win in self.windows:
            win.showNormal()

    def close_all(self):
        for win in self.windows:
            win.close()


class SystemConfig:
    def __init__(self, config_path="camera_configuration.json"):
        self.config_path = config_path
        self.camera_count = None
        self.valid_camera_options = [4, 8, 12, 16, 20, 24, 32, 48]
        self.load_or_prompt()

    def load_or_prompt(self):
        if self.load_config():
            if self.camera_count is None:
                self.prompt_for_camera_count()
        else:
            self.prompt_for_camera_count()

    def load_config(self):
        if not os.path.exists(self.config_path):
            return False
        try:
            with open(self.config_path, 'r') as f:
                data = json.load(f)
            self.camera_count = data.get('camera_count')
            return True
        except Exception as e:
            print(f"Error reading config file: {e}")
            return False

    def save_config(self):
        try:
            with open(self.config_path, 'w') as f:
                json.dump({'camera_count': self.camera_count}, f, indent=4)
        except Exception as e:
            print(f"Error saving config file: {e}")

    def prompt_for_camera_count(self):
        dialog = CameraCountDialog(self.valid_camera_options)
        result = dialog.exec_()
        if result == QDialog.Accepted:
            self.camera_count = dialog.get_selected_count()
            self.save_config()
        else:
            QMessageBox.critical(None, "Error", "Camera count must be selected to run the application.")
            sys.exit(0)


class CameraCountDialog(QDialog):
    def __init__(self, options):
        super().__init__()
        self.setWindowTitle("Select Camera Count")
        self.setModal(True)
        self.selected_count = None
        self.setup_ui(options)

    def setup_ui(self, options):
        layout = QVBoxLayout()

        label = QLabel("Please select the number of cameras:")
        layout.addWidget(label)

        self.combo_box = QComboBox()
        for option in options:
            self.combo_box.addItem(str(option))
        layout.addWidget(self.combo_box)

        button = QPushButton("Confirm")
        button.clicked.connect(self.accept_selection)
        layout.addWidget(button)

        self.setLayout(layout)
        self.setFixedSize(300, 150)

    def accept_selection(self):
        self.selected_count = int(self.combo_box.currentText())
        self.accept()

    def get_selected_count(self):
        return self.selected_count
    

class CameraConfigurationManager:
    def __init__(self, config_path="camera_config.json"):
        self.config_path = config_path
        self.config_data = {}
        self.load()

    def load(self):
        if os.path.exists(self.config_path):
            try:
                if os.path.getsize(self.config_path) == 0:
                    # File is empty
                    self.config_data = {}
                    return
                with open(self.config_path, "r") as f:
                    self.config_data = json.load(f)
            except Exception as e:
                print(f"Error loading camera config: {e}")
                self.config_data = {}
        else:
            self.config_data = {}


    def save(self):
        try:
            with open(self.config_path, "w") as f:
                json.dump(self.config_data, f, indent=4)
        except Exception as e:
            print(f"Error saving camera config: {e}")

    def set_camera_config(self, cam_id, name, rtsp_link):
        self.config_data[str(cam_id)] = {
            "name": name,
            "rtsp_link": rtsp_link
        }
        self.save()

    def get_camera_config(self, cam_id):
        return self.config_data.get(str(cam_id), {})
    
    
class ConfigureCameraDialog(QDialog):
    def __init__(self, total_cameras, config_manager, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Configure Camera")
        self.setModal(True)
        self.config_manager = config_manager
        self.total_cameras = total_cameras
        self.selected_cam_id = None
        self.name_input = None
        self.rtsp_input = None

        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout()

        # Dropdown to select camera
        label1 = QLabel("Select Camera:")
        layout.addWidget(label1)

        self.camera_dropdown = QComboBox()
        for i in range(1, self.total_cameras + 1):
            self.camera_dropdown.addItem(f"Camera {i}", i)
        layout.addWidget(self.camera_dropdown)

        # Text input for camera name
        label2 = QLabel("Camera Name (optional):")
        layout.addWidget(label2)

        self.name_input = QLabel()
        self.name_input = QLineEdit()
        layout.addWidget(self.name_input)

        # Text input for RTSP link
        label3 = QLabel("RTSP Link:")
        layout.addWidget(label3)

        self.rtsp_input = QLineEdit()
        layout.addWidget(self.rtsp_input)

        # Confirm button
        save_button = QPushButton("Save")
        save_button.clicked.connect(self.save_configuration)
        layout.addWidget(save_button)

        self.setLayout(layout)
        self.setFixedSize(400, 300)

    def save_configuration(self):
        cam_id = self.camera_dropdown.currentData()
        name = self.name_input.text().strip()
        rtsp_link = self.rtsp_input.text().strip()

        if not rtsp_link:
            QMessageBox.warning(self, "Error", "RTSP Link cannot be empty.")
            return

        if not name:
            name = f"Camera {cam_id}"  # fallback default

        self.config_manager.set_camera_config(cam_id, name, rtsp_link)
        self.accept()


def run_app():
    app = QApplication(sys.argv)
    config = SystemConfig()
    controller = AppController(config.camera_count)
    sys.exit(app.exec_())


# 🎬 Run with example count
if __name__ == '__main__':
    run_app()  # Try 15 or 35 to test both modes