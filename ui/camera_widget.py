# camera_app/ui/camera_widget.py

import os
from PyQt5.QtWidgets import QWidget, QLabel, QSizePolicy, QMessageBox, QVBoxLayout
from PyQt5.QtCore import Qt, pyqtSignal, QTimer
from PyQt5.QtGui import QPixmap, QImage, QFont
from core.camera_stream_worker import CameraStreamWorker
from utils.logging import log

STATUS_COLOR = {
    "NOT_CONFIGURED": "#2196F3",  # Blue
    "DISABLED": "#FF9800",        # Orange
    "ERROR": "#F44336",           # Red
    "CONNECTED": "#4CAF50"        # Green
}

class CameraWidget(QWidget):
    doubleClicked = pyqtSignal(int)
    connectionStatusChanged =  pyqtSignal(int, bool) #new signal 

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
        self._pending_frame = None  # latest frame awaiting paint (drop-old strategy)

        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setStyleSheet("border: 1px solid #444; background-color: #2c2c2c; border-radius: 5px;")

        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)

        self.title = QLabel(self.name)
        self.title.setAlignment(Qt.AlignCenter)
        title_font = QFont()
        title_font.setPointSize(14)  # increase this value as you prefer (e.g., 16, 18)
        title_font.setBold(True)
        self.title.setFont(title_font)

        self.title.setStyleSheet(f"color: white; background-color: {STATUS_COLOR['NOT_CONFIGURED']}; font-weight: bold; padding: 4px;")
                
        layout.addWidget(self.title)

        self.content = QLabel()
        self.content.setAlignment(Qt.AlignCenter)
        self.content.setStyleSheet("background-color: #1a1a1a; padding: 0px; margin: 0px;")
        self.content.setContentsMargins(0, 0, 0, 0)
        self.content.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Ignored)
        layout.addWidget(self.content, stretch=1)

        self.setLayout(layout)
        self.show_placeholder()

    def mouseDoubleClickEvent(self, event):
        self.doubleClicked.emit(self.cam_id)

    def show_error_popup(self, message):
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
                    240, 180, Qt.KeepAspectRatio, Qt.SmoothTransformation))
                return
        self.content.setText("No Stream")
        self.update_status()

    def handle_frame(self, cam_id, frame):
        """Store the latest frame and schedule a single paint.
        If frames arrive faster than the UI can paint, older ones are dropped."""
        if cam_id != self.cam_id:
            return
        self._pending_frame = frame
        # Schedule paint on next event-loop tick (coalesces multiple frames)
        QTimer.singleShot(0, self._paint_pending_frame)

    def _paint_pending_frame(self):
        """Paint only the most recent frame, discarding any that arrived in between."""
        frame = self._pending_frame
        if frame is None or not self.isVisible():
            return
        self._pending_frame = None  # consume it

        height, width, channel = frame.shape
        bytes_per_line = 3 * width
        # BGR888 accepts OpenCV's native BGR format — no cvtColor conversion needed.
        # .copy() ensures Qt owns the data (numpy array may be freed otherwise)
        q_img = QImage(frame.data, width, height, bytes_per_line, QImage.Format_BGR888).copy()
        pixmap = QPixmap.fromImage(q_img)

        content_size = self.content.size()
        scaled_pixmap = pixmap.scaled(
            content_size.width(),
            content_size.height(),
            Qt.KeepAspectRatio,#make it Qt.KeepAspectRatioByExpanding if you need to fit it to full screen.
            Qt.FastTransformation
        )

        if scaled_pixmap.width() > content_size.width() or scaled_pixmap.height() > content_size.height():
            x = (scaled_pixmap.width() - content_size.width()) // 2
            y = (scaled_pixmap.height() - content_size.height()) // 2
            scaled_pixmap = scaled_pixmap.copy(
                x, y,
                min(content_size.width(), scaled_pixmap.width()),
                min(content_size.height(), scaled_pixmap.height())
            )

        self.content.setPixmap(scaled_pixmap)

    def update_connection_status(self, cam_id, connected):
        if cam_id == self.cam_id:
            self.is_connected = connected
            self.update_status()
            self.connectionStatusChanged.emit(cam_id, connected)

    def update_status(self):
        if not self.is_configured:
            color = STATUS_COLOR["NOT_CONFIGURED"]
        elif not self.is_enabled:
            color = STATUS_COLOR["DISABLED"]
        elif not self.is_connected:
            color = STATUS_COLOR["ERROR"]
        else:
            color = STATUS_COLOR["CONNECTED"]

        self.title.setStyleSheet(f"color: white; background-color: {color}; font-weight: bold; padding: 4px;")

    def configure(self, rtsp_url, enabled):
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

        self.stop_stream()

        self.stream_worker = CameraStreamWorker(self.cam_id, rtsp_url)
        self.stream_worker.frameReady.connect(self.handle_frame)
        self.stream_worker.connectionStatus.connect(self.update_connection_status)

        self.stream_worker.finished.connect(lambda: log.info(f"Camera {self.cam_id}: Thread fully stopped."))

        try:
            self.stream_worker.start()
            self.is_streaming = True
            return True
        except Exception as e:
            log.error(f"Failed to start CameraStreamWorker for Camera {self.cam_id}: {str(e)}")
            self.show_error_popup(f"Unable to start camera stream:\n{e}")
            return False

    def stop_stream(self, blocking=True):
        if self.stream_worker:
            log.info(f"Stopping stream for Camera {self.cam_id} (blocking={blocking})")
            try:
                self.stream_worker.frameReady.disconnect(self.handle_frame)
                self.stream_worker.connectionStatus.disconnect(self.update_connection_status)
            except (TypeError, RuntimeError):
                pass  # already disconnected
            self.stream_worker.stop(blocking=blocking)
            self.stream_worker = None
            self._pending_frame = None
            self.is_streaming = False
            self.is_connected = False
            self.show_placeholder()

    def update_name(self, name):
        self.name = name
        self.title.setText(name)
