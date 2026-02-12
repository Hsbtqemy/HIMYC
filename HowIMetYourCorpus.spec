# -*- mode: python ; coding: utf-8 -*-
# Phase 6 : packaging Windows — PyInstaller spec avec données (schema.sql, migrations)

import os

block_cipher = None

# Données à inclure dans le .exe (DB : schéma + migrations)
storage_src = os.path.join('src', 'howimetyourcorpus', 'core', 'storage')
storage_dest = 'howimetyourcorpus/core/storage'
datas = [
    (os.path.join(storage_src, 'schema.sql'), storage_dest),
    (os.path.join(storage_src, 'migrations'), os.path.join(storage_dest, 'migrations')),
]

a = Analysis(
    [os.path.join('src', 'howimetyourcorpus', 'app', 'main.py')],
    pathex=['src'],
    binaries=[],
    datas=datas,
    hiddenimports=[
        'howimetyourcorpus',
        'howimetyourcorpus.core.storage.db',
        'howimetyourcorpus.core.storage.project_store',
    ],
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
    name='HowIMetYourCorpus',
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
)
