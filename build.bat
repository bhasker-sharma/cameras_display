@echo off
setlocal EnableDelayedExpansion
title Tuyere Camera Viewer - Build

set APP_NAME=TuyereCameraViewer
set DIST_DIR=dist\%APP_NAME%

:: External tool paths — edit these if installed elsewhere
set GST_SRC=C:\Program Files\gstreamer\1.0\msvc_x86_64
set VLC_SRC=C:\Program Files\VideoLAN\VLC
set ISCC="C:\Program Files (x86)\Inno Setup 6\ISCC.exe"

:: Local bin\ folder — place ffmpeg.exe and ffprobe.exe here before building
set LOCAL_BIN=bin

echo.
echo ============================================================
echo   Tuyere Camera Viewer - Build Script
echo ============================================================
echo.

:: ── STEP 1: Check prerequisites ─────────────────────────────
echo [1/6] Checking prerequisites...

if not exist "%GST_SRC%\bin\gst-launch-1.0.exe" (
    echo.
    echo  [ERROR] GStreamer not found at:
    echo          %GST_SRC%
    echo.
    echo  Install GStreamer 1.0 MSVC x86_64 ^(runtime + development^) from:
    echo  https://gstreamer.freedesktop.org/data/pkg/windows/
    echo.
    pause & exit /b 1
)
echo   [OK] GStreamer found.

if not exist "%VLC_SRC%\libvlc.dll" (
    echo.
    echo  [ERROR] VLC not found at:
    echo          %VLC_SRC%
    echo.
    echo  Install VLC 64-bit from: https://www.videolan.org/vlc/
    echo.
    pause & exit /b 1
)
echo   [OK] VLC found.

if not exist "%LOCAL_BIN%\ffmpeg.exe" (
    echo.
    echo  [ERROR] ffmpeg.exe not found in .\bin\
    echo.
    echo  Download a Windows 64-bit static FFmpeg build and place
    echo  ffmpeg.exe and ffprobe.exe inside the .\bin\ folder:
    echo  https://github.com/BtbN/FFmpeg-Builds/releases
    echo  ^(get: ffmpeg-master-latest-win64-gpl.zip^)
    echo.
    pause & exit /b 1
)
echo   [OK] ffmpeg.exe found.

if not exist "%LOCAL_BIN%\ffprobe.exe" (
    echo.
    echo  [ERROR] ffprobe.exe not found in .\bin\
    echo  ^(Download same FFmpeg build as ffmpeg.exe^)
    echo.
    pause & exit /b 1
)
echo   [OK] ffprobe.exe found.

echo   [OK] All prerequisites satisfied.
echo.

:: ── STEP 2: Activate venv and run PyInstaller ───────────────
echo [2/6] Building Python application with PyInstaller...

if not exist "env\Scripts\activate.bat" (
    echo  [ERROR] Virtual environment not found. Run: python -m venv env
    pause & exit /b 1
)

call env\Scripts\activate.bat
if errorlevel 1 (
    echo  [ERROR] Failed to activate virtual environment.
    pause & exit /b 1
)

:: Clean previous build artifacts
if exist "dist\%APP_NAME%" rmdir /s /q "dist\%APP_NAME%"
if exist "build\%APP_NAME%" rmdir /s /q "build\%APP_NAME%"

pyinstaller tuyere_camera.spec --clean --noconfirm
if errorlevel 1 (
    echo  [ERROR] PyInstaller build failed.
    pause & exit /b 1
)

if not exist "%DIST_DIR%\%APP_NAME%.exe" (
    echo  [ERROR] EXE not found after build. Check PyInstaller output above.
    pause & exit /b 1
)
echo   [OK] PyInstaller build complete.
echo.

:: ── STEP 3: Bundle FFmpeg ───────────────────────────────────
echo [3/6] Bundling FFmpeg...

mkdir "%DIST_DIR%\bin" 2>nul
copy /Y "%LOCAL_BIN%\ffmpeg.exe"  "%DIST_DIR%\bin\ffmpeg.exe"  >nul
copy /Y "%LOCAL_BIN%\ffprobe.exe" "%DIST_DIR%\bin\ffprobe.exe" >nul

echo   [OK] ffmpeg.exe + ffprobe.exe bundled in bin\
echo.

:: ── STEP 4: Bundle GStreamer ─────────────────────────────────
echo [4/6] Bundling GStreamer runtime...
echo   (This copies ~300 MB of DLLs and plugins — may take a moment)

mkdir "%DIST_DIR%\gstreamer\bin"               2>nul
mkdir "%DIST_DIR%\gstreamer\lib\gstreamer-1.0" 2>nul

xcopy /E /Y /Q /I "%GST_SRC%\bin\*"                   "%DIST_DIR%\gstreamer\bin\"
xcopy /E /Y /Q /I "%GST_SRC%\lib\gstreamer-1.0\*"     "%DIST_DIR%\gstreamer\lib\gstreamer-1.0\"

echo   [OK] GStreamer bundled.
echo.

:: ── STEP 5: Bundle VLC DLLs ─────────────────────────────────
echo [5/6] Bundling VLC DLLs...

:: Core VLC DLLs go into the app root (beside the EXE)
copy /Y "%VLC_SRC%\libvlc.dll"     "%DIST_DIR%\libvlc.dll"     >nul
copy /Y "%VLC_SRC%\libvlccore.dll" "%DIST_DIR%\libvlccore.dll" >nul

:: VLC plugins must sit in a plugins\ folder next to libvlc.dll
mkdir "%DIST_DIR%\plugins" 2>nul
xcopy /E /Y /Q /I "%VLC_SRC%\plugins\*" "%DIST_DIR%\plugins\"

echo   [OK] VLC DLLs + plugins bundled.
echo.

:: ── STEP 6: Create installer with Inno Setup ────────────────
echo [6/6] Creating Windows installer...

if not exist %ISCC% (
    echo   [SKIP] Inno Setup not found at: %ISCC%
    echo.
    echo   To generate the installer:
    echo     1. Install Inno Setup 6 from https://jrsoftware.org/isinfo.php
    echo     2. Re-run this script
    echo.
    echo ============================================================
    echo  BUILD COMPLETE  ^(app folder only — no installer^)
    echo  App folder : %DIST_DIR%\
    echo ============================================================
    pause & exit /b 0
)

if not exist "installer" mkdir installer

%ISCC% "installer\tuyere_setup.iss"
if errorlevel 1 (
    echo  [ERROR] Inno Setup compilation failed.
    pause & exit /b 1
)

echo.
echo ============================================================
echo  BUILD COMPLETE
echo  App folder : %DIST_DIR%\
echo  Installer  : installer\TuyereCameraViewer_Setup.exe
echo ============================================================
pause
