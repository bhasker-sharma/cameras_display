# camera_app/controller/app_controller.py

from config.config_manager import ConfigManager
from config.stream_config_manager import CameraStreamConfigManager
from ui.camera_window import CameraWindow
from ui.dialogs import CameraCountDialog, CameraConfigDialog
from utils.logging import log

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
    48: [(0, 4, 6), (1, 4, 6)],
}

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
        for window in self.windows.values():
            window.close()
        self.windows.clear()

        self.camera_count = self.config_mgr.get_camera_count()
        if self.camera_count == 0:
            self.camera_count = 4
            self.config_mgr.set_camera_count(self.camera_count)

        layouts = GRID_LAYOUTS.get(self.camera_count, [(0, 2, 2)])
        cam_ids = list(range(1, self.camera_count + 1))

        for window_id, rows, cols in layouts:
            cam_id_start = sum(l[1] * l[2] for l in layouts[:layouts.index((window_id, rows, cols))])
            window_cam_ids = cam_ids[cam_id_start:cam_id_start + rows * cols]

            is_main = window_id == 0
            title = "Camera Viewer" if is_main else f"Camera Viewer (Window {window_id + 1})"

            window = CameraWindow(
                title, window_cam_ids, rows, cols,
                self.stream_config,
                self if is_main else None
            )
            self.windows[window_id] = window

    def change_camera_count(self):
        dialog = CameraCountDialog(valid_camera_counts=list(GRID_LAYOUTS.keys()))
        if dialog.exec_():
            old_count = self.camera_count
            new_count = dialog.get_selected_count()
            log.info(f"Changing camera count from {old_count} to {new_count}")
            self.config_mgr.set_camera_count(new_count)
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
