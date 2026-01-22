# -*- mode: python ; coding: utf-8 -*-

# PDF Screenshot Tool - PyInstaller Build Specification
# This creates a professional Windows executable with proper metadata

a = Analysis(
    ['src\\main.py'],
    pathex=[],
    binaries=[],
    datas=[('assets', 'assets')],
    hiddenimports=['PIL._tkinter_finder'],  # Ensure Pillow works with tkinter
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'matplotlib', 'numpy.testing', 'pytest', 'setuptools',
        'pkg_resources', 'unittest', 'xmlrpc', 'lib2to3',
    ],
    noarchive=False,
    optimize=1,  # Basic optimization
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='PDFScreenshotTool',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['assets\\icon.ico'],
    version='version_info.txt',  # Embedded version info for Windows
    uac_admin=False,  # Does not require admin privileges
    uac_uiaccess=False,
)
