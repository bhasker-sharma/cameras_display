import os
import shutil
import threading
import datetime
from utils.logging import log

try:
    import psutil
    _psutil_available = True
except ImportError:
    _psutil_available = False


class StorageManager:
    """
    Background storage watchdog that enforces a minimum free-space threshold
    on the recording drive using a FIFO (oldest-first) deletion strategy.

    Every `check_interval_minutes`, it checks the free space on the drive
    where recordings are stored. If free space drops below `min_free_gb`,
    it deletes the oldest YYYY_MM_DD date folder (all cameras for that day)
    and repeats until free space is restored. Today's folder is never deleted.
    """

    def __init__(self, recording_folder: str, min_free_gb: float = 50.0, check_interval_minutes: int = 5):
        self.recording_folder = recording_folder
        self.min_free_bytes = min_free_gb * (1024 ** 3)
        self.check_interval = check_interval_minutes * 60
        self._stop_event = threading.Event()
        self._thread = None

    def start(self):
        """Start the background watchdog thread."""
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=True, name="StorageManager")
        self._thread.start()
        log.info(
            f"[Storage] Watchdog started — "
            f"min free: {self.min_free_bytes / (1024 ** 3):.1f} GB, "
            f"check every {self.check_interval // 60} min"
        )

    def stop(self):
        """Signal the watchdog thread to stop."""
        self._stop_event.set()

    def update_settings(self, recording_folder: str, min_free_gb: float):
        """Update path and threshold without restarting the thread."""
        self.recording_folder = recording_folder
        self.min_free_bytes = min_free_gb * (1024 ** 3)
        log.info(f"[Storage] Settings updated — min free: {min_free_gb:.1f} GB, folder: {recording_folder}")

    # ------------------------------------------------------------------ #
    #  Internal                                                            #
    # ------------------------------------------------------------------ #

    def _run(self):
        # Run once immediately at startup, then every interval
        while not self._stop_event.is_set():
            try:
                self._check_and_cleanup()
            except Exception as e:
                log.error(f"[Storage] Unexpected error in watchdog: {e}")
            self._stop_event.wait(timeout=self.check_interval)

    def _get_free_bytes(self) -> float | None:
        """Return free bytes on the recording drive, or None on error."""
        if not _psutil_available:
            log.warning("[Storage] psutil not available — cannot check disk space")
            return None
        try:
            return psutil.disk_usage(self.recording_folder).free
        except Exception as e:
            log.error(f"[Storage] Failed to read disk usage: {e}")
            return None

    def _get_oldest_date_folder(self) -> str | None:
        """
        Return the full path of the oldest YYYY_MM_DD folder that is NOT today.
        Returns None if no eligible folder exists.
        """
        today_str = datetime.date.today().strftime("%Y_%m_%d")
        try:
            folders = [
                f for f in os.listdir(self.recording_folder)
                if (
                    os.path.isdir(os.path.join(self.recording_folder, f))
                    and f != today_str
                    and len(f) == 10           # must match YYYY_MM_DD length
                    and f.count("_") == 2      # must have exactly 2 underscores
                )
            ]
            if not folders:
                return None
            folders.sort()   # alphabetical sort = chronological for YYYY_MM_DD
            return os.path.join(self.recording_folder, folders[0])
        except Exception as e:
            log.error(f"[Storage] Failed to list recording folders: {e}")
            return None

    def _check_and_cleanup(self):
        """Core logic: check free space and delete oldest folders if needed."""
        if not os.path.exists(self.recording_folder):
            return

        free = self._get_free_bytes()
        if free is None:
            return

        free_gb = free / (1024 ** 3)

        if free >= self.min_free_bytes:
            log.debug(f"[Storage] Free space OK: {free_gb:.1f} GB")
            return

        log.warning(
            f"[Storage] Low disk space: {free_gb:.2f} GB free "
            f"(threshold: {self.min_free_bytes / (1024 ** 3):.1f} GB) — starting FIFO cleanup"
        )

        deleted_count = 0
        while True:
            free = self._get_free_bytes()
            if free is None or free >= self.min_free_bytes:
                break

            oldest = self._get_oldest_date_folder()
            if oldest is None:
                log.warning(
                    "[Storage] No more old day folders to delete — "
                    "disk is still below threshold. Add more storage."
                )
                break

            try:
                shutil.rmtree(oldest)
                log.info(f"[Storage] Deleted old recordings folder: {oldest}")
                deleted_count += 1
            except Exception as e:
                log.error(f"[Storage] Failed to delete {oldest}: {e}")
                break

        if deleted_count > 0:
            final_free = self._get_free_bytes() or 0
            log.info(
                f"[Storage] Cleanup done — deleted {deleted_count} day folder(s), "
                f"free space now: {final_free / (1024 ** 3):.2f} GB"
            )
