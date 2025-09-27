# verify_setup.py - Check if environment is ready for PyInstaller build

import sys
import os
import importlib
import subprocess

def check_python_version():
    """Check Python version"""
    version = sys.version_info
    print(f"Python Version: {version.major}.{version.minor}.{version.micro}")
    if version.major == 3 and version.minor >= 7:
        print("✅ Python version is compatible")
        return True
    else:
        print("❌ Python 3.7+ required")
        return False

def check_required_packages():
    """Check if all required packages are installed"""
    required_packages = [
        'PyQt5', 'cv2', 'numpy', 'vlc', 'reportlab', 'pyinstaller'
    ]
    
    missing_packages = []
    
    for package in required_packages:
        try:
            importlib.import_module(package)
            print(f"✅ {package} - Found")
        except ImportError:
            print(f"❌ {package} - Missing")
            missing_packages.append(package)
    
    return len(missing_packages) == 0, missing_packages

def check_project_structure():
    """Check if all required files and folders exist"""
    required_items = [
        'main.py',
        'assets/logo.png',
        'core/',
        'ui/',
        'config/',
        'utils/',
        'requirements.txt'
    ]
    
    missing_items = []
    
    for item in required_items:
        if os.path.exists(item):
            print(f"✅ {item} - Found")
        else:
            print(f"❌ {item} - Missing")
            missing_items.append(item)
    
    return len(missing_items) == 0, missing_items

def check_external_dependencies():
    """Check for FFmpeg and VLC runtime folders"""
    external_deps = [
        'core/ffmpeg_binary',
        'core/vlc_runtime'
    ]
    
    missing_deps = []
    
    for dep in external_deps:
        if os.path.exists(dep):
            print(f"✅ {dep} - Found")
        else:
            print(f"⚠️ {dep} - Missing (will need to be added)")
            missing_deps.append(dep)
    
    return missing_deps

def main():
    print("=" * 50)
    print("PYINSTALLER BUILD ENVIRONMENT CHECK")
    print("=" * 50)
    
    # Check Python version
    print("\n1. Python Version Check:")
    python_ok = check_python_version()
    
    # Check packages
    print("\n2. Required Packages Check:")
    packages_ok, missing_packages = check_required_packages()
    
    # Check project structure
    print("\n3. Project Structure Check:")
    structure_ok, missing_files = check_project_structure()
    
    # Check external dependencies
    print("\n4. External Dependencies Check:")
    missing_external = check_external_dependencies()
    
    # Summary
    print("\n" + "=" * 50)
    print("SUMMARY")
    print("=" * 50)
    
    if python_ok and packages_ok and structure_ok:
        print("🎉 Environment is ready for PyInstaller build!")
        if missing_external:
            print("⚠️ Note: You'll need to add external dependencies during build setup")
        return True
    else:
        print("❌ Environment needs fixes before building:")
        if missing_packages:
            print(f"   Install missing packages: {', '.join(missing_packages)}")
        if missing_files:
            print(f"   Missing files: {', '.join(missing_files)}")
        return False

if __name__ == "__main__":
    main()