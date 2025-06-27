# camera_app/ui/dialogs.py
import vlc
from PyQt5.QtWidgets import (
    QDialog, QLabel, QLineEdit, QComboBox, QPushButton,QTreeWidget,QTreeWidgetItem,QHeaderView,
    QVBoxLayout, QGridLayout, QDialogButtonBox, QTableWidget, QTableWidgetItem, QCheckBox, QWidget, QHBoxLayout,
    QPushButton, QVBoxLayout, QDialogButtonBox, QApplication,QMessageBox,QSizePolicy,QSlider
)
from PyQt5.QtCore import Qt,QTimer
from PyQt5.QtGui import QFont, QImage, QPixmap
import os,sys
from ui.responsive import ScreenScaler
from utils.logging import log
import cv2,json
from datetime import datetime, timedelta


class CameraConfigDialog(QDialog):
    def __init__(self, camera_count, config_manager, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Configure Cameras")
        self.setMinimumSize(1000, 600)
        self.config_manager = config_manager
        self.camera_count = camera_count

        layout = QVBoxLayout()

        main_font = QFont()
        main_font.setPointSize(14)

        label_font = QFont()
        label_font.setPointSize(16)
        label_font.setBold(True)

        # Master control buttons
        master_buttons_layout = QHBoxLayout()
        master_label = QLabel("Master Controls:")
        master_label.setFont(label_font)

        enable_all_btn = QPushButton("Enable All")
        disable_all_btn = QPushButton("Disable All")
        enable_all_btn.setFont(main_font)
        disable_all_btn.setFont(main_font)

        enable_all_btn.setStyleSheet(self.master_button_style())
        disable_all_btn.setStyleSheet(self.master_button_style())

        enable_all_btn.clicked.connect(self.enable_all_cameras)
        disable_all_btn.clicked.connect(self.disable_all_cameras)

        master_buttons_layout.addWidget(master_label)
        master_buttons_layout.addWidget(enable_all_btn)
        master_buttons_layout.addWidget(disable_all_btn)
        master_buttons_layout.addStretch()
        layout.addLayout(master_buttons_layout)

        # Table setup
        self.table = QTableWidget(camera_count, 4)
        self.table.setHorizontalHeaderLabels(["Camera Name", "RTSP URL", "Recording","Enabled"])
        self.table.setFont(main_font)
        self.table.setStyleSheet("""
            QTableWidget {
                background-color: #2c2c2c;
                color: white;
                gridline-color: #555;
                font-size: 14px;
                selection-background-color: transparent;  /* remove blue background */
                selection-color: white;
            }
            QHeaderView::section {
                background-color: #444;
                color: white;
                font-weight: bold;
                padding: 4px;
            }
            QTableWidget::item:selected {
                border: 2px solid white;
            }
            QTableWidget::item:hover {
                background-color: #3c3c3c;
            }
            QTableWidget QLineEdit {
            border: 2px solid white;
            background-color: #2c2c2c;
            color: white;
            padding: 4px;
            }
        """)
        header = self.table.horizontalHeader()
        header.setStretchLastSection(False)  # We’ll control the widths ourselves
        header.setSectionResizeMode(0, self.table.horizontalHeader().ResizeToContents)  # Camera Name → stretch
        header.setSectionResizeMode(1, self.table.horizontalHeader().Stretch)  # RTSP URL → fit contents
        header.setSectionResizeMode(2, self.table.horizontalHeader().ResizeToContents)  # Enabled → fit content
        header.setSectionResizeMode(3, self.table.horizontalHeader().ResizeToContents)
        
        self.enable_buttons = {}
        self.record_buttons = {}

        for row in range(camera_count):
            cam_id = row + 1
            data = self.config_manager.get_camera_config(cam_id)

            # Set minimum row height
            self.table.setRowHeight(row, 50)

            # Camera Name (editable, synced)
            name_value = data.get("name", f"Camera {cam_id}")
            name_item = QTableWidgetItem(name_value)
            name_item.setFont(main_font)
            self.table.setItem(row, 0, name_item)

            # RTSP URL (editable, synced)
            rtsp_value = data.get("rtsp", "")
            rtsp_item = QTableWidgetItem(rtsp_value)
            rtsp_item.setFont(main_font)
            self.table.setItem(row, 1, rtsp_item)

            #  Recording Enabled Button (inside table, synced)
            record_enabled_state = data.get("record",False)
            record_btn = QPushButton()
            record_btn.setCheckable(True)  
            record_btn.setChecked(record_enabled_state)
            record_btn.setText("ON" if record_enabled_state else "OFF")
            record_btn.setFont(main_font)
            record_btn.setMinimumWidth(130)
            record_btn.setMinimumHeight(30)
            record_btn.setStyleSheet(self.button_style(record_enabled_state))
            record_btn.clicked.connect(lambda checked, btn=record_btn : self.toggle_record_button(btn))        

            self.record_buttons[cam_id] = record_btn 

            record_container = QWidget()
            record_layout = QHBoxLayout(record_container)
            record_layout.addWidget(record_btn)
            record_layout.setAlignment(Qt.AlignCenter)
            record_layout.setContentsMargins(0, 0, 0, 0)
            self.table.setCellWidget(row, 2, record_container)

            # Enabled Button (inside table, synced)
            enable_btn = QPushButton()
            enable_btn.setCheckable(True)
            enabled_state = data.get("enabled", False)
            enable_btn.setChecked(enabled_state)
            enable_btn.setText("Enabled" if enabled_state else "Disabled")
            enable_btn.setFont(main_font)
            enable_btn.setMinimumWidth(120)
            enable_btn.setMinimumHeight(30)
            enable_btn.setStyleSheet(self.button_style(enabled_state))
            enable_btn.clicked.connect(lambda checked, btn=enable_btn: self.toggle_button(btn))
            self.enable_buttons[cam_id] = enable_btn

            button_container = QWidget()
            button_layout = QHBoxLayout(button_container)
            button_layout.addWidget(enable_btn)
            button_layout.setAlignment(Qt.AlignCenter)
            button_layout.setContentsMargins(0, 0, 0, 0)  # Ensure no cutting
            self.table.setCellWidget(row, 3, button_container)

        layout.addWidget(self.table)

        # OK/Cancel Buttons
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.setFont(main_font)
        buttons.accepted.connect(self.save_config)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self.setLayout(layout)
        self.center_dialog_on_screen()

    def toggle_button(self, btn):
        btn.setText("Enabled" if btn.isChecked() else "Disabled")
        btn.setStyleSheet(self.button_style(btn.isChecked()))

    def toggle_record_button(self, btn):
        btn.setText("ON" if btn.isChecked() else "OFF")
        btn.setStyleSheet(self.button_style(btn.isChecked()))

    def button_style(self, enabled):
        return f"""
            QPushButton {{
                background-color: {'#007BFF' if enabled else '#555'};
                color: white;
                font-weight: {'bold' if enabled else 'normal'};
                padding: 8px 16px;
                border-radius: 6px;
            }}
        """

    def master_button_style(self):
        return """
            QPushButton {
                background-color: #666;
                color: white;
                font-weight: bold;
                padding: 10px 20px;
                border-radius: 6px;
            }
            QPushButton:hover {
                background-color: #888;
            }
        """

    def enable_all_cameras(self):
        for btn in self.enable_buttons.values(): 
            btn.setChecked(True)
            self.toggle_button(btn)

        for btn in self.record_buttons.values():
            btn.setChecked(True)   
            self.toggle_record_button(btn)

    def disable_all_cameras(self):
        for btn in self.enable_buttons.values():
            btn.setChecked(False)
            self.toggle_button(btn)
        
        for btn in self.record_buttons.values():
            btn.setChecked(False)   
            self.toggle_record_button(btn)

    def save_config(self):
        confirm = QMessageBox.question(
            self,
            "Restart Required",
            "Do you want to restart the system to apply these changes?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if confirm == QMessageBox.Yes:
            for row in range(self.camera_count):
                cam_id = row + 1
                name = self.table.item(row, 0).text()
                rtsp = self.table.item(row, 1).text()
                enabled = self.enable_buttons[cam_id].isChecked()
                record = self.record_buttons[cam_id].isChecked()

                data = {
                    "name": name,
                    "rtsp": rtsp,
                    "enabled": enabled,
                    "record": record
                }
                self.config_manager.set_camera_config(cam_id, data)

            self.accept()

            # Restart the application
            QApplication.quit()
            os.execl(sys.executable, sys.executable, *sys.argv)
        else:
            self.reject()  # Close without saving

    def center_dialog_on_screen(self):
        screen = QApplication.primaryScreen().geometry()
        dialog_geom = self.frameGeometry()
        dialog_geom.moveCenter(screen.center())
        self.move(dialog_geom.topLeft())

class CameraCountDialog(QDialog):
    def __init__(self, valid_camera_counts=None):
        super().__init__()
        self.setWindowTitle("Change camera Count")
        self.setFixedSize(500, 200)

        layout = QVBoxLayout()
        label = QLabel("Choose number of camera to display: ")
        label_font = QFont()
        label_font.setPointSize(13)
        label.setFont(label_font)
        layout.addWidget(label)

        self.combo = QComboBox()
        main_font = QFont()
        main_font.setPointSize(14)
        self.combo.setFont(main_font)
        self.combo.setStyleSheet("""
            QComboBox {                         
                background-color: #333;
                color: white;
                border: 1px solid #555;
                padding: 4px;
                border-radius: 4px;
            }
            QComboBox::drop-down {
                border: 0px;
            }
            QComboBox QAbstractItemView {
                background-color: #333;
                color: white;
            }                
            """)
        valid_counts = valid_camera_counts or [4, 8, 12, 16, 20, 24, 32, 40, 44, 48]
        self.combo.addItems([str(c) for c in valid_counts])
        layout.addWidget(self.combo)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self.setLayout(layout)
        self.center_dialog_on_screen()

    def get_selected_count(self):
        return int(self.combo.currentText())

    def center_dialog_on_screen(self):
        screen = QApplication.primaryScreen().geometry()
        dialog_geom = self.frameGeometry()
        dialog_geom.moveCenter(screen.center())
        self.move(dialog_geom.topLeft())


class PlaybackDialog(QDialog):

    def __init__(self, root_folder="recordings", parent=None):
        super().__init__(parent)
        self.setWindowTitle("Playback Viewer")
        self.root_folder = root_folder
        self.current_video_path = ""
        self.is_playing = True
        self.seeking = False
        self.duration = 0  # in milliseconds
        self.scaler = ScreenScaler()

        # Size and centering
        screen = QApplication.primaryScreen().availableGeometry()
        width = int(screen.width() * 0.6)
        height = int(screen.height() * 0.6)
        self.setMinimumSize(width, height)

        frame = self.frameGeometry()
        frame.moveCenter(screen.center())
        self.move(frame.topLeft())

        # VLC setup
        self.vlc_instance = vlc.Instance()
        self.player = self.vlc_instance.media_player_new()
        self.vlc_timer = QTimer()
        self.vlc_timer.timeout.connect(self.update_slider)

        # Build UI and populate file list
        self.build_ui()
        self.populate_tree()

    def build_ui(self):
        font = QFont()
        font.setPointSize(self.scaler.scale(12))

        # Tree View
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["File/Folder", "Type"])
        self.tree.setFont(font)
        header = self.tree.header()
        header.setFont(font)
        header.setStretchLastSection(True)
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.tree.itemDoubleClicked.connect(self.on_item_double_clicked)

        # Video Display
        self.video_label = QLabel("video preview")
        self.video_label.setAlignment(Qt.AlignCenter)
        self.video_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.video_label.setStyleSheet("background-color: #2c2c2c; color: white")

        # Controls
        self.play_pause_button = QPushButton("⏸")
        self.play_pause_button.setFixedSize(self.scaler.scale(50), self.scaler.scale(50))
        self.play_pause_button.clicked.connect(self.toggle_play_pause)

        self.slider = QSlider(Qt.Horizontal)
        self.slider.sliderPressed.connect(self.pause_for_seek)
        self.slider.sliderReleased.connect(self.seek_video)
        self.slider.sliderMoved.connect(self.preview_slider_position)

        self.time_label = QLabel("00:00 / 00:00")
        self.time_label.setStyleSheet("color: white; font-size: 14px;")

        self.slider_time_label = QLabel("00:00:00 | Timestamp")
        self.slider_time_label.setAlignment(Qt.AlignCenter)
        self.slider_time_label.setStyleSheet("color: #aaa; font-size: 12px;")

        # Layouts
        slider_box = QVBoxLayout()
        slider_box.addWidget(self.slider_time_label)
        slider_box.addWidget(self.slider)

        control_box = QHBoxLayout()
        control_box.addStretch()
        control_box.addWidget(self.play_pause_button)
        control_box.addLayout(slider_box, 5)
        control_box.addWidget(self.time_label)
        control_box.addStretch()

        video_box = QVBoxLayout()
        video_box.addWidget(self.video_label)
        video_box.addLayout(control_box)

        main_box = QHBoxLayout()
        main_box.addWidget(self.tree, 2)
        container = QLabel()
        container.setLayout(video_box)
        main_box.addWidget(container, 5)

        layout = QVBoxLayout()
        layout.setContentsMargins(
            self.scaler.scale(10),
            self.scaler.scale(10),
            self.scaler.scale(10),
            self.scaler.scale(10)
        )
        layout.addLayout(main_box)
        self.setLayout(layout)

    def populate_tree(self):
        self.tree.clear()
        if not os.path.exists(self.root_folder):
            QMessageBox.warning(self, "Missing Folder", f"No recordings found in: {self.root_folder}")
            return
        self.add_items(self.tree.invisibleRootItem(), self.root_folder)

    def add_items(self, parent_item, folder_path):
        for name in sorted(os.listdir(folder_path)):
            full_path = os.path.join(folder_path, name)
            if os.path.isdir(full_path):
                item = QTreeWidgetItem(parent_item, [name, "Folder"])
                self.add_items(item, full_path)
            elif name.endswith((".avi", ".mp4")):
                item = QTreeWidgetItem(parent_item, [name, "Video"])
                item.setData(0, Qt.UserRole, full_path)

    def on_item_double_clicked(self, item, column):
        if item.text(1) == "Video":
            path = item.data(0, Qt.UserRole)
            self.start_video(path)

    def start_video(self, path):
        if self.player.is_playing():
            self.player.stop()

        self.media = self.vlc_instance.media_new(path)
        self.player.set_media(self.media)
        if sys.platform.startswith("win"):
            self.player.set_hwnd(int(self.video_label.winId()))
        else:
            self.player.set_xwindow(self.video_label.winId())
        self.player.play()
        self.current_video_path = path
        self.is_playing = True
        self.play_pause_button.setText("⏸")

        # Delay to allow VLC to fetch metadata (like duration)
        QTimer.singleShot(1500, self.setup_slider)   

    def setup_slider(self):  
        if not self.media:
            return

        def finalize_slider():
            self.duration = self.media.get_duration()
            if self.duration <= 0:
                QTimer.singleShot(1000, self.setup_slider)
                return

            self.slider.setRange(0, self.duration)
            self.slider.setValue(0)
            self.vlc_timer.start(500)

        # Try parsing the media info
        parsed = self.media.get_state() in [vlc.State.Opening, vlc.State.Buffering, vlc.State.NothingSpecial]
        if parsed:
            self.media.parse_with_options(vlc.MediaParseFlag.local, timeout=5)
        
        QTimer.singleShot(1000, finalize_slider)

    def format_time(self, seconds):
        minutes = int(seconds // 60)
        seconds = int(seconds % 60)
        return f"{minutes:02}:{seconds:02}"

    def pretty_timestamp(self, seconds):
        ts = timedelta(seconds=int(seconds))
        return str(ts) + " | Timestamp"
    
    def toggle_play_pause(self):
        if self.player.is_playing():
            self.player.pause()
            self.play_pause_button.setText("▶")
            self.is_playing = False
        else:
            self.player.play()
            self.play_pause_button.setText("⏸")
            self.is_playing = True

    
    def pause_for_seek(self):
        self.seeking = True
        self.vlc_timer.stop()

    def seek_video(self):
        self.seeking = False
        self.player.set_time(self.slider.value())  # in ms
        if self.is_playing:
            self.vlc_timer.start(500)

    def preview_slider_position(self, value):
        seconds = value // 1000
        self.time_label.setText(f"{self.format_time(seconds)} / {self.format_time(self.duration // 1000)}")
        self.slider_time_label.setText(self.pretty_timestamp(seconds))

    def update_slider(self):
        if not self.seeking:
            position = self.player.get_time()  # in ms
            self.slider.blockSignals(True)
            self.slider.setValue(position)
            self.slider.blockSignals(False)

            seconds = position // 1000
            self.time_label.setText(f"{self.format_time(seconds)} / {self.format_time(self.duration // 1000)}")
            self.slider_time_label.setText(self.pretty_timestamp(seconds))
