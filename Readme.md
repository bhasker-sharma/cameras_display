camera_app/
│
├── main.py                          # Entry point of the app
├── assets/                          # Images, icons, etc.
│   └── logo.png
│
├── config/                          # Configuration loading/saving
│   ├── config_manager.py            # Handles camera count config
│   └── stream_config_manager.py     # Handles camera stream URLs and states
│
├── core/                            # Backend logic and threads
│   └── camera_stream_worker.py      # Camera thread for RTSP stream capture
│
├── ui/                              # GUI components and layout
│   ├── camera_widget.py             # Individual camera widget
│   ├── camera_window.py             # Main camera window layout
│   ├── dialogs.py                   # Camera count and config dialogs
│   └── styles.py                    # Centralized dark theme/style
│
├── controller/
│   └── app_controller.py            # Orchestrates config, UI, and state
│
└── utils/
    └── logging.py                   # Logging setup / fallback logger




https://chatgpt.com/share/6825e10a-0c08-8000-8359-b063c6002daa

commands to make the enviornment and activate it 

* python -m venv env


Software flow :
main.py
│
├── Starts QApplication
│
└── AppController
    ├── Loads config files
    ├── Initializes windows
    │
    └── CameraWindow (UI)
        ├── Top Navbar (QHBoxLayout)
        │   ├── [Change Camera Count] ──► AppController.change_camera_count()
        │   ├── [Configure Camera] ────► AppController.open_camera_config()
        │   └── [New: Playback Button] ─► AppController.open_playback_dialog()
        │
        └── Grid Layout (QGridLayout)
            ├── CameraWidget 1
            ├── CameraWidget 2
            ├── ...
            └── CameraWidget N
