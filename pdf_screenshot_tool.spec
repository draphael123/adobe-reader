# -*- mode: python ; coding: utf-8 -*-
# PDF Screenshot Tool - PyInstaller Spec File

import sys
import os

block_cipher = None

# Get the directory containing this spec file
SPEC_DIR = os.path.dirname(os.path.abspath(SPEC))

# Check if icon exists
icon_path = os.path.join(SPEC_DIR, 'assets', 'icon.ico')
icon_exists = os.path.exists(icon_path)

a = Analysis(
    ['src/main.py'],
    pathex=[SPEC_DIR],
    binaries=[],
    datas=[],
    hiddenimports=[
        'pystray._win32',
        'PIL._tkinter_finder',
        'pynput.keyboard._win32',
        'pynput.mouse._win32',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='PDFScreenshotTool',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # No console window - runs in background with system tray
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=icon_path if icon_exists else None,
    version_info=None,
)

