# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for Shellshuck — builds two executables:
#   1. shellshuck         — main GUI app
#   2. shellshuck-askpass  — SSH_ASKPASS helper (invoked by ssh as a child process)
# Usage: pyinstaller shellshuck.spec

main_a = Analysis(
    ['src/shellshuck/__main__.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('resources/icons', 'resources/icons'),
    ],
    hiddenimports=[
        'shellshuck',
        'shellshuck.app',
        'shellshuck.config',
        'shellshuck.models',
        'shellshuck.resources',
        'shellshuck.key_manager',
        'shellshuck.managers',
        'shellshuck.managers.tunnel',
        'shellshuck.managers.mount',
        'shellshuck.widgets',
        'shellshuck.widgets.main_window',
        'shellshuck.widgets.tunnel_dialog',
        'shellshuck.widgets.mount_dialog',
        'shellshuck.widgets.splash',
        'shellshuck.widgets.log_panel',
        'shellshuck.widgets.key_setup_dialog',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

askpass_a = Analysis(
    ['src/shellshuck/askpass.py'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

MERGE(
    (main_a, 'shellshuck', 'shellshuck'),
    (askpass_a, 'shellshuck-askpass', 'shellshuck-askpass'),
)

# --- Main app ---

main_pyz = PYZ(main_a.pure)

main_exe = EXE(
    main_pyz,
    main_a.scripts,
    main_a.binaries,
    main_a.datas,
    [],
    name='shellshuck',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    icon='resources/icons/shellshuck.svg',
)

# --- Askpass helper ---

askpass_pyz = PYZ(askpass_a.pure)

askpass_exe = EXE(
    askpass_pyz,
    askpass_a.scripts,
    askpass_a.binaries,
    askpass_a.datas,
    [],
    name='shellshuck-askpass',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
)
