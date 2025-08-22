# provision_key.py
from utils.security_pendrive import provision_token_on_drive, _iter_removable_roots_public
import sys,os
import shutil

def pick_drive():
    roots = _iter_removable_roots_public()
    if not roots:
        print("No removable drives found.")
        sys.exit(1)
    if len(roots) == 1:
        return roots[0]
    print("Select removable drive:")
    for i, r in enumerate(roots, 1):
        print(f"{i}) {r}")
    idx = int(input("Choice: "))
    return roots[idx-1]

def prompt_and_clean_drive(root):
    print(f"\nWARNING: You are about to ERASE ALL DATA on: {root}")
    confirm = input("Type 'YES' to continue, or anything else to cancel: ").strip()
    if confirm != "YES":
        print("Cancelled by user.")
        sys.exit(0)
    for item in os.listdir(root):
        path = os.path.join(root, item)
        try:
            if os.path.isdir(path):
                shutil.rmtree(path)
            else:
                os.remove(path)
        except Exception as e:
            print(f"Failed to delete {path}: {e}")
    print("✔ Drive cleaned.")


if __name__ == "__main__":
    root = pick_drive()
    prompt_and_clean_drive(root)
    path, token = provision_token_on_drive(root)
    print(f"Token written to {path}")
    print("(No need to copy token into code in strong mode; your code uses _APP_SECRET_HEX as the HMAC key.)")
