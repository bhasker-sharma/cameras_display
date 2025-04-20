import sys
import os
import time
import json
from math import ceil, sqrt
from PyQt5.QtWidgets import (
    QApplication, QWidget, QMainWindow, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QDialog, QComboBox, QDialogButtonBox,QSizePolicy,
    QGridLayout, QMessageBox,QCheckBox, QLineEdit
)
from PyQt5.QtCore import Qt, pyqtSignal, QTimer, QPropertyAnimation,QThread, pyqtSignal
from PyQt5.QtGui import QPixmap, QIcon,QImage
from PyQt5.QtWidgets import QGraphicsOpacityEffect
import cv2
import threading

CAMERA_OPTIONS = [4, 8, 12, 16, 20, 24, 32, 40, 48]


# ============================== Config Manager ==============================

class SystemConfigManager:
    def __init__(self, path="config.json"):
        self.path = path
        self.config = {"camera_count": 0}
        self.load_config()

    def load_config(self):
        if os.path.exists(self.path):
            try:
                with open(self.path, "r") as f:
                    self.config = json.load(f)
            except:
                self.config = {"camera_count": 0}

    def save_config(self):
        with open(self.path, "w") as f:
            json.dump(self.config, f, indent=4)

    def get_camera_count(self):
        return self.config.get("camera_count", 0)

    def set_camera_count(self, count):
        self.config["camera_count"] = count
        self.save_config()

# ============================== Camera Stream Class ==============================
class StreamThread(QThread):
    frame_received = pyqtSignal(QImage)

    def __init__(self, rtsp_url):
        super().__init__()
        self.rtsp_url = rtsp_url
        self.running = True

    def run(self):
        cap = cv2.VideoCapture(self.rtsp_url)
        while self.running:
            ret, frame = cap.read()
            if ret:
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                h, w, ch = rgb.shape
                bytes_per_line = ch * w
                image = QImage(rgb.data, w, h, bytes_per_line, QImage.Format_RGB888)
                self.frame_received.emit(image)
        cap.release()

    def stop(self):
        self.running = False
        self.quit()
        self.wait()
# ============================== System config Dialog ==============================

class SystemConfigPopup(QDialog):
    def __init__(self, current_count, config_manager):
        super().__init__()
        self.setWindowTitle("System Configuration")
        self.setFixedSize(360, 160)
        self.setStyleSheet("""
            QDialog {
                background-color: #1e1e1e;
                border: 2px solid #444;
                border-radius: 10px;
            }
            QLabel {
                color: #ffffff;
                font-size: 14px;
                padding-bottom: 4px;
            }
            QComboBox {
                background-color: #2e2e2e;
                color: white;
                font-size: 14px;
                padding: 4px;
                border-radius: 6px;
                border: 1px solid #666;
            }
            QDialogButtonBox QPushButton {
                background-color: #444;
                color: white;
                padding: 6px 16px;
                border-radius: 4px;
            }
            QDialogButtonBox QPushButton:hover {
                background-color: #555;
            }
        """)

        self.config_manager = config_manager

        layout = QVBoxLayout()
        title = QLabel("Update number of cameras:")
        title.setStyleSheet("font-weight: bold; font-size: 16px; color: #FFD700;")
        layout.addWidget(title)

        self.combo = QComboBox()
        self.combo.addItems([str(c) for c in CAMERA_OPTIONS])
        if current_count in CAMERA_OPTIONS:
            self.combo.setCurrentText(str(current_count))
        layout.addWidget(self.combo)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Ok).setText("Save")
        buttons.button(QDialogButtonBox.Cancel).setText("Cancel")
        layout.addWidget(buttons)

        self.setLayout(layout)

        buttons.accepted.connect(self.save_and_close)
        buttons.rejected.connect(self.reject)

    def save_and_close(self):
        selected = int(self.combo.currentText())
        if selected > 0:
            self.config_manager.set_camera_count(selected)
            self.accept()


# ============================== Camera Config Dialog ==============================

class CameraConfigDialog(QDialog):
    def __init__(self, camera_count):
        super().__init__()
        self.setWindowTitle("Camera Configuration")
        self.setFixedSize(420, 300)
        self.config_path = "camera_configs.json"
        self.camera_count = camera_count
        self.camera_configs = self.load_configs()

        self.setStyleSheet("""
            QDialog {
                background-color: #1e1e1e;
                border-radius: 10px;
            }
            QLabel, QCheckBox {
                color: white;
                font-size: 13px;
            }
            QLineEdit, QComboBox {
                background-color: #2e2e2e;
                color: white;
                border-radius: 5px;
                padding: 4px;
                border: 1px solid #555;
            }
            QPushButton {
                background-color: #444;
                color: white;
                padding: 5px 14px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #666;
            }
        """)

        layout = QVBoxLayout()

        self.cam_select = QComboBox()
        self.cam_select.addItems([f"{i}" for i in range(1, camera_count + 1)])
        self.cam_select.currentIndexChanged.connect(self.load_fields)
        layout.addWidget(QLabel("Select Camera Number:"))
        layout.addWidget(self.cam_select)

        self.name_input = QLineEdit()
        layout.addWidget(QLabel("Camera Name:"))
        layout.addWidget(self.name_input)

        self.rtsp_input = QLineEdit()
        layout.addWidget(QLabel("RTSP Link:"))
        layout.addWidget(self.rtsp_input)

        self.enable_checkbox = QCheckBox("Enable this camera")
        layout.addWidget(self.enable_checkbox)

        self.test_btn = QPushButton("Test Connection")
        self.test_btn.clicked.connect(self.test_connection)
        layout.addWidget(self.test_btn)

        self.result_label = QLabel("")
        layout.addWidget(self.result_label)

        btn_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btn_box.accepted.connect(self.save_config)
        btn_box.rejected.connect(self.reject)
        layout.addWidget(btn_box)

        self.setLayout(layout)
        self.load_fields()  # Load initial selection

    def load_configs(self):
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, "r") as f:
                    return json.load(f)
            except:
                return {}
        return {}

    def load_fields(self):
        cam_id = self.cam_select.currentText()
        if cam_id in self.camera_configs:
            data = self.camera_configs[cam_id]
            self.name_input.setText(data.get("name", ""))
            self.rtsp_input.setText(data.get("rtsp", ""))
            self.enable_checkbox.setChecked(data.get("enabled", False))
        else:
            self.name_input.clear()
            self.rtsp_input.clear()
            self.enable_checkbox.setChecked(False)

    def save_config(self):
        cam_id = self.cam_select.currentText()
        self.camera_configs[cam_id] = {
            "name": self.name_input.text(),
            "rtsp": self.rtsp_input.text(),
            "enabled": self.enable_checkbox.isChecked()
        }
        with open(self.config_path, "w") as f:
            json.dump(self.camera_configs, f, indent=4)
        self.accept()

    def test_connection(self):
        rtsp = self.rtsp_input.text().strip()
        if not rtsp:
            self.result_label.setText("❌ Please enter an RTSP URL.")
            return

        self.result_label.setText("⏳ Testing connection...")

        self.test_result = None  # Store result safely

        def worker():
            cap = cv2.VideoCapture(rtsp)
            success, _ = cap.read()
            cap.release()
            self.test_result = success

        thread = threading.Thread(target=worker)
        thread.start()

        # Wait up to 2 seconds for the test to complete
        thread.join(timeout=2)

        if thread.is_alive():
            self.result_label.setText("❌ Connection timeout after 2s.")
        elif self.test_result:
            self.result_label.setText("✅ Connection test passed!")
        else:
            self.result_label.setText("❌ Connection failed.")
# ============================== Camera Count Dialog ==============================

class CameraCountDialog(QDialog):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("🛠️ Initial System Configuration")
        self.setFixedSize(360, 160)
        self.setStyleSheet("""
            QDialog {
                background-color: #1e1e1e;
                border: 2px solid #444;
                border-radius: 10px;
            }
            QLabel {
                color: #ffffff;
                font-size: 14px;
                padding-bottom: 4px;
            }
            QComboBox {
                background-color: #2e2e2e;
                color: white;
                font-size: 14px;
                padding: 4px;
                border-radius: 6px;
                border: 1px solid #666;
            }
            QDialogButtonBox QPushButton {
                background-color: #444;
                color: white;
                padding: 6px 16px;
                border-radius: 4px;
            }
            QDialogButtonBox QPushButton:hover {
                background-color: #555;
            }
        """)

        layout = QVBoxLayout()
        title = QLabel("Select number of cameras to display:")
        title.setStyleSheet("font-weight: bold; font-size: 16px; color: #FFD700;")
        layout.addWidget(title)

        self.combo = QComboBox()
        self.combo.addItems([str(c) for c in CAMERA_OPTIONS])
        layout.addWidget(self.combo)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Ok).setText("Confirm")
        buttons.button(QDialogButtonBox.Cancel).setText("Cancel")
        layout.addWidget(buttons)

        self.setLayout(layout)

        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

    def get_camera_count(self):
        return int(self.combo.currentText())

# ============================== Camera Widget ==============================

class CameraWidget(QWidget):
    doubleClicked = pyqtSignal(int)

    def __init__(self, cam_id, config=None):
        super().__init__()
        self.cam_id = cam_id
        self.setMinimumSize(200, 200)
        self.setStyleSheet("border: 1px solid #555; border-radius: 6px; background-color: #2c2c2c;")

        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.placeholder = QLabel()
        self.placeholder.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.placeholder)

        self.label = QLabel()
        self.label.setFixedHeight(24)
        self.label.setAlignment(Qt.AlignCenter)
        self.label.setStyleSheet("""
            background-color: #444;
            color: white;
            font-size: 10px;
            font-weight: bold;
            border-top: 1px solid #333;
        """)
        layout.addWidget(self.label)

        self.setLayout(layout)

        self.stream_thread = None
        self.load_config(config)

    def load_config(self, config):
        cam_key = str(self.cam_id)
        if config and cam_key in config:
            conf = config[cam_key]
            self.label.setText(conf.get("name") or f"Camera {self.cam_id}")
            if conf.get("enabled") and conf.get("rtsp"):
                self.start_stream(conf["rtsp"])
            else:
                self.show_logo()
        else:
            self.label.setText(f"Camera {self.cam_id}")
            self.show_logo()

    def show_logo(self):
        pixmap = QPixmap("assets/logo.png")
        if not pixmap.isNull():
            self.placeholder.setPixmap(pixmap.scaled(140, 140, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        else:
            self.placeholder.setText("Camera Feed")

    def start_stream(self, rtsp_url):
        self.stream_thread = StreamThread(rtsp_url)
        self.stream_thread.frame_received.connect(self.update_frame)
        self.stream_thread.start()

    def update_frame(self, frame):
        self.placeholder.setPixmap(QPixmap.fromImage(frame).scaled(self.placeholder.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))

    def stop_stream(self):
        if self.stream_thread:
            self.stream_thread.stop()
            self.stream_thread = None

    def closeEvent(self, event):
        self.stop_stream()
        super().closeEvent(event)

    def mouseDoubleClickEvent(self, event):
        self.doubleClicked.emit(self.cam_id)

# ============================== Base Window ==============================

class ClosableMainWindow(QMainWindow):
    window_closed = pyqtSignal()

    def closeEvent(self, event):
        self.window_closed.emit()
        super().closeEvent(event)

# ============================== Main Window ==============================

class MainWindow(ClosableMainWindow):
    def __init__(self, camera_ids, config_manager, controller=None):
        super().__init__()
        self.setWindowTitle("Toshniwal Camera Viewer")
        self.setWindowIcon(QIcon("assets/logo.png"))
        self.camera_ids = camera_ids
        self.config_manager = config_manager
        self.controller = controller

        self.focused = False
        self.focused_cam_id = None
        self.all_camera_widgets = {}

        central_widget = QWidget()
        self.main_layout = QVBoxLayout()

        self.top_bar = QHBoxLayout()
        company_label = QLabel("Toshniwal Industries Pvt. Ltd.")
        company_label.setStyleSheet("font-weight: bold; font-size: 16px; color: #eeeeee;")
        company_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.top_bar.addWidget(company_label)
        self.top_bar.addStretch()

        # 🆕 Buttons
        self.config_btn = self.make_button("Configure Cameras", self.open_config)
        self.cam_config_btn = self.make_button("Camera Config", self.open_camera_config)
        self.reset_btn = self.make_button("Reset", self.reset_config)
        self.rec_btn = self.make_button("Recordings", self.show_recordings)

        for btn in [self.config_btn, self.cam_config_btn, self.reset_btn, self.rec_btn]:
            self.top_bar.addWidget(btn)

        self.camera_section = QVBoxLayout()
        self.camera_grid = self.create_camera_grid(camera_ids)
        self.camera_section.addLayout(self.camera_grid)

        self.main_layout.addLayout(self.top_bar)
        self.main_layout.addLayout(self.camera_section)

        central_widget.setLayout(self.main_layout)
        self.setCentralWidget(central_widget)
        self.showMaximized()

    def make_button(self, text, handler):
        btn = QPushButton(text)
        btn.setFixedHeight(28)
        btn.clicked.connect(handler)
        btn.setStyleSheet("""
            QPushButton {
                background-color: #444;
                color: white;
                padding: 4px 10px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #666;
            }
        """)
        return btn

    def create_camera_grid(self, camera_ids):
        grid = QGridLayout()
        rows, cols = calculate_grid_layout(len(camera_ids))

        # 🔁 Load camera config file
        config = {}
        if os.path.exists("camera_configs.json"):
            try:
                with open("camera_configs.json", "r") as f:
                    config = json.load(f)
            except:
                config = {}

        for idx, cam_id in enumerate(camera_ids):
            r, c = divmod(idx, cols)
            cam_widget = CameraWidget(cam_id, config=config)
            cam_widget.doubleClicked.connect(self.focus_camera)
            self.all_camera_widgets[cam_id] = cam_widget
            grid.addWidget(cam_widget, r, c)
        return grid


    def clear_layout(self, layout):
        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
            elif item.layout():
                self.clear_layout(item.layout())

    def focus_camera(self, cam_id):
        if self.focused and self.focused_cam_id == cam_id:
            self.restore_camera_grid()
            self.focused = False
            self.focused_cam_id = None
            return

        self.focused = True
        self.focused_cam_id = cam_id
        self.clear_layout(self.camera_section)

        zoomed_widget = CameraWidget(cam_id)
        zoomed_widget.doubleClicked.connect(self.focus_camera)
        self.camera_section.addWidget(zoomed_widget)

    def restore_camera_grid(self):
        self.clear_layout(self.camera_section)
        self.camera_grid = self.create_camera_grid(self.camera_ids)
        self.camera_section.addLayout(self.camera_grid)

    def open_config(self):
        popup = SystemConfigPopup(
            current_count=self.config_manager.get_camera_count(),
            config_manager=self.config_manager
        )
        if popup.exec_() == QDialog.Accepted:
            if self.controller:
                self.controller.reset()

    def open_camera_config(self):
        popup = CameraConfigDialog(
            camera_count=self.config_manager.get_camera_count()
        )
        popup.exec_()

    def reset_config(self):
        if self.controller:
            self.controller.reset()

    def show_recordings(self):
        print("🎬 Show recordings (not implemented yet)")


# ============================== Secondary Window ==============================

class CameraDisplayWindow(ClosableMainWindow):
    def __init__(self, camera_ids):
        super().__init__()
        self.setWindowTitle("Secondary Camera Window")
        self.setWindowIcon(QIcon("assets/logo.png"))
        self.camera_ids = camera_ids
        self.focused = False
        self.focused_cam_id = None
        self.all_camera_widgets = {}

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
            cam_widget = CameraWidget(cam_id)
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

        zoomed_widget = CameraWidget(cam_id)
        zoomed_widget.doubleClicked.connect(self.focus_camera)
        self.camera_section.addWidget(zoomed_widget)

        if was_maximized:
            self.showMaximized()

    def restore_camera_grid(self):
        was_maximized = self.isMaximized()
        self.clear_layout(self.camera_section)
        self.camera_grid = self.create_camera_grid(self.camera_ids)
        self.camera_section.addLayout(self.camera_grid)
        if was_maximized:
            self.showMaximized()

    def clear_layout(self, layout):
        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
            elif item.layout():
                self.clear_layout(item.layout())

# ============================== Utility ==============================

def calculate_grid_layout(n):
    cols = ceil(sqrt(n))
    rows = ceil(n / cols)
    return rows, cols

# ============================== App Controller ==============================

class AppController:
    def __init__(self):
        self.config = SystemConfigManager()
        self.camera_count = self.config.get_camera_count()

        if not self.camera_count or self.camera_count == 0:
            dialog = SystemConfigPopup(0, self.config)
            dialog.setWindowTitle("🛠️ Initial System Configuration")
            if dialog.exec_() == QDialog.Accepted:
                self.camera_count = self.config.get_camera_count()
            else:
                sys.exit()
        else:
            self.show_startup_info("✅ System configuration already defined")

        self.windows = []
        self.build_windows()

    def build_windows(self):
        all_ids = list(range(1, self.camera_count + 1))
        if self.camera_count <= 24:
            self.main_window = MainWindow(all_ids, self.config, controller=self)
            self.windows = [self.main_window]
        else:
            half = self.camera_count // 2
            main_ids = all_ids[:half]
            second_ids = all_ids[half:]

            self.main_window = MainWindow(main_ids, self.config, controller=self)
            self.display_window = CameraDisplayWindow(second_ids)

            self.main_window.window_closed.connect(self.close_all)
            self.display_window.window_closed.connect(self.close_all)

            # Show secondary first
            self.display_window.showMaximized()
            
            # Then show and raise main window
            self.main_window.showMaximized()
            self.main_window.raise_()
            self.main_window.activateWindow()

            self.windows = [self.main_window, self.display_window]

    def reset(self):
        self.camera_count = self.config.get_camera_count()
        self.close_all()
        self.build_windows()

    def close_all(self):
        for win in self.windows:
            win.close()

    def show_startup_info(self, message):
        toast = QLabel(message)
        toast.setStyleSheet("""
            QLabel {
                background-color: rgba(60, 60, 60, 220);
                color: white;
                padding: 12px 24px;
                border-radius: 6px;
                font-size: 14px;
            }
        """)
        toast.setWindowFlags(Qt.FramelessWindowHint | Qt.ToolTip)
        toast.setAlignment(Qt.AlignCenter)

        screen_center = QApplication.primaryScreen().geometry().center()
        toast.resize(toast.sizeHint())
        toast.move(screen_center.x() - toast.width() // 2, screen_center.y() - 100)
        toast.setGraphicsEffect(QGraphicsOpacityEffect(opacity=0))
        toast.show()

        effect = toast.graphicsEffect()
        anim = QPropertyAnimation(effect, b"opacity")
        anim.setDuration(2000)
        anim.setStartValue(0.0)
        anim.setKeyValueAt(0.5, 1.0)
        anim.setEndValue(0.0)
        anim.finished.connect(toast.close)
        anim.start()


# ============================== Main ==============================

def run_app():
    app = QApplication(sys.argv)
    app.setStyleSheet("""
        QWidget {
            background-color: #2c2c2c;
            color: #e0e0e0;
            font-family: Arial;
        }
        QLabel {
            color: #f0f0f0;
        }
    """)
    controller = AppController()
    sys.exit(app.exec_())


if __name__ == '__main__':
    run_app()
