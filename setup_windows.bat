@echo off
echo ==========================================
echo STARTING ENVIRONMENT SETUP (Windows)
echo ==========================================

:: 1. Submodules (commented out, pip git+ handles this)
::echo [1/4] Updating repository and submodules...
::git submodule update --init --recursive

:: 2. Main Application Configuration (Python 3.11)
echo.
echo [1/3] Creating environment for Main App (Python 3.11)...
if exist .venv rmdir /s /q .venv
py -3.11 -m venv .venv

echo Installing Main App dependencies...
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -r requirements.txt
call .venv\Scripts\deactivate.bat

:: 3. RASA Configuration (Python 3.10)
echo.
echo [2/3] Creating environment for BotRASA (Python 3.10)...
cd BotRASA
if exist .venv_rasa rmdir /s /q .venv_rasa
py -3.10 -m venv .venv_rasa

echo [3/3] Installing and training RASA...
call .venv_rasa\Scripts\activate.bat
python -m pip install --upgrade pip
:: Added spacy here for consistency with the Linux version
pip install rasa spacy

echo.
echo ------------------------------------------
echo TRAINING MODEL (This might take a while)...
echo ------------------------------------------
rasa train

call .venv_rasa\Scripts\deactivate.bat
cd ..

echo.
echo ==========================================
echo DONE! Environments are ready.
echo Launch instructions:
echo Terminal 1: RASA - rasa run --enable-api --cors "*"
echo Terminal 2: App - .venv\Scripts\python main_app.py
echo ==========================================
pause