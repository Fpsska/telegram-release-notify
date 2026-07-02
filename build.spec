# -*- mode: python ; coding: utf-8 -*-

a = Analysis(
    ['app/main.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('core/workflow_matrix.json', 'core'),
        ('app/web', 'app/web'),
    ],
    hiddenimports=['webview.platforms.edgechromium'],
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
