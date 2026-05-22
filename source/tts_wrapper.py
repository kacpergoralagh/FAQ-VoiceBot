import grpc
import wave
import os
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

TTS_API_PATH = os.path.abspath(
    os.path.join(
        BASE_DIR,
        "..",
        "external",
        "techmo_tts",
        "tts-api-python"
    )
)

sys.path.append(TTS_API_PATH)

from tts_service_api import techmo_tts_api as api   # Corrected import


# =============================
# Configuration
# =============================

GRPC_SERVICE_ADDRESS = "devtechmo.pl:25515"

CA_CERT_PATH = os.path.join(BASE_DIR, "cert", "tls-client", "ca.crt")
CLIENT_CERT_PATH = os.path.join(BASE_DIR, "cert", "tls-client", "client.crt")
CLIENT_KEY_PATH = os.path.join(BASE_DIR, "cert", "tls-client", "client.key")


def synthesize_audio(
    text: str,
    output_wav: str = "output.wav",
    voice_name: str = "masza") -> str:
    """
    Speech synthesis (Techmo TTS).
    """

    # =============================
    # Load certificates
    # =============================

    # Check certificates
    missing_certs = []
    for cert_path in [CA_CERT_PATH, CLIENT_CERT_PATH, CLIENT_KEY_PATH]:
         if not os.path.exists(cert_path):
             missing_certs.append(cert_path)
             
    if missing_certs:
        error_msg = (
            f"Missing TTS certificate files:\n" + 
            "\n".join(missing_certs) + 
            "\n\nMake sure the appropriate files exist in the 'cert/tls-client/' directory."
        )
        raise FileNotFoundError(error_msg)

    with open(CA_CERT_PATH, "rb") as f:
        trusted_certs = f.read()

    with open(CLIENT_CERT_PATH, "rb") as f:
        client_cert = f.read()

    with open(CLIENT_KEY_PATH, "rb") as f:
        client_key = f.read()

    credentials = grpc.ssl_channel_credentials(
        root_certificates=trusted_certs,
        private_key=client_key,
        certificate_chain=client_cert
    )

    # =============================
    # Synthesis configuration
    # =============================

    synthesis_config = api.SynthesisConfig(
        language_code="pl",
        voice=api.Voice(
            name=voice_name,
            variant=1
        )
    )

    output_config = api.OutputConfig(
        audio_encoding=api.AudioEncoding.PCM16,
        sampling_rate_hz=22500,
        max_frame_size=0
    )

    # =============================
    # Connection and synthesis
    # =============================

    with grpc.secure_channel(GRPC_SERVICE_ADDRESS, credentials) as grpc_channel:
        tts_stub = api.TTSStub(grpc_channel)
        request = api.SynthesizeRequest(
            text=text,
            synthesis_config=synthesis_config,
            output_config=output_config
        )

        response = tts_stub.Synthesize(request, timeout=10)

        # =============================
        # Save to WAV file
        # =============================

        with wave.open(output_wav, "wb") as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)  # PCM16 = 2 bytes
            wav_file.setframerate(output_config.sampling_rate_hz)
            wav_file.writeframes(response.audio)

    return output_wav


# Usage example
'''''
if __name__ == "__main__":
    wav = synthesize_audio(
        text="To jest test syntezy mowy Techmo",
        output_wav="tts_test.wav"
    )
    print("Generated:", wav)
'''''