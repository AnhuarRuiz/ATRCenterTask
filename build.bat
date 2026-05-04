@echo off
setlocal EnableDelayedExpansion

echo ============================================================
echo  ATRCenterTask - Build Script
echo ============================================================
echo.

:: ── Locate Python ─────────────────────────────────────────────────────────────
set PYTHON=
for %%C in (python py python3) do (
    if not defined PYTHON (
        %%C --version >nul 2>&1
        if not errorlevel 1 set PYTHON=%%C
    )
)
if not defined PYTHON (
    echo ERROR: Python not found.
    echo Install from https://www.python.org/downloads/ and check "Add to PATH".
    pause & exit /b 1
)
echo  Using: %PYTHON%
echo.

:: ── Step 1: dependencies ──────────────────────────────────────────────────────
echo [1/4] Installing runtime dependencies...
%PYTHON% -m pip install -r requirements.txt
if errorlevel 1 ( echo ERROR: pip install failed. & pause & exit /b 1 )

:: ── Step 2: PyInstaller ───────────────────────────────────────────────────────
echo.
echo [2/4] Installing PyInstaller...
%PYTHON% -m pip install pyinstaller
if errorlevel 1 ( echo ERROR: PyInstaller install failed. & pause & exit /b 1 )

:: ── Step 3: pre-generate UIAutomation comtypes bindings ───────────────────────
echo.
echo [3/4] Pre-generating UIAutomation bindings for comtypes...
%PYTHON% -c "import comtypes.client; comtypes.client.GetModule('UIAutomationCore.dll'); print('  UIAutomationClient bindings OK')"
if errorlevel 1 (
    echo WARNING: Could not pre-generate UIAutomation bindings.
    echo          The .exe may fail to measure taskbar content width.
)

:: ── Step 4: build ─────────────────────────────────────────────────────────────
echo.
echo [4/4] Building ATRCenterTask.exe ...
%PYTHON% -m PyInstaller --onefile --noconsole ^
    --name ATRCenterTask ^
    --icon=logo\logo.ico ^
    --add-data "logo\logo.png;logo" ^
    --hidden-import pystray._win32 ^
    --collect-all comtypes ^
    ATRCenterTask.py

echo.
if exist dist\ATRCenterTask.exe (
    echo ============================================================
    echo  SUCCESS  -  dist\ATRCenterTask.exe is ready
    echo ============================================================
    echo.
    echo  1. Exit ATRCenterTask from the tray: right-click its icon then Exit
    echo  2. Run dist\ATRCenterTask.exe
) else (
    echo ============================================================
    echo  BUILD FAILED  -  check the output above for errors
    echo ============================================================
)
pause
