# -*- mode: python ; coding: utf-8 -*-
# DMGDesk.spec — PyInstaller spec per la desktop app
# Versione V16 — aggiornato per nuovo struttura progetto

import sys
from pathlib import Path

block_cipher = None

a = Analysis(
    ['main.py'],
    pathex=['.'],
    binaries=[],
    datas=[
        # Pacchetti applicazione
        ('config',          'config'),
        ('database',        'database'),
        ('ui',              'ui'),
        ('logic',           'logic'),
        ('utils',           'utils'),
        ('api',             'api'),
        # File singoli al root
        ('machine_client.py', '.'),
        # Icona (per splash/icona nella finestra)
        ('app_icon.ico',    '.'),
    ],
    collect_all=['tkinter', 'customtkinter'],
    hiddenimports=[
        # CustomTkinter
        'customtkinter',
        'customtkinter.windows',
        'customtkinter.windows.widgets',
        'customtkinter.windows.widgets.appearance_mode',
        'customtkinter.windows.widgets.scaling',
        'customtkinter.windows.widgets.font',
        # Tkinter
        'tkinter',
        'tkinter.ttk',
        'tkinter.filedialog',
        'tkinter.messagebox',
        'tkinter.simpledialog',
        # PIL
        'PIL',
        'PIL.Image',
        'PIL.ImageTk',
        'PIL._tkinter_finder',
        # Dati
        'pandas',
        'pandas.core',
        'pandas.io',
        'openpyxl',
        'numpy',
        # API interna (usata da tab_macchina e altri)
        'api.toa_parser',
        'api.routers',
        'database.db_handler',
        # Altri
        'json',
        'threading',
        'pathlib',
        're',
        'datetime',
        'shutil',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Escludi moduli pesanti non necessari per la desktop app
        'fastapi',
        'uvicorn',
        'starlette',
        'pydantic',
        'aiohttp',
        'httpx',
        'pytest',
        'matplotlib',
        'scipy',
        'sklearn',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='DMGDesk',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,         # Niente finestra console
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='app_icon.ico',   # Icona dell'exe
    version_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='DMGDesk',         # Cartella output: dist\DMGDesk\
)
