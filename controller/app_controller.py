# camera_app/controller/app_controller.py

from config.config_manager import ConfigManager
from config.stream_config_manager import CameraStreamConfigManager
from ui.camera_window import CameraWindow
from ui.dialogs import CameraCountDialog, CameraConfigDialog
from utils.logging import log
from PyQt5.QtWidgets import QMessageBox
import sys
import os
import time
from core.camera_record_worker import CameraRecorderWorker
from PyQt5.QtCore import QTimer, QThread, pyqtSignal

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

class _DongleChecker(QThread):
    """Runs the dongle check in a background thread so it never blocks the UI."""
    result = pyqtSignal(bool, str)  # (ok, error_message)

    def run(self):
        from utils.security_pendrive import check_pendrive_key
        ok, err = check_pendrive_key()
        self.result.emit(ok, err or "")


class AppController:
    def __init__(self):
        self.config_mgr = ConfigManager()
        self.stream_config = CameraStreamConfigManager()
        self.windows = {}
        self.recorder_threads = {}
        self.camera_count = self.config_mgr.get_camera_count()

        # ---- periodic dongle enforcement (background thread, every 5 min) ----
        self._dongle_popup_shown = False
        self._dongle_checker = None          # background thread reference
        self._dongle_timer = QTimer()
        self._dongle_timer.timeout.connect(self._start_dongle_check)
        self._dongle_timer.start(5 * 60 * 1000)  # every 5 minutes
        # ------------------------------------------

        if self.camera_count == 0:
            self.change_camera_count()

        self.initialize_windows()
        self.start_recording_for_configured_cameras()

    def _stop_all_streams_fast(self):
        """Signal ALL stream workers to stop, then wait collectively (max 2s total).
        This ensures old VideoCapture objects are released before new streams open."""
        workers = []
        for window in self.windows.values():
            for widget in window.camera_widgets.values():
                if widget.stream_worker:
                    widget.stream_worker.running = False
                    workers.append(widget.stream_worker)
                    # Disconnect signals so old frames don't arrive on new widgets
                    try:
                        widget.stream_worker.frameReady.disconnect()
                        widget.stream_worker.connectionStatus.disconnect()
                    except (TypeError, RuntimeError):
                        pass

        if not workers:
            return

        # Wait for all workers collectively — 2s max total, not per camera
        deadline = time.perf_counter() + 2.0
        for w in workers:
            remaining_ms = max(0, int((deadline - time.perf_counter()) * 1000))
            if remaining_ms > 0:
                w.wait(remaining_ms)

    def _stop_all_recorders_fast(self):
        """Stop all recorders quickly: send 'q' to ffmpeg, don't wait for threads."""
        for cam_id, recorder in list(self.recorder_threads.items()):
            recorder.running = False
            # Send 'q' to ffmpeg without waiting for process exit
            if recorder.process and recorder.process.poll() is None:
                try:
                    recorder.process.stdin.write(b'q')
                    recorder.process.stdin.flush()
                except (BrokenPipeError, OSError):
                    pass
            log.info(f"Signaled recorder for Camera {cam_id} to stop.")
        self.recorder_threads.clear()

    def initialize_windows(self):
        # Fast cleanup of old windows
        if self.windows:
            self._stop_all_streams_fast()
            self._stop_all_recorders_fast()
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
            if new_count == old_count:
                return
            log.info(f"Changing camera count from {old_count} to {new_count}")
            self.config_mgr.set_camera_count(new_count)

            # Rebuild windows — fast cleanup happens inside initialize_windows
            self.initialize_windows()

            # Restart recordings for newly configured cameras
            self.start_recording_for_configured_cameras()

    def open_camera_config(self):
        dialog = CameraConfigDialog(self.camera_count, self.stream_config, controller=self)
        if dialog.exec_():
            log.info("Camera configuration updated — rebuilding windows.")
            self.initialize_windows()
            self.start_recording_for_configured_cameras()


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
        self._dongle_timer.stop()
        # Signal all recorders to stop first (instant)
        for cam_id, recorder in list(self.recorder_threads.items()):
            recorder.running = False
            recorder.stop_ffmpeg()
            log.info(f"Signaled recorder stop for Camera {cam_id}")
        # Then wait collectively with a 5s total cap
        deadline = time.perf_counter() + 5.0
        for cam_id, recorder in list(self.recorder_threads.items()):
            remaining_ms = max(0, int((deadline - time.perf_counter()) * 1000))
            if remaining_ms > 0:
                recorder.wait(remaining_ms)
            log.info(f"Recorder for Camera {cam_id} finished.")
        self.recorder_threads.clear()

    def shutdown(self):
        """Fast shutdown for app exit. Signals everything to stop, brief wait, then done."""
        log.info("Shutdown: stopping all streams and recordings.")
        self._dongle_timer.stop()
        # Signal all streams to stop (non-blocking)
        self._stop_all_streams_fast()
        # Signal all recorders to stop
        self._stop_all_recorders_fast()
        log.info("Shutdown complete.")

    def _start_dongle_check(self):
        """Launch the dongle check in a background thread (never blocks UI)."""
        if self._dongle_checker and self._dongle_checker.isRunning():
            return  # previous check still running, skip
        self._dongle_checker = _DongleChecker()
        self._dongle_checker.result.connect(self._on_dongle_result)
        self._dongle_checker.start()

    def _on_dongle_result(self, ok, err):
        """Handle dongle check result back on the UI thread (via signal)."""
        if ok:
            self._dongle_popup_shown = False
            return

        if not self._dongle_popup_shown:
            self._dongle_popup_shown = True
            try:
                msg = QMessageBox()
                msg.setIcon(QMessageBox.Critical)
                msg.setWindowTitle("Security USB Removed")
                msg.setText(err or "Authorized USB key was removed. The application will now close.")
                msg.exec_()
            except Exception:
                pass

            try:
                self.stop_all_recordings()
            except Exception:
                pass
            for w in list(self.windows.values()):
                try:
                    w.close()
                except Exception:
                    pass
            sys.exit(1)
