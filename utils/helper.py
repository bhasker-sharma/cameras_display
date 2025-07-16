import json,os
import datetime
from utils.logging import Logger
import re
from PyQt5.QtCore import QDate, QTime

log = Logger.get_logger(name="Helper", log_file="pipeline1.log")

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
def get_all_recorded_cameras(recordings_root="recordings"):
    """Return a sorted list of all unique camera folder names in recordings."""
    cam_names = set()

    if not os.path.exists(recordings_root):
        return []

    for date_folder in os.listdir(recordings_root):
        date_path = os.path.join(recordings_root, date_folder)
        if not os.path.isdir(date_path):
            continue
        for cam_folder in os.listdir(date_path):
            cam_path = os.path.join(date_path, cam_folder)
            if os.path.isdir(cam_path):
                cam_names.add(cam_folder)

    return sorted(cam_names)

def find_recording_file_for_time_range(cam_name: str, date_str: str, start_time, end_time):
    """
    Find the video file for a camera and date that contains the desired time range.
    Returns: (video_path, metadata_path, recording_start_datetime) or (None, None, None)
    """
    folder_path = os.path.join("recordings", date_str, cam_name)

    if not os.path.exists(folder_path):
        return None, None, None

    # onvert QTime to datetime.time if needed
    if isinstance(start_time, QTime):
        start_time = datetime.time(start_time.hour(), start_time.minute(), start_time.second())
    if isinstance(end_time, QTime):
        end_time = datetime.time(end_time.hour(), end_time.minute(), end_time.second())

    for filename in os.listdir(folder_path):
        if filename.endswith(".mp4"):
            video_path = os.path.join(folder_path, filename)
            metadata_path = video_path.replace(".mp4", "_metadata.json")

            if not os.path.exists(metadata_path):
                continue

            try:
                with open(metadata_path, "r") as f:
                    metadata = json.load(f)

                recording_start = datetime.datetime.fromisoformat(metadata["start_time"])
                duration = metadata.get("duration_seconds", 0)
                recording_end = recording_start + datetime.timedelta(seconds=duration)

                user_start = datetime.datetime.combine(recording_start.date(), start_time)
                user_end = datetime.datetime.combine(recording_start.date(), end_time)

                if recording_start <= user_start and recording_end >= user_end:
                    return video_path, metadata_path, recording_start

            except Exception as e:
                log.warning(f"[Playback] Failed to read metadata: {metadata_path} — {e}")
                continue

    return None, None, None

def get_available_metadata_for_camera(cam_name, date_str):
    folder_path = os.path.join("recordings", date_str, cam_name)
    
    if not os.path.exists(folder_path):
        log.warning(f"[Metadata Debug] Folder does not exist: {folder_path}")
        return

    log.info(f"[Metadata Debug] Scanning metadata in: {folder_path}")
    found = False
    log.info(f"[Metadata Debug] --- Listing all available metadata for {cam_name} on {date_str} ---")

    for filename in os.listdir(folder_path):
        if filename.endswith("_metadata.json"):
            found = True
            meta_path = os.path.join(folder_path, filename)
            try:
                with open(meta_path, "r") as f:
                    meta = json.load(f)
                start_time = meta.get("start_time", "unknown")
                duration = meta.get("duration_seconds", "unknown")
                log.info(f"[Metadata Debug] {filename}: start_time={start_time}, duration={duration}s")
            except Exception as e:
                log.warning(f"[Metadata Debug] Failed to read {filename} — {e}")

    if not found:
        log.info("[Metadata Debug] No metadata files found in folder.")
    log.info(f"[Metadata Debug] --- End of metadata listing ---")
