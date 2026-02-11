import json,os
import datetime
import subprocess
from utils.logging import Logger
import re
from PyQt5.QtCore import QDate, QTime
from utils.subproc import win_no_window_kwargs

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
    log.info(f"[Debug] Looking for video in: {folder_path}")

    if not os.path.exists(folder_path):
        log.info(f"[Debug] Folder does not exist: {folder_path}")
        return None, None, None

    # onvert QTime to datetime.time if needed
    if isinstance(start_time, QTime):
        start_time = datetime.time(start_time.hour(), start_time.minute(), start_time.second())
    if isinstance(end_time, QTime):
        end_time = datetime.time(end_time.hour(), end_time.minute(), end_time.second())

    log.info(f"[Debug] Looking for time range: {start_time} to {end_time}")

    for filename in os.listdir(folder_path):
        if filename.endswith(".mp4"):
            log.info(f"[Debug] Checking video file: {filename}")
            video_path = os.path.join(folder_path, filename)
            metadata_path = video_path.replace(".mp4", "_metadata.json")

            if not os.path.exists(metadata_path):
                log.info(f"[Debug] Metadata not found: {metadata_path}")
                continue

            try:
                with open(metadata_path, "r") as f:
                    metadata = json.load(f)

                recording_start = datetime.datetime.fromisoformat(metadata["start_time"])
                duration = metadata.get("duration_seconds", 0)
                recording_end = recording_start + datetime.timedelta(seconds=duration)

                user_start = datetime.datetime.combine(recording_start.date(), start_time)
                user_end = datetime.datetime.combine(recording_start.date(), end_time)

                log.info(f"[Debug] Recording: {recording_start} to {recording_end}")
                log.info(f"[Debug] User range: {user_start} to {user_end}")
                
                # Check for overlap instead of containment
                # Overlap exists if: user_start < recording_end AND user_end > recording_start
                overlaps = user_start < recording_end and user_end > recording_start
                log.info(f"[Debug] Check overlap: user_start < recording_end? {user_start < recording_end}")
                log.info(f"[Debug] Check overlap: user_end > recording_start? {user_end > recording_start}")
                log.info(f"[Debug] Overlaps? {overlaps}")

                if overlaps:
                    log.info(f"[Debug] MATCH FOUND: {video_path}")
                    return video_path, metadata_path, recording_start
                else:
                    log.info(f"[Debug] No overlap for {filename}")

            except Exception as e:
                log.warning(f"[Playback] Failed to read metadata: {metadata_path} — {e}")
                continue

    log.info(f"[Debug] No matching video found in {folder_path}")
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


def _get_mp4_duration_seconds(video_path):
    """Use ffprobe to get the duration of an MP4 file in seconds."""
    try:
        cmd = [
            "ffprobe", "-v", "quiet",
            "-print_format", "json",
            "-show_format",
            video_path
        ]
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            stdin=subprocess.DEVNULL,
            **win_no_window_kwargs()
        )
        if result.returncode == 0:
            info = json.loads(result.stdout)
            return float(info["format"]["duration"])
    except Exception as e:
        log.warning(f"[Metadata Cleanup] ffprobe failed for {video_path}: {e}")
    return None


def fix_orphaned_metadata(recordings_root="recordings"):
    """
    Scan all metadata files and fix ones missing duration_seconds.
    This happens when the app crashes or is closed without stopping recordings.
    Calculates duration from the MP4 file using ffprobe.
    """
    if not os.path.exists(recordings_root):
        return

    fixed = 0
    for date_folder in os.listdir(recordings_root):
        date_path = os.path.join(recordings_root, date_folder)
        if not os.path.isdir(date_path):
            continue
        for cam_folder in os.listdir(date_path):
            cam_path = os.path.join(date_path, cam_folder)
            if not os.path.isdir(cam_path):
                continue
            for filename in os.listdir(cam_path):
                if not filename.endswith("_metadata.json"):
                    continue
                meta_path = os.path.join(cam_path, filename)
                try:
                    with open(meta_path, "r", encoding="utf-8") as f:
                        meta = json.load(f)
                    if meta.get("duration_seconds") is not None:
                        continue  # already has duration, skip

                    # Find the corresponding MP4
                    video_file = filename.replace("_metadata.json", ".mp4")
                    video_path = os.path.join(cam_path, video_file)
                    if not os.path.exists(video_path):
                        continue

                    duration = _get_mp4_duration_seconds(video_path)
                    if duration is None or duration <= 0:
                        continue

                    start_time = datetime.datetime.fromisoformat(meta["start_time"])
                    end_time = start_time + datetime.timedelta(seconds=duration)
                    meta["duration_seconds"] = round(duration, 2)
                    meta["end_time"] = end_time.isoformat()

                    with open(meta_path, "w", encoding="utf-8") as f:
                        json.dump(meta, f, indent=2)
                    fixed += 1
                    log.info(f"[Metadata Cleanup] Fixed: {meta_path} → duration={duration:.2f}s")

                except Exception as e:
                    log.warning(f"[Metadata Cleanup] Error processing {meta_path}: {e}")

    if fixed > 0:
        log.info(f"[Metadata Cleanup] Fixed {fixed} orphaned metadata file(s).")
