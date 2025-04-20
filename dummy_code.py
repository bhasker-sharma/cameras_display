import sys
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QGridLayout,
    QLabel, QVBoxLayout
)
from PyQt5.QtCore import pyqtSignal, Qt
from math import ceil, sqrt
from PyQt5.QtWidgets import QPushButton, QHBoxLayout, QSizePolicy

from PyQt5.QtCore import pyqtSignal

class CameraWidget(QWidget):
    doubleClicked = pyqtSignal(int)  # Signal with cam_id

    def __init__(self, cam_id):
        super().__init__()
        self.cam_id = cam_id  # Save for signal use
        self.setMinimumSize(200, 200)
        self.setStyleSheet("border: 2px solid #444; border-radius: 6px;")

        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.header = QLabel(f"Camera {cam_id}")
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
        return CameraWidget(cam_widget.cam_id)


class CameraDisplayWindow(ClosableMainWindow):
    def __init__(self, camera_ids):
        super().__init__()
        self.setWindowTitle("Secondary Camera Window")
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
        return CameraWidget(cam_widget.cam_id)


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

def run_app(camera_count):
    app = QApplication(sys.argv)
    controller = AppController(camera_count)
    sys.exit(app.exec_())

# 🎬 Run with example count
if __name__ == '__main__':
    run_app(camera_count=24)  # Try 15 or 35 to test both modes