import json,os
import datetime
from utils.logging import log
import re


#this is used to save metadata for the recording used in core/camera_record_worker.py
def save_metadata(path: str, start_time: datetime.datetime, duration_seconds:float = None, end_time: datetime.datetime = None):
    try:
        data = {
            "start_time": start_time.isoformat()
        }
        if end_time is not None:
            data["end_time"] = end_time.isoformat()
        if duration_seconds is not None:
            data["duration_seconds"] = round(duration_seconds, 2)

        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        log.error(f"[Recorder] Failed to write metadata to {path}: {e}")

#this is used to sanetize camera names for file paths and file names so that system does not throw errors
def sanitize_filename(name: str) -> str:
    """Remove or replace invalid characters for filenames (Windows-safe)."""
    name = name.strip().replace(" ", "_")
    return re.sub(r'[<>:"/\\|?*]', '_', name)

#this is used to get the recording enabled cameras from the stream_config.json file
def get_recording_enabled_cameras(json_path="camera_streams.json"):
    """
    Returns dict {sanitized_cam_name: cam_id} for cameras with 'record': true.
    """
    if not os.path.exists(json_path):
        log.error(f"[Helper] stream_config.json not found at {json_path}")
        return {}
    try:
        with open(json_path, "r") as f:
            data = json.load(f)

        valid_cameras = {}
        for cam_id, info in data.items():
            if info.get("record"):
                cam_name = sanitize_filename(info.get("name", f"Camera_{cam_id}"))
                valid_cameras[cam_name] = int(cam_id)

        return valid_cameras
    except Exception as e:
        log.error(f"[Helper] Failed to load cameras: {e}")
        return {}
