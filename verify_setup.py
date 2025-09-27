# verify_setup_enhanced.py - Enhanced environment check for PyInstaller build

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
        ('PyQt5', 'PyQt5'), 
        ('cv2', 'opencv-python'), 
        ('numpy', 'numpy'), 
        ('vlc', 'python-vlc'), 
        ('reportlab', 'reportlab')
    ]
    
    missing_packages = []
    
    for import_name, package_name in required_packages:
        try:
            importlib.import_module(import_name)
            print(f"✅ {package_name} - Found")
        except ImportError:
            print(f"❌ {package_name} - Missing")
            missing_packages.append(package_name)
    
    # Special check for PyInstaller (command-line tool)
    try:
        result = subprocess.run(['pyinstaller', '--version'], 
                              capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            version = result.stdout.strip()
            print(f"✅ pyinstaller - Found (version: {version})")
        else:
            print("❌ pyinstaller - Command not working")
            missing_packages.append('pyinstaller')
    except (subprocess.TimeoutExpired, FileNotFoundError, subprocess.SubprocessError):
        print("❌ pyinstaller - Not found in PATH")
        missing_packages.append('pyinstaller')
    
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
    """Check for FFmpeg and VLC runtime folders with specific files"""
    dependencies = {
        'FFmpeg': {
            'path': 'core/ffmpeg_binary',
            'files': ['ffmpeg.exe']
        },
        'VLC Runtime': {
            'path': 'core/vlc_runtime',
            'files': ['libvlc.dll', 'libvlccore.dll', 'plugins/']
        }
    }
    
    missing_deps = []
    
    for dep_name, dep_info in dependencies.items():
        dep_path = dep_info['path']
        required_files = dep_info['files']
        
        if os.path.exists(dep_path):
            print(f"✅ {dep_name} folder - Found")
            
            # Check specific files
            for file_name in required_files:
                file_path = os.path.join(dep_path, file_name)
                if os.path.exists(file_path):
                    print(f"  ✅ {file_name} - Found")
                else:
                    print(f"  ❌ {file_name} - Missing")
                    missing_deps.append(f"{dep_name}/{file_name}")
        else:
            print(f"❌ {dep_name} folder - Missing")
            missing_deps.extend([f"{dep_name}/{f}" for f in required_files])
    
    return missing_deps

def check_spec_file():
    """Check if PyInstaller spec file exists"""
    spec_files = ['camera_app.spec', 'main.spec']
    for spec_file in spec_files:
        if os.path.exists(spec_file):
            print(f"✅ {spec_file} - Found")
            return True
    print("⚠ No PyInstaller spec file found (will be created)")
    return False

def provide_build_commands():
    """Provide build commands based on setup"""
    print("\n📋 BUILD COMMANDS:")
    print("-" * 30)
    
    if os.path.exists('camera_app.spec'):
        print("Using existing spec file:")
        print("  pyinstaller camera_app.spec")
    else:
        print("Create spec file first, then run:")
        print("  pyinstaller camera_app.spec")
    
    print("\nAlternative one-liner (without spec):")
    print('  pyinstaller --onedir --windowed --name="CameraViewer" --add-data="assets;assets" --add-data="core/ffmpeg_binary;ffmpeg_binary" --add-data="core/vlc_runtime;vlc_runtime" main.py')

def provide_missing_deps_guide():
    """Provide guide for setting up missing dependencies"""
    print("\n🔧 SETUP MISSING DEPENDENCIES:")
    print("-" * 40)
    
    print("\n1. FFmpeg Setup:")
    print("   - Download: https://ffmpeg.org/download.html")
    print("   - Extract ffmpeg.exe to: core/ffmpeg_binary/ffmpeg.exe")
    
    print("\n2. VLC Runtime Setup:")  
    print("   - Download VLC portable: https://www.videolan.org/vlc/")
    print("   - Copy these files to core/vlc_runtime/:")
    print("     • libvlc.dll")
    print("     • libvlccore.dll") 
    print("     • plugins/ (entire folder)")
    
    print("\n3. Create directories:")
    print("   mkdir core\\ffmpeg_binary")
    print("   mkdir core\\vlc_runtime")
    print("   mkdir core\\vlc_runtime\\plugins")

def main():
    print("=" * 60)
    print("ENHANCED PYINSTALLER BUILD ENVIRONMENT CHECK")
    print("=" * 60)
    
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
    
    # Check spec file
    print("\n5. PyInstaller Spec File Check:")
    spec_exists = check_spec_file()
    
    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    
    ready_to_build = python_ok and packages_ok and structure_ok and len(missing_external) == 0
    
    if ready_to_build:
        print("🎉 Environment is fully ready for PyInstaller build!")
        provide_build_commands()
    else:
        print("❌ Environment needs fixes before building:")
        if missing_packages:
            print(f"   📦 Install packages: pip install {' '.join(missing_packages)}")
        if missing_files:
            print(f"   📁 Missing files: {', '.join(missing_files)}")
        if missing_external:
            print(f"   🔧 Missing external deps: {len(missing_external)} items")
            provide_missing_deps_guide()
    
    return ready_to_build

if __name__ == "__main__":
    main()