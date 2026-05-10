# PyInstaller spec for SchoolERP -- single-folder Windows build.
# Run: pyinstaller --clean SchoolERP.spec
# Output: dist/SchoolERP/SchoolERP.exe
#
# The data files block bundles SQL migrations + any resource files so the
# packaged app finds them at runtime alongside the executable.

# -*- mode: python ; coding: utf-8 -*-

import os

block_cipher = None

datas = [
    ("app/db/migrations/*.sql", "app/db/migrations"),
    ("resources", "resources"),
]

hiddenimports = [
    "openpyxl",
    "reportlab",
    "reportlab.pdfbase._fontdata",
    "reportlab.pdfbase._fontdata_enc_winansi",
    "reportlab.pdfbase._fontdata_enc_macroman",
    "reportlab.pdfbase._fontdata_enc_standard",
    "reportlab.pdfbase._fontdata_enc_symbol",
    "reportlab.pdfbase._fontdata_enc_zapfdingbats",
    "reportlab.pdfbase._fontdata_enc_pdfdoc",
    "reportlab.pdfbase._fontdata_enc_macexpert",
    "reportlab.pdfbase._fontdata_widths_courier",
    "reportlab.pdfbase._fontdata_widths_courierbold",
    "reportlab.pdfbase._fontdata_widths_courieroblique",
    "reportlab.pdfbase._fontdata_widths_courierboldoblique",
    "reportlab.pdfbase._fontdata_widths_helvetica",
    "reportlab.pdfbase._fontdata_widths_helveticabold",
    "reportlab.pdfbase._fontdata_widths_helveticaoblique",
    "reportlab.pdfbase._fontdata_widths_helveticaboldoblique",
    "reportlab.pdfbase._fontdata_widths_timesroman",
    "reportlab.pdfbase._fontdata_widths_timesbold",
    "reportlab.pdfbase._fontdata_widths_timesitalic",
    "reportlab.pdfbase._fontdata_widths_timesbolditalic",
    "reportlab.pdfbase._fontdata_widths_symbol",
    "reportlab.pdfbase._fontdata_widths_zapfdingbats",
]

a = Analysis(
    ["app/main.py"],
    pathex=[os.path.abspath(".")],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Trim a few large optional things to keep the bundle under control.
        "tkinter",
        "matplotlib",
        "numpy.distutils",
        "test",
        "tests",
    ],
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="SchoolERP",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,           # GUI app -- no console window
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="SchoolERP",
)
