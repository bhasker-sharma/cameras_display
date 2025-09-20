# camera_app/ui/dialogs.py
from PyQt5.QtMultimedia import QMediaPlayer, QMediaContent
from PyQt5.QtMultimediaWidgets import QVideoWidget
from PyQt5.QtCore import QUrl
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
import json
from datetime import datetime, timedelta
from PyQt5.QtWidgets import QFileDialog, QMessageBox
import csv
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph,Image, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from datetime import datetime

class CameraConfigDialog(QDialog):
    def __init__(self, camera_count, config_manager,controller = None, parent=None ):
        super().__init__(parent)
        self.controller = controller
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
        
        #create a horizontal row fro buttons
        button_row_layout = QHBoxLayout()
        
        # OK/Cancel Buttons
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.setFont(main_font)
        buttons.accepted.connect(self.save_config)
        buttons.rejected.connect(self.reject)
        
        # Add export import  buttons
        export_import_box = QDialogButtonBox()
        export_import_box.setFont(main_font)
        export_btn = export_import_box.addButton("Export CSV", QDialogButtonBox.ActionRole)
        import_btn = export_import_box.addButton("Import CSV", QDialogButtonBox.ActionRole)
        export_btn.setFont(main_font)
        import_btn.setFont(main_font)
        
        export_btn.clicked.connect(self.export_config)
        import_btn.clicked.connect(self.import_csv)
        
        # Add to layout: left, stretch, right
        button_row_layout.addWidget(buttons)
        button_row_layout.addStretch()
        button_row_layout.addWidget(export_import_box)
                
        layout.addLayout(button_row_layout)
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
            if self.controller:
                self.controller.stop_all_recordings()
            QApplication.quit()
            os.execl(sys.executable, sys.executable, *sys.argv)
        else:
            self.reject()  # Close without saving

    def center_dialog_on_screen(self):
        screen = QApplication.primaryScreen().geometry()
        dialog_geom = self.frameGeometry()
        dialog_geom.moveCenter(screen.center())
        self.move(dialog_geom.topLeft())

    def export_config(self):

        path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Camera Configuration",
            "system_configuration.csv",
            "CSV Files (*.csv);;PDF Files (*.pdf)"
        )
        if not path:
            return  # user cancelled

        try:
            if path.lower().endswith(".csv"):
                # --- Export CSV ---
                with open(path, "w", newline="", encoding="utf-8") as f:
                    writer = csv.writer(f)
                    writer.writerow(["CameraID", "Name", "RTSP", "Record", "Enabled"])
                    for row in range(self.camera_count):
                        cam_id = row + 1
                        name = self.table.item(row, 0).text()
                        rtsp = self.table.item(row, 1).text()
                        record = self.record_buttons[cam_id].isChecked()
                        enabled = self.enable_buttons[cam_id].isChecked()
                        writer.writerow([cam_id, name, rtsp, record, enabled])
                QMessageBox.information(self, "Export Successful", f"Configuration exported to:\n{path}")
            
            # ---Export PDF ---
            elif path.lower().endswith(".pdf"):
                # --- Header section ---

                styles = getSampleStyleSheet()

                # --- Header Styles ---
                title_style = ParagraphStyle(
                    "ReportTitle",
                    parent=styles["Heading1"],
                    alignment=TA_CENTER,
                    fontSize=16,
                    textColor=colors.black,
                    spaceAfter=6,
                )
                subtitle_style = ParagraphStyle(
                    "SubTitle",
                    parent=styles["Normal"],
                    alignment=TA_CENTER,
                    fontSize=12,
                    textColor=colors.darkgray,
                    spaceAfter=12,
                )
                right_style = ParagraphStyle(
                    "RightAlign",
                    parent=styles["Normal"],
                    alignment=TA_RIGHT,
                    fontSize=9,
                    textColor=colors.grey,
                )

                # --- Logo ---
                logo_path = "assets/logo.png"
                if os.path.exists(logo_path):
                    logo = Image(logo_path, width=50, height=50)  # bigger logo
                else:
                    logo = Paragraph("", styles["Normal"])

                # --- Title & Timestamp ---
                title = Paragraph("TIPL – Camera Configuration Report", title_style)
                timestamp = Paragraph(datetime.now().strftime("%d-%m-%Y %H:%M:%S"), right_style)

                header_table = Table([[logo, title, timestamp]], colWidths=[60, 380, 140])
                header_table.setStyle(TableStyle([
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("ALIGN", (0, 0), (0, 0), "LEFT"),
                    ("ALIGN", (1, 0), (1, 0), "CENTER"),
                    ("ALIGN", (2, 0), (2, 0), "RIGHT"),
                ]))

                # --- Data Table ---
                data = [["CameraID", "Name", "RTSP", "Record", "Enabled"]]
                for row in range(self.camera_count):
                    cam_id = row + 1
                    name = self.table.item(row, 0).text()
                    rtsp = self.table.item(row, 1).text()
                    record = "ON" if self.record_buttons[cam_id].isChecked() else "OFF"
                    enabled = "Enabled" if self.enable_buttons[cam_id].isChecked() else "Disabled"
                    data.append([cam_id, name, rtsp, record, enabled])

                table = Table(data, repeatRows=1)  # repeat header on each page
                style = TableStyle([
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2c3e50")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                    ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, 0), 11),
                    ("BOTTOMPADDING", (0, 0), (-1, 0), 10),
                    ("BACKGROUND", (0, 1), (-1, -1), colors.beige),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
                ])
                table.setStyle(style)

                # --- Signature Line at Bottom ---
                signature = Paragraph("<br/><br/><br/>Verified By: ___________________________", styles["Normal"])

                # --- Build PDF ---
                doc = SimpleDocTemplate(path, pagesize=letter)
                elements = [
                    header_table,
                    Spacer(1, 8),
                    Spacer(1, 8),
                    table,
                    Spacer(1, 20),
                    signature,
                ]
                doc.build(elements)
                QMessageBox.information(self, "Export Successful", f"Configuration exported to:\n{path}")
            else:
                QMessageBox.warning(self, "Export Failed", "Unsupported file format selected.")

        except Exception as e:
            QMessageBox.critical(self, "Export Failed", str(e))
            
        
    def import_csv(self):
        from PyQt5.QtWidgets import QFileDialog, QMessageBox
        import csv

        path, _ = QFileDialog.getOpenFileName(
            self,
            "Import Camera Configuration",
            "",
            "CSV Files (*.csv);;All Files (*)"
        )
        if not path:
            return  # user cancelled

        try:
            with open(path, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    cam_id = int(row["CameraID"])
                    if cam_id > self.camera_count:
                        continue

                    # Update table values
                    self.table.setItem(cam_id-1, 0, QTableWidgetItem(row["Name"]))
                    self.table.setItem(cam_id-1, 1, QTableWidgetItem(row["RTSP"]))

                    # Update record button
                    record_state = row["Record"].lower() == "true"
                    btn = self.record_buttons[cam_id]
                    btn.setChecked(record_state)
                    self.toggle_record_button(btn)

                    # Update enable button
                    enabled_state = row["Enabled"].lower() == "true"
                    btn2 = self.enable_buttons[cam_id]
                    btn2.setChecked(enabled_state)
                    self.toggle_button(btn2)

            QMessageBox.information(self, "Import Successful", f"Configuration imported from:\n{path}")
        except Exception as e:
            QMessageBox.critical(self, "Import Failed", str(e))
        
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

