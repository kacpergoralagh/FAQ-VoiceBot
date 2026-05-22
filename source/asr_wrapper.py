import wave
import grpc
import os
import sys

asr_path = os.path.abspath(
    "external/techmo_asr/asr-api-python"
)
sys.path.append(asr_path)

# External module imports
from asr_api import v1p1 as api
from pydub import AudioSegment


# ====== TLS and ASR Configuration ======
GRPC_ADDRESS = "devtechmo.pl:25510"  # ASR server address

# Paths to certificates (after extracting techmo-agh-tls.tar.gz)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))  # directory containing asr_wrapper.py
CA_CERT = os.path.join(BASE_DIR, "cert", "tls-client", "ca.crt")
CLIENT_CERT = os.path.join(BASE_DIR, "cert", "tls-client", "client.crt")
CLIENT_KEY = os.path.join(BASE_DIR, "cert", "tls-client", "client.key")


def transcribe_wav(file_path: str, save_txt: bool = True) -> str:
    """Transcribes a WAV file and returns the recognized text as a string."""

    # --- Load audio file ---
    with wave.open(file_path, "rb") as audio_file:
        audio_bytes = audio_file.readframes(audio_file.getnframes())
        sampling_rate_hz = audio_file.getframerate()

    # --- Load TLS certificates ---
    # Check if files exist
    missing_certs = []
    for cert_path in [CA_CERT, CLIENT_CERT, CLIENT_KEY]:
        if not os.path.exists(cert_path):
            missing_certs.append(cert_path)
            
    if missing_certs:
        error_msg = (
            f"Missing TLS certificate files:\n" + 
            "\n".join(missing_certs) + 
            "\n\nEnsure that the 'cert/tls-client/' folder exists in the project root directory "
            "containing files: ca.crt, client.crt, client.key"
        )
        raise FileNotFoundError(error_msg)

    with open(CA_CERT, "rb") as f:
        ca = f.read()
    with open(CLIENT_CERT, "rb") as f:
        cert = f.read()
    with open(CLIENT_KEY, "rb") as f:
        key = f.read()

    creds = grpc.ssl_channel_credentials(
        root_certificates=ca,
        private_key=key,
        certificate_chain=cert
    )

    # --- 3. Server connection and client initialization ---
    with grpc.secure_channel(GRPC_ADDRESS, creds) as channel:
        stub = api.AsrStub(channel)

        # --- 4. Prepare requests ---
        requests = (
            api.StreamingRecognizeRequest(
                config=api.StreamingRecognizeRequestConfig(
                    audio_config=api.AudioConfig(
                        encoding=api.AudioConfig.AudioEncoding.LINEAR16,
                        sampling_rate_hz=sampling_rate_hz
                    ),
                    speech_recognition_config=api.SpeechRecognitionConfig(
                        enable_speech_recognition=True
                    )
                )
            ),
            api.StreamingRecognizeRequest(
                data=api.StreamingRecognizeRequestData(
                    audio=api.Audio(bytes=audio_bytes)
                )
            )
        )

        # --- 5. Execute and fetch response ---
        texts = []
        for response in stub.StreamingRecognize(iter(requests)):
            # Single result in the result field
            if hasattr(response, "result") and hasattr(response.result, "speech_recognition_result"):
                sr_result = response.result.speech_recognition_result
                for alt in sr_result.recognition_alternatives:
                    if hasattr(alt, "transcript"):
                        texts.append(alt.transcript)

    final_text = " ".join(texts)

    # --- Save to TXT file ---
    if save_txt:
        base, _ = os.path.splitext(file_path)
        txt_path = f"{base}.txt"
        with open(txt_path, "w", encoding="utf-8") as f:
            f.write(final_text)
        print(f"Transcription saved to: {txt_path}")
        
    # --- 6. Return the final text ---
    return final_text


# ====== Usage example ======
if __name__ == "__main__":
    # Load file
    audio = AudioSegment.from_file("rec.wav")

    # Convert to mono and 16kHz
    audio = audio.set_channels(1)
    audio = audio.set_frame_rate(16000)

    # Save to new file
    audio.export("rec.wav", format="wav")
    f = wave.open("rec.wav", "rb")
    print(f.getnchannels(), f.getsampwidth(), f.getframerate())
    plik_audio = "rec.wav"
    
    try:
        tekst = transcribe_wav(plik_audio)
        print("Recognized text:", tekst)
    except Exception as e:
        print("Transcription error:", e)