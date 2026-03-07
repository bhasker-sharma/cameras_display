# utils/subproc.py

import os, subprocess

def win_no_window_kwargs():
    """Return kwargs for subprocess.run/call to avoid console flicker on Windows."""
    if os.name == "nt":
        si = subprocess.STARTUPINFO()
        si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        return {
            "startupinfo": si,
            "creationflags": subprocess.CREATE_NO_WINDOW,
        }
    return {}


def kill_process_tree(pid):
    """Kill a process and all its children on Windows (or just the process on other OS)."""
    try:
        if os.name == "nt":
            subprocess.run(
                ["taskkill", "/F", "/T", "/PID", str(pid)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                **win_no_window_kwargs(),
            )
        else:
            os.kill(pid, 9)
    except Exception:
        pass


def kill_orphaned_subprocesses():
    """Kill any orphaned ffmpeg.exe and gst-launch-1.0.exe from previous runs."""
    if os.name != "nt":
        return
    for name in ("ffmpeg.exe", "gst-launch-1.0.exe"):
        try:
            subprocess.run(
                ["taskkill", "/F", "/IM", name],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                **win_no_window_kwargs(),
            )
        except Exception:
            pass
