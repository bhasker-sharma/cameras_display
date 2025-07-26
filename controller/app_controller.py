# camera_app/controller/app_controller.py

from config.config_manager import ConfigManager
from config.stream_config_manager import CameraStreamConfigManager
from ui.camera_window import CameraWindow
from ui.dialogs import CameraCountDialog, CameraConfigDialog
from utils.logging import log
from PyQt5.QtWidgets import QMessageBox
import sys
import os
from core.camera_record_worker import CameraRecorderWorker

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
        self.recorder_threads = {}
        self.camera_count = self.config_mgr.get_camera_count()

        if self.camera_count == 0:
            self.change_camera_count()

        self.initialize_windows()
        self.start_recording_for_configured_cameras()

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
            #making the dialogue for the pop up
            msg_box = QMessageBox()
            msg_box.setIcon(QMessageBox.Question)
            msg_box.setWindowTitle("restart window")
            msg_box.setText("Configuration updated, Do you want to Restart to apply changes")
            msg_box.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
            result = msg_box.exec_()

            if result == QMessageBox.Yes:
                log.info("Opted for the option yes, going to restart")
                self.stop_all_recordings()
                python = sys.executable
                os.execl(python, python, *sys.argv)
            else:
                log.info("User cancled restart , No restart will be performed")
            # self.initialize_windows()

    def open_camera_config(self):
        dialog = CameraConfigDialog(self.camera_count, self.stream_config, controller =self)
        if dialog.exec_():
            log.info("Camera configuration updated")


    def start_recording_for_configured_cameras(self):
        for cam_id in range(1, self.camera_count + 1):
            if cam_id in self.recorder_threads:
                # Check if thread is still running, else remove it
                recorder = self.recorder_threads[cam_id]
                if not recorder.isRunning():
                    log.info(f"Recorder thread for Camera {cam_id} stopped unexpectedly. Restarting.")
                    del self.recorder_threads[cam_id]
                else:
                    continue  # already recording

            config = self.stream_config.get_camera_config(cam_id)
            rtsp_url = config.get("rtsp", "")
            name = config.get("name", f"Camera {cam_id}")
            enabled = config.get("enabled", False)
            record = config.get("record", False)

            log.info(f"Evaluating camera {cam_id}: enabled={enabled}, record={record}, rtsp={rtsp_url}")
            
            if enabled and record and rtsp_url:
                recorder = CameraRecorderWorker(cam_id, name, rtsp_url, record_enabled=record)
                recorder.recording_finished.connect(self.handle_recording_finished)
                recorder.start()
                self.recorder_threads[cam_id] = recorder
                log.info(f"Started recorder for Camera {cam_id}")

    def handle_recording_finished(self, cam_id):
        log.info(f"Recording finished signal received for Camera {cam_id}")
        if cam_id in self.recorder_threads:
            recorder = self.recorder_threads[cam_id]
            if not recorder.isRunning():
                del self.recorder_threads[cam_id]
                # Restart recording for this camera
                log.info(f"Restarting recorder for Camera {cam_id}")
                self.start_recording_for_configured_cameras()

    def stop_all_recordings(self):
        for cam_id, recorder in self.recorder_threads.items():
            recorder.stop()
            log.info(f"Stopped recorder for Camera {cam_id}")
        self.recorder_threads.clear()
