import os
import soundfile as sf
import sounddevice as sd
import numpy as np
from datetime import datetime
import csv

# New imports for analysis
import librosa

# Imports required for playback and signals
from PySide6.QtCore import QObject, Signal, QUrl
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput, QMediaDevices, QAudioDevice
from pydub import AudioSegment

class AudioController(QObject):
    playback_finished = Signal()

    def __init__(self):
        super().__init__()
        
        user_home = os.path.expanduser("~")
        self.save_folder = os.path.join(user_home, "Documents", "FAQ_VoiceBot_audio_data")

        if not os.path.exists(self.save_folder):
            os.makedirs(self.save_folder)
        
        # --- Recording variables ---
        self.is_recording = False
        self.recording_frames = []
        self.stream = None
        self.samplerate = 16000 # Default sampling rate for recording
        self.input_device_index = None

        # --- Playback variables ---
        self.player = QMediaPlayer()
        self.audio_output = QAudioOutput()
        self.audio_output.setDevice(QMediaDevices.defaultAudioOutput())
        self.player.setAudioOutput(self.audio_output)
        self.audio_output.setVolume(1.0)
        self.player.mediaStatusChanged.connect(self._handle_media_status)

    # ... (Methods set_save_folder, get_input_devices etc. remain unchanged) ...
    def set_save_folder(self, new_path):
        if os.path.exists(new_path):
            self.save_folder = new_path

    def get_input_devices(self):
        devices = sd.query_devices()
        input_devices = []
        for i, dev in enumerate(devices):
            if dev['max_input_channels'] > 0:
                input_devices.append((i, dev['name']))
        return input_devices

    def set_input_device(self, index):
        self.input_device_index = index

    def get_output_devices(self):
        return QMediaDevices.audioOutputs()

    def set_output_device(self, device_info):
        self.audio_output.setDevice(device_info)

    # --- Recording ---
    def start_recording(self):
        if self.is_recording:
            return
        self.stop_audio()
        self.recording_frames = []
        self.is_recording = True
        
        def callback(indata, frames, time, status):
            if status: print(status)
            self.recording_frames.append(indata.copy())

        try:
            self.stream = sd.InputStream(
                samplerate=self.samplerate, 
                channels=1, 
                callback=callback,
                device=self.input_device_index
            )
            self.stream.start()
        except Exception as e:
            print(f"Recording error: {e}")
            self.is_recording = False

    def stop_recording(self):
        if not self.is_recording or self.stream is None:
            return None
        self.stream.stop()
        self.stream.close()
        self.is_recording = False

        if len(self.recording_frames) > 0:
            full_recording = np.concatenate(self.recording_frames, axis=0)
            # timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            filename = f"rec.wav"
            filepath = os.path.join(self.save_folder, filename)
            sf.write(filepath, full_recording, self.samplerate)
            return filepath
        return None

    # --- Playback ---
    def play_audio(self, file_path):
        self.stop_audio()
        url = QUrl.fromLocalFile(file_path)
        self.player.setSource(url)
        self.player.play()

    def stop_audio(self):
        if self.player.playbackState() != QMediaPlayer.StoppedState:
            self.player.stop()
        self.player.setSource(QUrl())
            
    def _handle_media_status(self, status):
        if status == QMediaPlayer.EndOfMedia:
            self.stop_audio()
            self.playback_finished.emit()

    # --- New analysis functions ---

    def analyze_audio_file(self, file_path):
        """
        Loads a file and returns a dictionary with analysis data.
        Uses the librosa library.
        """
        try:
            # Load audio (y = samples, sr = sample rate)
            # sr=None means loading with the file's original sampling rate
            y, sr = librosa.load(file_path, sr=None, mono=False)
            
            # Check channels
            channels = 1
            if y.ndim > 1:
                channels = y.shape[0]
                # For MFCC and RMS analysis, we usually flatten to mono
                y_mono = librosa.to_mono(y)
            else:
                y_mono = y

            # Duration
            duration = librosa.get_duration(y=y_mono, sr=sr)
            
            # RMS (Root Mean Square) - amplitude
            rms = np.sqrt(np.mean(y_mono**2))
            
            # MFCC (Mel-frequency cepstral coefficients)
            mfcc = librosa.feature.mfcc(y=y_mono, sr=sr, n_mfcc=13)
            
            results = {
                "y": y_mono,           # Samples (mono)
                "sr": sr,              # Sampling rate
                "duration": duration,  # Time in seconds
                "rms": rms,            # RMS value
                "channels": "Stereo" if channels > 1 else "Mono",
                "mfcc": mfcc           # MFCC matrix
            }
            return results
        except Exception as e:
            print(f"Analysis error: {e}")
            return None

    def export_samples_to_csv(self, file_path, samples):
        """Saves samples to a CSV file."""
        try:
            with open(file_path, 'w', newline='') as csvfile:
                writer = csv.writer(csvfile)
                writer.writerow(["Sample_Value"])
                for sample in samples:
                    writer.writerow([sample])
            return True
        except Exception as e:
            print(f"CSV export error: {e}")
            return False