# camera_app/ui/dialogs.py
import vlc
from PyQt5.QtWidgets import (
    QDialog, QLabel, QLineEdit, QComboBox, QPushButton,QTreeWidget,QTreeWidgetItem,QHeaderView,
    QVBoxLayout, QGridLayout, QDialogButtonBox, QTableWidget, QTableWidgetItem, QCheckBox, QWidget, QHBoxLayout,
    QPushButton, QVBoxLayout, QDialogButtonBox, QApplication,QMessageBox,QSizePolicy,QSlider,QStyle
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
        self.scaler = ScreenScaler()
        self.vlc_instance = vlc.Instance()
        self.player = self.vlc_instance.media_player_new()
        self.media = None
        self.manual_duration = 0        # duration in ms
        self.user_seeking = False       # whether user is dragging
        self.slider_position_ms = 0     # current slider target
        self.fps = 25                   # fallback if FPS isn't found
        self.last_frame_limit_ms = 0    # upper seek limit for in-progress files

        log.debug("[PlaybackDialog] Initializing UI")
        self.init_ui()
        self.populate_tree()
        self.resize_to_screen()

    def init_ui(self):
        layout = QHBoxLayout()
        self.setLayout(layout)

        # Left: Folder tree (unchanged)
        self.tree = QTreeWidget()
        self.tree.setHeaderLabel("Recorded Files")
        self.tree.itemDoubleClicked.connect(self.play_video_from_item)
        layout.addWidget(self.tree, 2)

        # Right: Video player
        player_layout = QVBoxLayout()

        self.video_frame = QLabel("No video selected")
        self.video_frame.setStyleSheet("background-color: black;")
        self.video_frame.setMinimumHeight(self.scaler.scale_h(300))
        self.video_frame.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        player_layout.addWidget(self.video_frame)

        # New compact control layout (slider + play + time) in one line
        bottom_controls = QHBoxLayout()

        # Play/Pause icon button
        self.play_button = QPushButton()
        self.play_button.setFixedSize(32, 32)
        self.play_button.setIcon(self.style().standardIcon(QStyle.SP_MediaPlay))
        self.play_button.clicked.connect(self.toggle_play_pause)
        bottom_controls.addWidget(self.play_button)

        # Slider
        self.slider = QSlider(Qt.Horizontal)
        self.slider.setRange(0, 1000)
        self.slider.sliderPressed.connect(self.start_seeking)
        self.slider.sliderReleased.connect(self.finish_seeking)
        self.slider.sliderMoved.connect(self.while_seeking)

        bottom_controls.addWidget(self.slider, stretch=1)

        # Time label
        self.time_label = QLabel("00:00 / 00:00")
        self.time_label.setStyleSheet("color: white;")
        bottom_controls.addWidget(self.time_label)

        player_layout.addLayout(bottom_controls)
        layout.addLayout(player_layout, 5)

        # Timer for VLC sync
        self.vlc_timer = QTimer()
        self.vlc_timer.setInterval(500)
        self.vlc_timer.timeout.connect(self.update_ui)


    def resize_to_screen(self):
        screen = QApplication.primaryScreen().availableGeometry()
        width = int(screen.width() * 0.6)
        height = int(screen.height() * 0.6)
        self.setMinimumSize(width, height)
        self.move(screen.center() - self.rect().center())
        log.debug(f"[PlaybackDialog] Resized to {width}x{height}")

    def populate_tree(self):
        self.tree.clear()
        log.debug("[PlaybackDialog] Populating tree view")
        for root, dirs, files in os.walk(self.root_folder):
            relative_path = os.path.relpath(root, self.root_folder)
            parts = [] if relative_path == "." else relative_path.split(os.sep)

            parent = self.tree
            current_item = None

            for part in parts:
                found = False
                for i in range(parent.topLevelItemCount() if isinstance(parent, QTreeWidget) else parent.childCount()):
                    item = parent.topLevelItem(i) if isinstance(parent, QTreeWidget) else parent.child(i)
                    if item.text(0) == part:
                        current_item = item
                        parent = item
                        found = True
                        break

                if not found:
                    new_item = QTreeWidgetItem([part])
                    if isinstance(parent, QTreeWidget):
                        parent.addTopLevelItem(new_item)
                    else:
                        parent.addChild(new_item)
                    current_item = new_item
                    parent = new_item

            for f in files:
                if f.endswith(".avi") or f.endswith(".mp4"):
                    file_item = QTreeWidgetItem([f])
                    file_item.setData(0, Qt.UserRole, os.path.join(root, f))
                    parent.addChild(file_item)

    def play_video_from_item(self, item, column):
        filepath = item.data(0, Qt.UserRole)
        if not filepath or not filepath.endswith((".avi", ".mp4")):
            return
        
        self.media = self.vlc_instance.media_new(filepath)
        self.player.set_media(self.media)
        self.manual_duration = 0
        self.last_frame_limit_ms = 0

        log.info(f"[PlaybackDialog] Playing: {filepath}")
        self.media = self.vlc_instance.media_new(filepath)
        self.player.set_media(self.media)

        json_path = filepath.replace(".avi", ".json").replace(".mp4", ".json")
        if os.path.exists(json_path):
            try:
                with open(json_path, "r") as f:
                    meta = json.load(f)
                    if "start_time" in meta and "end_time" in meta:
                        fmt = "%Y-%m-%d %H:%M:%S"
                        start = datetime.strptime(meta["start_time"], fmt)
                        end = datetime.strptime(meta["end_time"], fmt)
                        self.manual_duration = int((end - start).total_seconds() * 1000)
                    elif "start_time" in meta and os.path.exists(filepath):
                        # Get frame count and FPS to calculate in-progress duration
                        cap = cv2.VideoCapture(filepath)
                        frames = cap.get(cv2.CAP_PROP_FRAME_COUNT)
                        fps = cap.get(cv2.CAP_PROP_FPS)
                        cap.release()
                        fps = fps if 0 < fps < 60 else 25
                        self.fps = fps
                        self.manual_duration = int(frames / fps * 1000)
                        self.last_frame_limit_ms = self.manual_duration
            except Exception as e:
                log.warning(f"[PlaybackDialog] Failed to parse recording metadata: {e}")

        # Attach to screen
        if sys.platform.startswith("linux"):
            self.player.set_xwindow(self.video_frame.winId())
        elif sys.platform == "win32":
            self.player.set_hwnd(int(self.video_frame.winId()))

        self.player.play()
        self.play_button.setIcon(self.style().standardIcon(QStyle.SP_MediaPause))
        self.vlc_timer.start()

    def toggle_play_pause(self):
        if not self.player:
            return

        state = self.player.get_state()
        log.debug(f"[PlaybackDialog] toggle_play_pause state = {state}")

        if state == vlc.State.Playing:
            self.player.pause()
            self.play_button.setIcon(self.style().standardIcon(QStyle.SP_MediaPlay))
        elif state in (vlc.State.Paused, vlc.State.Stopped):
            self.player.play()
            self.play_button.setIcon(self.style().standardIcon(QStyle.SP_MediaPause))
        elif state == vlc.State.Ended:
            self.player.stop()
            self.player.play()
            self.play_button.setIcon(self.style().standardIcon(QStyle.SP_MediaPause))

    def handle_slider_release(self):
        if not self.player or not self.player.get_media():
            return

        new_position = self.slider.value() / 1000.0
        self.player.set_position(new_position)
        log.debug(f"[PlaybackDialog] Slider released -> position = {new_position:.2f}")

        if self.player.get_state() in (vlc.State.Ended, vlc.State.Stopped):
            self.player.play()
            self.play_button.setIcon(self.style().standardIcon(QStyle.SP_MediaPause))
            
    def update_ui(self):
        if not self.player or not self.player.get_media():
            log.debug("[PlaybackDialog] update_ui skipped: No player/media")
            return

        state = self.player.get_state()
        log.debug(f"[PlaybackDialog] update_ui state: {state}")

        if state == vlc.State.Ended:
            self.play_button.setIcon(self.style().standardIcon(QStyle.SP_MediaPlay))
            log.debug("[PlaybackDialog] update_ui: Video ended")
            return

        if state not in (vlc.State.Playing, vlc.State.Paused):
            log.debug("[PlaybackDialog] update_ui: Skipping — state is not playing/paused")
            return

        length = self.player.get_length()
        pos = self.player.get_time()
        log.debug(f"[PlaybackDialog] Raw VLC time — pos={pos}, length={length}")
              
        # Fallback: use JSON metadata duration
        if length <= 0 and hasattr(self, 'manual_duration') and self.manual_duration > 0:
            length = self.manual_duration
            
        # Clamp duration for live video (in-progress)
        if self.last_frame_limit_ms > 0:
            length = self.last_frame_limit_ms
            if pos > self.last_frame_limit_ms:
                self.player.set_pause(1)

        if length > 0 and pos >= 0 and not self.user_seeking:
            self.slider.blockSignals(True)
            self.slider.setValue(int((pos / length) * 1000))
            self.slider.blockSignals(False)

            formatted = f"{self.ms_to_time(pos)} / {self.ms_to_time(length)}"
            self.time_label.setText(formatted)
            log.debug(f"[PlaybackDialog] Time updated: {formatted}")
        else:
            log.debug("[PlaybackDialog] Skipped time update — length or pos invalid")
    
    def ms_to_time(self, ms):
        seconds = ms // 1000
        mins, secs = divmod(seconds, 60)
        hrs, mins = divmod(mins, 60)
        return f"{hrs:02}:{mins:02}:{secs:02}"

    def start_seeking(self):
        self.user_seeking = True
        self.player.set_pause(1)  # pause while dragging

    def while_seeking(self, val):
        if self.manual_duration > 0:
            self.slider_position_ms = int((val / 1000.0) * self.manual_duration)
            self.time_label.setText(f"{self.ms_to_time(self.slider_position_ms)} / {self.ms_to_time(self.manual_duration)}")

    def finish_seeking(self):
        self.user_seeking = False
        if self.manual_duration > 0:
            seek_ratio = self.slider.value() / 1000.0
            seek_ms = int(seek_ratio * self.manual_duration)

            # Clamp to last known safe frame
            if self.last_frame_limit_ms > 0:
                seek_ms = min(seek_ms, self.last_frame_limit_ms)

            self.player.set_time(seek_ms)
            self.play_button.setIcon(self.style().standardIcon(QStyle.SP_MediaPause))
            self.player.set_pause(0)
            log.debug(f"[PlaybackDialog] Seeking to {seek_ms} ms")