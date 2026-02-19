# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['G:\\내 드라이브\\Code\\portfolio1.6\\Portfolio.py'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=['PyQt6.QtWebEngineWidgets', 'pandas', 'plotly', 'yfinance', 'yahooquery', 'FinanceDataReader'],
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
    name='PortfolioManager',
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
