# ui/playbackdialog.py
import os
import shutil
import vlc
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout,
    QPushButton, QFileSystemModel, QTreeView,
    QFileDialog, QMessageBox
)
from PyQt5.QtCore import QModelIndex
from PyQt5.QtWidgets import QWidget
import sys



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
        # File system model
        self.model = QFileSystemModel()
        self.model.setRootPath(self.recordings_dir)
        self.model.setNameFilters(["*.mp4"])
        self.model.setNameFilterDisables(False)
        # File system view
        self.tree = QTreeView()
        self.tree.setModel(self.model)
        self.tree.setRootIndex(self.model.index(self.recordings_dir))
        self.tree.setColumnWidth(0, 300)
        self.tree.setAlternatingRowColors(True)
        self.tree.setSortingEnabled(True)
        self.tree.setRootIsDecorated(True)
        self.tree.setItemsExpandable(True)

        # VLC video frame
        self.video_frame = QWidget(self)
        self.video_frame.setMinimumHeight(400)
        self.video_frame.hide()
        # ✅ VLC player setup
        self.instance = vlc.Instance()
        self.player = self.instance.media_player_new()
        split_layout.addWidget(self.tree, 2)
        split_layout.addWidget(self.video_frame, 3)

        # Buttons at bottom
        btn_layout = QHBoxLayout()
        self.export_btn = QPushButton("Export Selected")
        self.close_btn = QPushButton("Close")
        btn_layout.addWidget(self.export_btn)
        btn_layout.addWidget(self.close_btn)

        main_layout.addLayout(btn_layout)

        # Connections
        self.export_btn.clicked.connect(self.export_selected)
        self.close_btn.clicked.connect(self.close)
        self.tree.doubleClicked.connect(self.preview_selected)

    def preview_selected(self, index: QModelIndex):
        """Play the selected file using VLC."""
        if not index.isValid():
            return

        file_path = self.model.filePath(index)
        if not os.path.isfile(file_path) or not file_path.lower().endswith(".mp4"):
            return

        self.video_frame.show()

        # Set the video output to the QWidget
        if sys.platform.startswith('linux'):  # for Linux using the X Server
            self.player.set_xwindow(self.video_frame.winId())
        elif sys.platform == "win32":  # for Windows
            self.player.set_hwnd(self.video_frame.winId())
        elif sys.platform == "darwin":  # for MacOS
            self.player.set_nsobject(int(self.video_frame.winId()))

        media = self.instance.media_new(file_path)
        self.player.set_media(media)
        self.player.play()

    def export_selected(self):
        """Export selected file to user-chosen destination."""
        index: QModelIndex = self.tree.currentIndex()
        if not index.isValid():
            QMessageBox.warning(self, "No Selection", "Please select a recording file.")
            return

        file_path = self.model.filePath(index)
        if not os.path.isfile(file_path) or not file_path.lower().endswith(".mp4"):
            QMessageBox.warning(self, "Invalid Selection", "Please select a valid .mp4 file.")
            return

        dest_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Recording",
            os.path.basename(file_path),
            "Video Files (*.mp4)"
        )

        if dest_path:
            try:
                shutil.copy2(file_path, dest_path)
                QMessageBox.information(self, "Success", f"Exported to:\n{dest_path}")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to export file:\n{e}")
