# utils/security_pendrive.py
import ctypes, os, hmac, hashlib, string, subprocess, re

# === Strong binding: token = HMAC(APP_SECRET, f"{VOLUME_SERIAL_HEX}|{PNP_ID}") ===
MODE = "HMAC_SERIAL_PNP"
_APP_SECRET_HEX = "9e157c09a36b438afe1583621cc066f2f57b3971c6e7b348dc607c93a4bfc7ae"
_TOKEN_FILENAME = ".cam_dongle.token"

# Windows drive type constants
DRIVE_REMOVABLE = 2
GetLogicalDrives = ctypes.windll.kernel32.GetLogicalDrives
GetDriveTypeW    = ctypes.windll.kernel32.GetDriveTypeW
GetVolumeInformationW = ctypes.windll.kernel32.GetVolumeInformationW

def _iter_removable_roots():
    mask = GetLogicalDrives()
    for i in range(26):
        if mask & (1 << i):
            root = f"{string.ascii_uppercase[i]}:\\"
            dtype = GetDriveTypeW(ctypes.c_wchar_p(root))
            if dtype == DRIVE_REMOVABLE:
                yield root

def _get_volume_serial(root):
    vol_name_buf   = ctypes.create_unicode_buffer(261)
    fs_name_buf    = ctypes.create_unicode_buffer(261)
    serial = ctypes.c_uint()
    max_comp_len = ctypes.c_uint()
    fs_flags = ctypes.c_uint()
    ok = GetVolumeInformationW(
        ctypes.c_wchar_p(root),
        vol_name_buf, len(vol_name_buf),
        ctypes.byref(serial),
        ctypes.byref(max_comp_len),
        ctypes.byref(fs_flags),
        fs_name_buf, len(fs_name_buf)
    )
    return serial.value if ok else None

def _wmic(args):
    p = subprocess.run(["wmic"] + args, capture_output=True, text=True, shell=True)
    out = (p.stdout or "").splitlines()
    return [ln.strip() for ln in out if ln.strip()]

def _map_drive_to_pnp_ps(root):
    """
    PowerShell fallback to resolve PNPDeviceID for a logical drive like 'F:\\'.
    Works on modern Windows where WMIC may be missing/limited.
    """
    drive = root.rstrip("\\")
    ps = r"""
$drive = '%s'
$part  = Get-WmiObject -Query "ASSOCIATORS OF {Win32_LogicalDisk.DeviceID='$drive'} WHERE AssocClass = Win32_LogicalDiskToPartition"
if ($part -eq $null) { exit 2 }
$disk  = Get-WmiObject -Query "ASSOCIATORS OF {Win32_DiskPartition.DeviceID='$($part.DeviceID)'} WHERE AssocClass = Win32_DiskDriveToDiskPartition"
if ($disk -eq $null) { exit 3 }
$disk.PNPDeviceID
""" % drive
    try:
        r = subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps],
            capture_output=True, text=True
        )
        if r.returncode == 0:
            # Take the first non-empty line
            lines = [ln.strip() for ln in (r.stdout or "").splitlines() if ln.strip()]
            return lines[0] if lines else None
    except Exception:
        pass
    return None

def _map_drive_to_pnp(root):
    """
    Try WMIC first; if it fails, use PowerShell fallback.
    Returns PNPDeviceID string or None.
    """
    drive = root.rstrip("\\")
    # 1) WMIC path (may be deprecated on your system)
    try:
        link1 = _wmic(["path", "Win32_LogicalDiskToPartition", "get", "Antecedent,Dependent"])
        target = None
        needle = f'Dependent="Win32_LogicalDisk.DeviceID=\\"{drive}\\""'
        for ln in link1:
            if needle in ln.replace("\\\\", "\\"):
                target = ln
                break
        if target:
            m = re.search(r'Antecedent="Win32_DiskPartition\.DeviceID=\\"([^"]+)\\""', target)
            if m:
                part_id = m.group(1)
                link2 = _wmic(["path", "Win32_DiskDriveToDiskPartition", "get", "Antecedent,Dependent"])
                dd_target = None
                dep = f'Dependent="Win32_DiskPartition.DeviceID=\\"{part_id}\\""'
                for ln in link2:
                    if dep in ln.replace("\\\\", "\\"):
                        dd_target = ln
                        break
                if dd_target:
                    m2 = re.search(r'Antecedent="Win32_DiskDrive\.DeviceID=\\"([^"]+)\\""', dd_target)
                    if m2:
                        phys = m2.group(1)
                        drives = _wmic(["diskdrive", "get", "DeviceID,PNPDeviceID,Model,InterfaceType"])
                        for ln in drives:
                            if phys in ln:
                                m3 = re.search(r'(USBSTOR[\\A-Za-z0-9&._\-]+)', ln)
                                return m3.group(1) if m3 else ln
    except Exception:
        pass

    # 2) PowerShell fallback
    return _map_drive_to_pnp_ps(root)

def _expected_token(serial_int, pnp_id_str):
    if not pnp_id_str:
        raise RuntimeError("PNP ID not found; cannot bind token.")
    serial_hex = f"{serial_int:08X}".encode()
    msg = serial_hex + b"|" + pnp_id_str.encode()
    key = bytes.fromhex(_APP_SECRET_HEX)
    return hmac.new(key, msg, hashlib.sha256).hexdigest()

def check_pendrive_key():
    try:
        found_any = False
        for root in _iter_removable_roots():
            found_any = True
            serial = _get_volume_serial(root)
            if not serial:
                continue
            pnp = _map_drive_to_pnp(root)
            if not pnp:
                continue
            token_path = os.path.join(root, _TOKEN_FILENAME)
            if not os.path.exists(token_path):
                continue
            with open(token_path, "r", encoding="utf-8") as f:
                token = f.read().strip()
            expected = _expected_token(serial, pnp)
            if hmac.compare_digest(token, expected):
                return True, None

        if not found_any:
            return False, "No removable drives detected."
        return False, "Security USB key not detected or mismatch."
    except Exception as e:
        return False, f"Dongle check error: {e}"

# --- Public helpers for provision script ---
def _iter_removable_roots_public():
    return list(_iter_removable_roots())

def provision_token_on_drive(root):
    serial = _get_volume_serial(root)
    if not serial:
        raise RuntimeError("Cannot read volume serial.")
    pnp = _map_drive_to_pnp(root)
    if not pnp:
        raise RuntimeError("Cannot resolve USB PNP ID for this drive.")
    token = _expected_token(serial, pnp)
    path = os.path.join(root, _TOKEN_FILENAME)
    with open(path, "w", encoding="utf-8") as f:
        f.write(token + "\n")
    try:
        subprocess.run(["attrib", "+H", path], check=False)
    except Exception:
        pass
    return path, token
