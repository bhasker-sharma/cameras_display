# camera_app/config/config_manager.py

import os
import json
from utils.logging import log
from utils.paths import get_data_dir

CONFIG_FILE = os.path.join(get_data_dir(), "camera_config.json")

class ConfigManager:
    def __init__(self, config_path=CONFIG_FILE):
        self.config_path = config_path
        self.config = self.load_config()

    def load_config(self):
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, 'r') as f:
                    return json.load(f)
            except Exception:
                log.error(f"Failed to load config: {self.config_path}")
        return {"camera_count": 0}

    def save_config(self):
        try:
            with open(self.config_path, 'w') as f:
                json.dump(self.config, f, indent=4)
        except Exception as e:
            log.error(f"Failed to save config: {str(e)}")

    def get_camera_count(self):
        return self.config.get("camera_count", 0)

    def set_camera_count(self, count):
        self.config["camera_count"] = count
        self.save_config()

    def get_settings_key(self):
        return self.config.get("settings_key", "admin@123")

    def set_settings_key(self, key):
        self.config["settings_key"] = key
        self.save_config()

    def get_recording_folder(self):
        return self.config.get("recording_folder", None)

    def set_recording_folder(self, path):
        self.config["recording_folder"] = path
        self.save_config()

    def get_min_free_gb(self):
        return self.config.get("min_free_gb", 50.0)

    def set_min_free_gb(self, value: float):
        self.config["min_free_gb"] = value
        self.save_config()
