@echo off
REM Build JhdFromCsv.exe on Windows. Double-click this file, or run it from a
REM command prompt. Needs Python 3.9+ on PATH ("Add python.exe to PATH" must be
REM ticked in the Python installer) and an internet connection the first time,
REM to fetch PyInstaller.
REM
REM The result is dist\JhdFromCsv.exe — a single self-contained file. Copy it
REM anywhere; it needs no Python and no other file from this repo.

setlocal
cd /d "%~dp0\.."

echo === Checking Python ===
python --version || (
    echo.
    echo Python was not found on PATH.
    echo Install it from https://www.python.org/downloads/ and be sure to tick
    echo "Add python.exe to PATH" during setup, then run this file again.
    goto :fail
)

echo.
echo === Installing PyInstaller ===
python -m pip install --upgrade --quiet pip pyinstaller || goto :fail

echo.
echo === Running tests ===
python -m pip install --quiet pytest || goto :fail
python -m pytest tools\test_jhd_from_csv.py -q || goto :fail

echo.
echo === Building ===
python -m PyInstaller --clean --noconfirm tools\JhdFromCsv.spec || goto :fail

echo.
echo === Checking the exe actually runs ===
dist\JhdFromCsv.exe tools\partners.example.csv -o "%TEMP%\jhd_smoketest" --no-pause || goto :fail

echo.
echo ============================================================
echo  Done.  Your program is:  %CD%\dist\JhdFromCsv.exe
echo.
echo  Copy it wherever you like, then drag a .csv onto it - or
echo  put partners.csv beside it and double-click.
echo  Instructions: tools\README-JhdFromCsv.md
echo ============================================================
pause
exit /b 0

:fail
echo.
echo BUILD FAILED - see the messages above.
pause
exit /b 1
