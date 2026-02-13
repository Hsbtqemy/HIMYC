# -*- mode: python ; coding: utf-8 -*-
# Phase 6 : packaging Windows (.exe) et macOS (.app avec icône)

import os
import sys

block_cipher = None

# Données à inclure (DB : schéma + migrations)
storage_src = os.path.join('src', 'howimetyourcorpus', 'core', 'storage')
storage_dest = 'howimetyourcorpus/core/storage'
datas = [
    (os.path.join(storage_src, 'schema.sql'), storage_dest),
    (os.path.join(storage_src, 'migrations'), os.path.join(storage_dest, 'migrations')),
]

a = Analysis(
    ['launch_himyc.py'],
    pathex=['src'],
    binaries=[],
    datas=datas,
    hiddenimports=[
        'howimetyourcorpus',
        'howimetyourcorpus.app.ui_mainwindow',
        'howimetyourcorpus.app.models_qt',
        'howimetyourcorpus.app.workers',
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

if sys.platform == 'darwin':
    # macOS : bundle .app avec icône (COLLECT + APP)
    exe = EXE(
        pyz,
        a.scripts,
        [],
        exclude_binaries=True,
        name='HowIMetYourCorpus',
        debug=False,
        strip=False,
        upx=True,
        console=False,
    )
    coll = COLLECT(
        exe,
        a.binaries,
        a.datas,
        strip=False,
        upx=True,
        upx_exclude=[],
        name='HowIMetYourCorpus',
    )
    icon_path = os.path.join('resources', 'icons', 'icon.icns')
    app = BUNDLE(
        coll,
        name='HowIMetYourCorpus.app',
        icon=icon_path if os.path.isfile(icon_path) else None,
        bundle_identifier='org.himyc.HowIMetYourCorpus',
    )
else:
    # Windows : un seul .exe avec icône
    icon_path_win = os.path.join('resources', 'icons', 'icon.ico')
    exe = EXE(
        pyz,
        a.scripts,
        a.binaries,
        a.datas,
        [],
        name='HowIMetYourCorpus',
        icon=icon_path_win if os.path.isfile(icon_path_win) else None,
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
