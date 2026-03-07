# utils/metrics.py

import os
import psutil
from PyQt5.QtCore import QObject, QTimer, pyqtSignal


class SystemMetrics(QObject):
    """Lightweight system metrics collector.

    Emits 'updated' signal every `interval_ms` with a dict:
      - cpu_percent:  overall server CPU usage (%)
      - mem_total_gb: total physical RAM (GB)
      - proc_mem_mb:  this process's resident memory (MB)
      - rec_total_gb: total space on the recording folder's drive (GB)
      - rec_free_gb:  free space on the recording folder's drive (GB)
    """

    updated = pyqtSignal(dict)

    def __init__(self, interval_ms=3000, recording_folder=None, parent=None):
        super().__init__(parent)
        self._process = psutil.Process(os.getpid())
        # Prime cpu_percent — first call always returns 0.
        psutil.cpu_percent(interval=None)

        self._app_path = os.path.abspath(".")
        # Walk up from recording_folder until we find an existing path
        # (handles the case where the folder hasn't been created yet).
        self._rec_path = self._resolve_path(recording_folder)

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._collect)
        self._timer.start(interval_ms)

    def _resolve_path(self, folder):
        """Return the deepest existing ancestor of folder, or the app path."""
        if not folder:
            return self._app_path
        path = folder
        while path:
            if os.path.exists(path):
                return path
            parent = os.path.dirname(path)
            if parent == path:   # reached drive root and it didn't exist
                break
            path = parent
        return self._app_path

    def _collect(self):
        try:
            cpu = psutil.cpu_percent(interval=None)
            mem = psutil.virtual_memory()
            proc_mem = self._process.memory_info().rss
            try:
                rec_disk = psutil.disk_usage(self._rec_path)
                rec_total = round(rec_disk.total / (1024 ** 3), 1)
                rec_free  = round(rec_disk.free  / (1024 ** 3), 1)
            except Exception:
                rec_total = 0.0
                rec_free  = 0.0

            self.updated.emit({
                "cpu_percent":  cpu,
                "mem_total_gb": round(mem.total   / (1024 ** 3), 1),
                "proc_mem_mb":  round(proc_mem    / (1024 ** 2), 1),
                "rec_total_gb": rec_total,
                "rec_free_gb":  rec_free,
            })
        except Exception:
            pass

    def stop(self):
        self._timer.stop()
