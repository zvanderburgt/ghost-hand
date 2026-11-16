# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec: one folder, fast start, model bundled.

    .venv\\Scripts\\pyinstaller.exe --noconfirm GhostHand.spec

Output: dist\\GhostHand\\GhostHand.exe

A onefile build is possible but this stack unpacks ~400 MB per launch, which is
a bad trade for an app that auto-starts with Windows.
"""

from PyInstaller.utils.hooks import collect_all

datas = [("assets/models/hand_landmarker.task", "assets/models")]
if __import__("os").path.exists("assets/app.ico"):
    datas.append(("assets/app.ico", "assets"))

binaries = []
hiddenimports = []

# These ship native DLLs or data files that PyInstaller's static analysis misses.
for package in ("mediapipe", "soundfile", "sounddevice", "pyrealsense2", "pycaw"):
    pkg_datas, pkg_binaries, pkg_hidden = collect_all(package)
    datas += pkg_datas
    binaries += pkg_binaries
    hiddenimports += pkg_hidden

excludes = [
    "tkinter",
    "PySide6.QtWebEngineCore",
    "PySide6.QtWebEngineWidgets",
    "PySide6.QtWebEngineQuick",
    "PySide6.QtQml",
    "PySide6.QtQuick",
    "PySide6.QtQuickWidgets",
    "PySide6.QtQuick3D",
    "PySide6.Qt3DCore",
    "PySide6.Qt3DRender",
    "PySide6.QtCharts",
    "PySide6.QtDataVisualization",
    "PySide6.QtMultimedia",
    "PySide6.QtMultimediaWidgets",
    "PySide6.QtPdf",
    "PySide6.QtPdfWidgets",
    "PySide6.QtDesigner",
    "PySide6.QtHelp",
    "PySide6.QtSql",
    "PySide6.QtTest",
    "PySide6.QtBluetooth",
    "PySide6.QtNfc",
    "PySide6.QtPositioning",
    "PySide6.QtSerialPort",
    "PySide6.QtWebSockets",
]

a = Analysis(
    ["src/main.py"],
    pathex=["src"],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=excludes,
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="GhostHand",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    icon="assets/app.ico" if __import__("os").path.exists("assets/app.ico") else None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="GhostHand",
)
