# -*- mode: python ; coding: utf-8 -*-
import os

HERE = os.path.dirname(os.path.abspath(SPEC))
MANIFEST = os.path.join(HERE, '..', 'cimatron_query.manifest')

a = Analysis(
    [os.path.join(HERE, '..', 'cimatron_query.py')],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=['clr', 'pythonnet'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='cimatron_query',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
    manifest=MANIFEST,
)
