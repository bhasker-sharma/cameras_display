# 🎥 Multi-Camera Streaming, Recording & Playback Software

A **PyQt5-based desktop application** for real-time **camera monitoring**, **recording**, and **playback**.  
Built for industrial monitoring setups with support for **RTSP cameras**, **multi-window grids (4–48 cams)**, and **hourly recording with metadata**.

---

## ✨ Features
- 📡 **Live Streaming**
  - RTSP camera feeds with auto-reconnect.
  - Adjustable grid layouts (4 → 48 cameras).
  - Double-click any camera → fullscreen focus mode.

- 🎬 **Recording**
  - Continuous recording using **FFmpeg**.
  - Automatic **hourly file split** with metadata (`start_time`, `end_time`, `duration`).
  - Organized folder structure: `recordings/YYYY_MM_DD/Camera_Name`.

- 🎞 **Playback & Export**
  - Built-in **VLC-based player** to preview recordings.
  - File tree explorer to browse by date/camera.
  - Export selected videos to another location.

- ⚙️ **Configuration**
  - Add/rename cameras, set RTSP URLs.
  - Enable/disable streaming & recording per camera.
  - Bulk **Enable All / Disable All** controls.
  - Export/Import config as **CSV** or **PDF report**.

- 🎨 **UI/UX**
  - Dark theme with responsive scaling.
  - Status indicators (Connected ✅, Error ❌, Disabled ⚠️).
  - Automatic reconnect for disconnected cameras.

- 📝 **Logging**
  - Centralized logging system (`logs/` folder).
  - Separate logs for streaming, recording, and playback events.

---

## 🛠 Tech Stack
- **Language**: Python 3
- **GUI Framework**: PyQt5
- **Video Processing**: FFmpeg, OpenCV, python-vlc
- **Storage**: JSON config + structured file system
- **Logging**: Python `logging` module

---

## 📂 Project Structure


camera_app/
│
├── main.py                         # Entry point
├── assets/                         # Icons, logo
│
├── config/
│ ├── config_manager.py             # Camera count config
│ └── stream_config_manager.py      # Per-camera RTSP config
│
├── core/
│ ├── camera_stream_worker.py       # Live streaming (FFmpeg → frames)
│ ├── camera_record_worker.py       # Recording (FFmpeg → MP4 + metadata)
│ └── camera_playback_worker.py     # Playback dialog (VLC)
│
├── ui/
│ ├── camera_window.py              # Main window layout (grid + navbar)
│ ├── camera_widget.py              # Individual camera widget
│ ├── dialogs.py                    # Config dialogs (CSV/PDF export, import)
│ ├── responsive.py                 # Screen scaler
│ └── styles.py                     # Dark theme styling
│
├── controller/
│ └── app_controller.py             # Orchestrates UI + config + recording
│
└── utils/
    ├── helper.py                   # Metadata saving, sanitization, helpers
    └── logging.py                  # Central logger


---

## 🚀 Getting Started

### 1. Clone the repository

git clone <your-repo-url>
cd camera_app

--- make the environemnt and ctivate it
    
    python -m venv env
    # Activate
        # On Windows:
        .\env\Scripts\activate

    #install requirements 
        pip install requirements.txt



