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
