# PyInstaller spec for JhdFromCsv — the standalone CSV -> .jhd converter.
#
#   pyinstaller tools/JhdFromCsv.spec          (run from the repo root)
#
# One console exe, no external files. tools/jhd_from_csv.py imports only the
# standard library, so there is nothing to bundle: no PyJHora, no PyQt, no
# swisseph, no ephemeris data. The excludes below drop the heavyweight modules
# PyInstaller would otherwise pull in through stdlib back-doors, which is the
# difference between a ~7 MB exe and a ~40 MB one.

from pathlib import Path

HERE = Path(SPECPATH)

a = Analysis(
    [str(HERE / "jhd_from_csv.py")],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=[],
    hookspath=[],
    runtime_hooks=[],
    excludes=[
        "tkinter", "unittest", "pydoc", "doctest", "email", "http", "xml",
        "PyQt6", "PyQt5", "numpy", "matplotlib", "PIL", "pytest",
    ],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="JhdFromCsv",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,          # the console IS the UI: it lists each file written
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
