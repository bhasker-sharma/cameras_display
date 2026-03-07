# camera_app/controller/app_controller.py

from config.config_manager import ConfigManager
from config.stream_config_manager import CameraStreamConfigManager
from ui.camera_window import CameraWindow
from ui.dialogs import CameraCountDialog, CameraConfigDialog
from utils.logging import log
from utils.subproc import kill_process_tree
from PyQt5.QtWidgets import (
    QApplication, QMessageBox, QDialog, QLabel,
    QFrame, QPushButton, QVBoxLayout, QHBoxLayout,
)
import sys
import os
import time
from core.camera_record_worker import CameraRecorderWorker
from utils.storage_manager import StorageManager
from PyQt5.QtCore import QTimer, QThread, pyqtSignal, Qt

RESTART_EXIT_CODE = 2

GRID_LAYOUTS = {
    4: [(0, 2, 2)],
    8: [(0, 2, 4)],
    12: [(0, 3, 4)],
    16: [(0, 4, 4)],
    20: [(0, 5, 4)],
    24: [(0, 4, 6)],
    32: [(0, 4, 4), (1, 4, 4)],
    50: [(0, 5, 5), (1, 5, 5)],
    48: [(0, 4, 6), (1, 4, 6)],
    56: [(0, 4, 7), (1, 4, 7)],
    64: [(0, 4, 8), (1, 4, 8)],
}

class _DongleChecker(QThread):
    """Runs the dongle check in a background thread so it never blocks the UI."""
    result = pyqtSignal(bool, str)  # (ok, error_message)

    def run(self):
        from utils.security_pendrive import check_pendrive_key
        ok, err = check_pendrive_key()
        self.result.emit(ok, err or "")


class DongleWarningDialog(QDialog):
    """Non-closable dialog shown when the security USB is removed at runtime.

    - User CANNOT close it (no X button, no Escape).
    - Pressing OK terminates the application immediately.
    - A background thread re-checks every 5 seconds; if the dongle is
      re-inserted the dialog dismisses itself and the app resumes normally.
    """

    def __init__(self, error_message="", heading="", status_text="", parent=None):
        super().__init__(parent)
        self.setWindowTitle("Security Alert")
        self.setWindowFlags(
            Qt.Dialog
            | Qt.CustomizeWindowHint
            | Qt.WindowTitleHint
            | Qt.WindowStaysOnTopHint
        )
        self.setModal(True)
        self.setFixedSize(500, 300)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 25, 30, 25)
        layout.setSpacing(10)

        # --- Title ---
        title = QLabel(heading or "SECURITY USB REMOVED")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet(
            "font-size: 20px; font-weight: bold; color: #E53935; letter-spacing: 2px;"
        )

        # --- Separator ---
        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setFixedHeight(2)
        sep.setStyleSheet("background-color: #E53935;")

        # --- Message ---
        msg_text = (
            error_message
            or (
                "The authorized security USB device has been\n"
                "disconnected from this machine.\n\n"
                "Re-insert the device to continue working,\n"
                "or press OK to exit the application."
            )
        )
        msg = QLabel(msg_text)
        msg.setWordWrap(True)
        msg.setAlignment(Qt.AlignCenter)
        msg.setStyleSheet("font-size: 13px; color: #e0e0e0;")

        # --- Status ---
        self._status_label = QLabel(status_text or "Waiting for device reconnection ...")
        self._status_label.setAlignment(Qt.AlignCenter)
        self._status_label.setStyleSheet("font-size: 11px; color: #777777;")

        # --- OK button (exits the app) ---
        ok_btn = QPushButton("OK")
        ok_btn.setFixedWidth(120)
        ok_btn.setCursor(Qt.PointingHandCursor)
        ok_btn.clicked.connect(self._exit_app)
        ok_btn.setStyleSheet("""
            QPushButton {
                background-color: #C62828;
                color: white;
                padding: 8px 0px;
                border-radius: 4px;
                font-size: 14px;
                font-weight: bold;
                border: none;
            }
            QPushButton:hover { background-color: #E53935; }
            QPushButton:pressed { background-color: #B71C1C; }
        """)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_row.addWidget(ok_btn)
        btn_row.addStretch()

        layout.addWidget(title)
        layout.addWidget(sep)
        layout.addSpacing(8)
        layout.addWidget(msg)
        layout.addWidget(self._status_label)
        layout.addSpacing(8)
        layout.addLayout(btn_row)

        self.setStyleSheet("""
            QDialog {
                background-color: #1a1a2e;
                border: 2px solid #C62828;
            }
        """)

        # --- Periodic re-check for dongle (every 5 s) ---
        self._checker = None
        self._check_timer = QTimer(self)
        self._check_timer.timeout.connect(self._run_check)
        self._check_timer.start(5000)

    # -- background dongle re-check --
    def _run_check(self):
        if self._checker and self._checker.isRunning():
            return
        self._checker = _DongleChecker()
        self._checker.result.connect(self._on_result)
        self._checker.start()

    def _on_result(self, ok, _err):
        if ok:
            self._check_timer.stop()
            self.accept()  # dongle back — dismiss and resume

    # -- OK = crash --
    def _exit_app(self):
        self._check_timer.stop()
        os._exit(1)

    # -- block all other ways to close --
    def closeEvent(self, event):
        event.ignore()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            event.ignore()
            return
        super().keyPressEvent(event)


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
        self._dongle_timer.start(1 * 60 * 1000)  # every 1 minute
        # ------------------------------------------

        # Storage watchdog — deletes oldest day folders when free space drops below threshold
        recording_folder = self.config_mgr.get_recording_folder()
        min_free_gb = self.config_mgr.get_min_free_gb()
        self.storage_manager = StorageManager(
            recording_folder=recording_folder or "",
            min_free_gb=min_free_gb,
        )
        if recording_folder and os.path.exists(recording_folder):
            self.storage_manager.start()
        else:
            log.info("[Storage] Watchdog not started — recording folder not configured yet")

        if self.camera_count == 0:
            self.change_camera_count()

        self.initialize_windows()
        # Recorders are now started per-camera inside the staggered stream startup
        # (camera_window._start_next_stream calls start_recording_for_camera)

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
        """Stop all recorders quickly: save metadata, send 'q' to ffmpeg, force-kill if needed."""
        import datetime as _dt
        from utils.helper import save_metadata as _save_metadata
        for cam_id, recorder in list(self.recorder_threads.items()):
            # Save end time BEFORE killing so metadata is never left as "ongoing"
            if recorder.video_start_time and recorder.metadata_file:
                try:
                    end_dt = _dt.datetime.now()
                    duration = (end_dt - recorder.video_start_time).total_seconds()
                    _save_metadata(recorder.metadata_file, recorder.video_start_time, duration, end_dt)
                    log.info(f"Saved metadata for Camera {cam_id} before stop.")
                except Exception as e:
                    log.warning(f"Failed to save metadata for Camera {cam_id}: {e}")
            recorder.running = False
            if recorder.process and recorder.process.poll() is None:
                # Try graceful stop first
                try:
                    recorder.process.stdin.write(b'q')
                    recorder.process.stdin.flush()
                except (BrokenPipeError, OSError):
                    pass
                # Force-kill the process tree to avoid orphans
                kill_process_tree(recorder.process.pid)
            log.info(f"Signaled recorder for Camera {cam_id} to stop.")
        self.recorder_threads.clear()

    def initialize_windows(self):
        # Fast cleanup of old windows (used on first startup only;
        # camera count / config changes now restart the whole app)
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

            # Restart app for clean startup (same as config change)
            log.info("Camera count changed — restarting application for clean startup.")
            QApplication.exit(RESTART_EXIT_CODE)

    def open_camera_config(self):
        dialog = CameraConfigDialog(self.camera_count, self.stream_config, controller=self)
        if dialog.exec_():
            log.info("Camera configuration updated — restarting application for clean startup.")
            QApplication.exit(RESTART_EXIT_CODE)

    def configure_recording_folder(self):
        from PyQt5.QtWidgets import QFileDialog
        current = self.config_mgr.get_recording_folder() or ""
        folder = QFileDialog.getExistingDirectory(
            None,
            "Select Recording Folder",
            current,
        )
        if not folder:
            return  # user cancelled
        self.config_mgr.set_recording_folder(folder)
        log.info(f"Recording folder set to: {folder}")
        QMessageBox.information(
            None,
            "Recording Folder Set",
            f"Recording folder configured:\n{folder}\n\nThe application will restart to apply changes.",
        )
        QApplication.exit(RESTART_EXIT_CODE)


    def start_recording_for_camera(self, cam_id):
        """Start recorder for a single camera (called from staggered stream startup)."""
        recording_folder = self.config_mgr.get_recording_folder()
        if not recording_folder:
            log.info(f"Recording folder not configured — skipping recorder for Camera {cam_id}")
            return

        if cam_id in self.recorder_threads:
            recorder = self.recorder_threads[cam_id]
            if recorder.isRunning():
                return  # already recording
            log.info(f"Recorder thread for Camera {cam_id} stopped unexpectedly. Restarting.")
            del self.recorder_threads[cam_id]

        config = self.stream_config.get_camera_config(cam_id)
        rtsp_url = config.get("rtsp", "")
        name = config.get("name", f"Camera {cam_id}")
        enabled = config.get("enabled", False)
        record = config.get("record", False)

        log.info(f"Evaluating camera {cam_id}: enabled={enabled}, record={record}, rtsp={rtsp_url}")

        if enabled and record and rtsp_url:
            recorder = CameraRecorderWorker(
                cam_id, name, rtsp_url,
                record_enabled=record,
                recording_dir=recording_folder,
            )
            recorder.recording_finished.connect(self.handle_recording_finished)
            recorder.start()
            self.recorder_threads[cam_id] = recorder
            log.info(f"Started recorder for Camera {cam_id}")

    def start_recording_for_configured_cameras(self):
        """Start recorders for all configured cameras (used by camera count change)."""
        for cam_id in range(1, self.camera_count + 1):
            self.start_recording_for_camera(cam_id)

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

            # --- Freeze the application: stop streams/recorders, hide windows ---
            self._stop_all_streams_fast()
            self._stop_all_recorders_fast()
            for w in self.windows.values():
                w.hide()

            dialog = DongleWarningDialog(err)
            dialog.exec_()
            # If we reach here the dongle was re-inserted (dialog.accept()).
            # OK button calls os._exit(1) and never returns here.

            # --- Resume: show windows and reinitialize all streams ---
            for w in self.windows.values():
                w._streams_cleaned = False
                w.showMaximized()
                w.initialize_streams()

            self._dongle_popup_shown = False
