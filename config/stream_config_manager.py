# camera_app/config/stream_config_manager.py

import os
import json
from utils.logging import log

CAMERA_STREAM_FILE = "camera_streams.json"

class CameraStreamConfigManager:
    def __init__(self, config_path=CAMERA_STREAM_FILE):
        self.config_path = config_path
        self.config = self.load_config()

    def load_config(self):
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, 'r') as f:
                    return json.load(f)
            except Exception as e:
                log.error(f"Failed to load camera stream config: {self.config_path} -> {e}")
        return {}

    def save_config(self):
        try:
            with open(self.config_path, 'w') as f:
                json.dump(self.config, f, indent=4)
        except Exception as e:
            log.error(f"Failed to save camera stream config: {str(e)}")

    def get_camera_config(self, cam_id):
        return self.config.get(str(cam_id), {})

    def set_camera_config(self, cam_id, data):
        self.config[str(cam_id)] = data
        self.save_config()
