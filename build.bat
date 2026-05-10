@echo off
REM Build SchoolERP.exe -- run from the repo root in a venv with dev deps installed.
REM Output: dist\SchoolERP\SchoolERP.exe
setlocal

if not exist .venv\Scripts\activate.bat (
    echo No venv found. Create one first:
    echo     python -m venv .venv
    echo     .venv\Scripts\activate
    echo     pip install -e ".[dev]"
    exit /b 1
)

call .venv\Scripts\activate.bat

echo == Cleaning previous build artefacts ==
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist

echo == Running PyInstaller ==
pyinstaller --clean SchoolERP.spec
if errorlevel 1 (
    echo Build failed.
    exit /b 1
)

echo.
echo == Build complete ==
echo The packaged app is at: dist\SchoolERP\SchoolERP.exe
echo Copy the entire dist\SchoolERP folder to the target machine.
endlocal
