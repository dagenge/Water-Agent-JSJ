# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['launch.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('agent', 'agent'),
        ('backend', 'backend'),
        ('frontend', 'frontend'),
        ('knowledge', 'knowledge'),
        ('config', 'config'),
        ('data', 'data'),
        ('.env', '.'),
        ('.env.example', '.'),
    ],
    hiddenimports=[
        'streamlit',
        'fastapi',
        'uvicorn',
        'langchain',
        'langchain_openai',
        'langchain_community',
        'langgraph',
        'sentence_transformers',
        'faiss',
        'rank_bm25',
        'pandas',
        'numpy',
        'plotly',
        'geopandas',
        'shapely',
        'pyproj',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
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
    name='WaterAgent',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,  # 显示控制台窗口（可改为 False 隐藏）
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='WaterAgent',
)
