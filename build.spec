# -*- mode: python ; coding: utf-8 -*-
import sys

IS_MACOS = sys.platform == "darwin"

# pywebview выбирает бэкенд по платформе; PyInstaller не видит этот динамический
# импорт, поэтому нужный бэкенд перечисляем явно.
hiddenimports = (
    ["webview.platforms.cocoa"] if IS_MACOS
    else ["webview.platforms.edgechromium"]
)

a = Analysis(
    ['app/main.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('core/workflow_matrix.json', 'core'),
        ('app/web', 'app/web'),
    ],
    hiddenimports=hiddenimports,
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
    name='ReleaseNotify',
    console=False,
    upx=True,
)

if IS_MACOS:
    app = BUNDLE(
        exe,
        name='ReleaseNotify.app',
        icon=None,
        bundle_identifier='com.release-notify.app',
        info_plist={
            'NSHighResolutionCapable': True,
        },
    )
