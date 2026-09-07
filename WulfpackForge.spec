# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ["main.py"],
    pathex=[],
    binaries=[],
    datas=[
        ("data/valheim_items.json", "data"),
        ("data/valheim_durability.json", "data"),
        ("assets/wulfpack-forge-banner.jpg", "assets"),
        ("assets/FrostWulf-favicon.png", "assets"),
        ("assets/glyphs/items", "assets/glyphs/items"),
        ("assets/glyphs/hair", "assets/glyphs/hair"),
        ("assets/glyphs/beard", "assets/glyphs/beard"),
    ],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="WulfpackForge",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    icon="assets/wulfpack-forge.ico",
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
