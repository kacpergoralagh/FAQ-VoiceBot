#!/bin/bash
set -e  # Abort the script if an error occurs

echo "=========================================="
echo "STARTING ENVIRONMENT SETUP (Linux)"
echo "=========================================="

# 2. Main Application Configuration
echo ""
echo "[1/3] Creating environment for Main App (Python 3.11)..."
rm -rf .venv
python3.11 -m venv .venv

echo "Installing Main App dependencies..."
source .venv/bin/activate
pip install --upgrade pip
pip install pydub
pip install -r requirements.txt
deactivate

# 3. RASA Configuration
echo ""
echo "[2/3] Creating environment for BotRASA (Python 3.10)..."
cd BotRASA  # Make sure the folder is named exactly like in the project
rm -rf .venv_rasa
python3.10 -m venv .venv_rasa

echo "[3/3] Installing and training RASA..."
source .venv_rasa/bin/activate
pip install --upgrade pip
pip install rasa spacy

echo ""
echo "------------------------------------------"
echo "TRAINING MODEL (This might take a while)..."
echo "------------------------------------------"
rasa train

deactivate
cd ..

echo ""
echo "=========================================="
echo "DONE! Environments are ready and the model is trained."
echo "Terminal 1: RASA      - cd BotRASA && source .venv_rasa/bin/activate && rasa run --enable-api --cors '*'"
echo "Terminal 2: App       - source .venv/bin/activate && python main_app.py"
echo "=========================================="