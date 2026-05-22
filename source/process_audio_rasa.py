from .asr_wrapper import transcribe_wav  # Import względny
from .tts_wrapper import synthesize_audio
import requests
import os

# --- Konfiguracja ---
SAVE_FOLDER = os.path.expanduser("~/Documents/TM_projekt_2_audio_data")
RASA_URL = "http://localhost:5005/webhooks/rest/webhook"

def send_to_rasa(message_text):
    payload = {"sender": "user", "message": message_text}
    try:
        response = requests.post(RASA_URL, json=payload)
        response.raise_for_status()
        data = response.json()
        return " ".join([item.get("text", "") for item in data])
    except Exception as e:
        print(f"Błąd połączenia z Rasą: {e}")
        return "[Błąd połączenia z Rasą]"

def process_audio_file(audio_path):
    print(f"Przetwarzanie pliku: {audio_path}")
    
    # --- Transkrypcja mowy ---
    text = transcribe_wav(audio_path)
    if not text:
        print("Nie udało się przetranskrybować audio.")
        return

    print(f"Transkrypcja: {text}")

    # --- Pobranie odpowiedzi z Rasa ---
    rasa_response = send_to_rasa(text)
    print(f"Odpowiedź Rasy: {rasa_response}")

    # --- Zapis odpowiedzi tekstowej ---
    base_name = os.path.splitext(os.path.basename(audio_path))[0]
    response_txt = os.path.join(SAVE_FOLDER, f"{base_name}_response.txt")
    with open(response_txt, "w", encoding="utf-8") as f:
        f.write(rasa_response)
    print(f"Odpowiedź zapisana w: {response_txt}")

    # --- Generowanie mowy (TTS) ---
    response_wav = os.path.join(SAVE_FOLDER, f"{base_name}_response.wav")
    synthesize_audio(rasa_response, output_wav=response_wav)
    print(f"Odpowiedź TTS zapisana w: {response_wav}")

if __name__ == "__main__":
    audio_file = os.path.join(SAVE_FOLDER, "rec.wav")
    if os.path.exists(audio_file):
        process_audio_file(audio_file)
    else:
        print("Nie znaleziono pliku audio do przetworzenia.")
