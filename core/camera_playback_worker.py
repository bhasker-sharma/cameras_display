import os
import sys
import shutil
import vlc

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout,
    QPushButton, QFileSystemModel, QTreeView,
    QFileDialog, QMessageBox, QLabel, QSlider, QFrame
)
from PyQt5.QtCore import QModelIndex, Qt, QTimer


class PlaybackDialog(QDialog):
    def __init__(self, parent=None, recordings_dir="recordings"):
        super().__init__(parent)
        self.setWindowTitle("Playback & Export Recordings")
        self.resize(900, 600)

        self.recordings_dir = os.path.abspath(recordings_dir)

        # --- Layout ---
        main_layout = QVBoxLayout(self)

        # Horizontal split for tree + video
        split_layout = QHBoxLayout()
        main_layout.addLayout(split_layout)

        # --- File system model & view ---
        self.model = QFileSystemModel()
        self.model.setRootPath(self.recordings_dir)
        self.model.setNameFilters(["*.mp4"])
        self.model.setNameFilterDisables(False)

        self.tree = QTreeView()
        self.tree.setModel(self.model)
        self.tree.setRootIndex(self.model.index(self.recordings_dir))
        self.tree.setColumnWidth(0, 300)
        self.tree.setAlternatingRowColors(True)
        self.tree.setSortingEnabled(True)
        self.tree.setRootIsDecorated(True)
        self.tree.setItemsExpandable(True)

        split_layout.addWidget(self.tree, 2)

        # --- VLC video output frame ---
        self.video_frame = QFrame(self)
        self.video_frame.setMinimumHeight(400)

        # --- VLC setup ---
        self.instance = vlc.Instance()
        self.player = self.instance.media_player_new()

        # --- Playback controls ---
        self.controls_layout = QHBoxLayout()
        self.play_button = QPushButton("Play")
        self.controls_layout.addWidget(self.play_button)

        self.position_slider = QSlider(Qt.Horizontal)
        self.position_slider.setRange(0, 1000)
        self.controls_layout.addWidget(self.position_slider)

        self.time_label = QLabel("00:00 / 00:00")
        self.controls_layout.addWidget(self.time_label)

        # Timer for updating slider/time
        self.timer = QTimer(self)
        self.timer.setInterval(500)
        self.timer.timeout.connect(self.update_ui)

        # Layout for video + controls
        self.video_layout = QVBoxLayout()
        self.video_layout.addWidget(self.video_frame)
        self.video_layout.addLayout(self.controls_layout)

        self.video_container = QFrame()
        self.video_container.setLayout(self.video_layout)
        self.video_container.hide()

        split_layout.addWidget(self.video_container, 3)

        # --- Bottom buttons ---
        btn_layout = QHBoxLayout()
        self.export_btn = QPushButton("Export Selected")
        self.close_btn = QPushButton("Close")
        btn_layout.addWidget(self.export_btn)
        btn_layout.addWidget(self.close_btn)
        main_layout.addLayout(btn_layout)

        # --- Signals ---
        self.export_btn.clicked.connect(self.export_selected)
        self.close_btn.clicked.connect(self.close)
        self.tree.doubleClicked.connect(self.preview_selected)
        self.play_button.clicked.connect(self.toggle_playback)
        self.position_slider.sliderMoved.connect(self.set_position)

    def preview_selected(self, index: QModelIndex):
        """Play selected file in VLC preview."""
        if not index.isValid():
            return

        file_path = self.model.filePath(index)
        if not os.path.isfile(file_path) or not file_path.lower().endswith(".mp4"):
            return

        self.video_container.show()
        self.video_frame.show()
        self.video_frame.repaint()
        self.timer.start()

        # VLC needs native window handle
        if sys.platform.startswith("linux"):
            self.player.set_xwindow(self.video_frame.winId())
        elif sys.platform == "win32":
            self.player.set_hwnd(int(self.video_frame.winId()))
        elif sys.platform == "darwin":
            self.player.set_nsobject(int(self.video_frame.winId()))

        media = self.instance.media_new(file_path)
        self.player.set_media(media)
        self.player.play()
        self.play_button.setText("Pause")

    def toggle_playback(self):
        if self.player.is_playing():
            self.player.pause()
            self.play_button.setText("Play")
        else:
            self.player.play()
            self.play_button.setText("Pause")

    def set_position(self, position):
        """Seek to position in media (0–1000 scale)."""
        self.player.set_position(position / 1000.0)

    def update_ui(self):
        """Update slider and time display."""
        if self.player is None:
            return

        length = self.player.get_length()  # in ms
        pos = self.player.get_time()      # in ms

        if length > 0:
            slider_pos = int((pos / length) * 1000)
            self.position_slider.blockSignals(True)
            self.position_slider.setValue(slider_pos)
            self.position_slider.blockSignals(False)

            current_sec = int(pos / 1000)
            total_sec = int(length / 1000)
            self.time_label.setText(
                f"{self.format_time(current_sec)} / {self.format_time(total_sec)}"
            )

    def format_time(self, seconds):
        m, s = divmod(seconds, 60)
        return f"{m:02}:{s:02}"

    def export_selected(self):
        """Export selected video to user-defined location."""
        index = self.tree.currentIndex()
        if not index.isValid():
            QMessageBox.warning(self, "No Selection", "Please select a recording file.")
            return

        file_path = self.model.filePath(index)
        if not os.path.isfile(file_path) or not file_path.lower().endswith(".mp4"):
            QMessageBox.warning(self, "Invalid Selection", "Please select a valid .mp4 file.")
            return

        dest_path, _ = QFileDialog.getSaveFileName(
            self, "Export Recording", os.path.basename(file_path), "Video Files (*.mp4)"
        )

        if dest_path:
            try:
                shutil.copy2(file_path, dest_path)
                QMessageBox.information(self, "Success", f"Exported to:\n{dest_path}")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to export file:\n{e}")
