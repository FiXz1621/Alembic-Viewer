# -*- mode: python ; coding: utf-8 -*-
import os

# Recoger solo los locales necesarios de babel
babel_datas = []
try:
    import babel
    babel_path = os.path.dirname(babel.__file__)
    # Solo incluir locales español, inglés y catalán
    locales_to_include = ['en', 'es', 'ca', 'en_US', 'es_ES', 'ca_ES', 'root']
    for locale in locales_to_include:
        locale_file = os.path.join(babel_path, 'locale-data', f'{locale}.dat')
        if os.path.exists(locale_file):
            babel_datas.append((locale_file, 'babel/locale-data'))
    # Incluir global.dat que es necesario
    global_dat = os.path.join(babel_path, 'global.dat')
    if os.path.exists(global_dat):
        babel_datas.append((global_dat, 'babel'))
except ImportError:
    pass

a = Analysis(
    ['alembic_viewer.py'],
    pathex=[],
    binaries=[],
    datas=babel_datas,
    hiddenimports=[
        'alembic_viewer',
        'alembic_viewer.app',
        'alembic_viewer.canvas',
        'alembic_viewer.config',
        'alembic_viewer.dialogs',
        'alembic_viewer.models',
        'alembic_viewer.parser',
    ],
    hookspath=['hooks'],  # Usar nuestro hook personalizado
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'PIL',           # No necesitamos Pillow en runtime
        'numpy',
        'pandas',
        'matplotlib',
        'scipy',
        'pytest',
        'unittest',
    ],
    noarchive=False,
    optimize=1,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='AlembicViewer',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['alembic_viewer.ico'],
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='AlembicViewer',
)

app = BUNDLE(
    coll,
    name='AlembicViewer.app',
    icon='alembic_viewer.ico',
    bundle_identifier='com.alembic.viewer',
)
