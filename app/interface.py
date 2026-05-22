from PySide6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                               QGridLayout, QPushButton, QLabel, QStackedWidget,
                               QFrame, QScrollArea, QInputDialog, QMessageBox,
                               QFileDialog, QComboBox, QGroupBox, QFormLayout,
                               QSizePolicy, QDialog, QProgressBar, QCheckBox, QLayout)
from PySide6.QtCore import Qt, QSize, Signal, QThread, QRectF
from PySide6.QtGui import QIcon, QPainter, QPainterPath, QColor, QBrush, QPen
import os
from source.asr_wrapper import transcribe_wav
from source.tts_wrapper import synthesize_audio
from source.process_audio_rasa import send_to_rasa
import traceback

# --- Matplotlib configuration for PySide6 ---
import matplotlib
matplotlib.use('qtagg') 
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import numpy as np

from app.logic import AudioController


# --- Analysis worker thread ---
class AnalysisWorker(QThread):
    finished = Signal(object)

    def __init__(self, controller, file_path):
        super().__init__()
        self.controller = controller
        self.file_path = file_path

    def run(self):
        data = self.controller.analyze_audio_file(self.file_path)
        self.finished.emit(data)


# --- ASR worker thread ---
class AsrWorker(QThread):
    finished = Signal(str, str) # text, error

    def __init__(self, file_path):
        super().__init__()
        self.file_path = file_path

    def run(self):
        try:
            # Use ASR wrapper
            text = transcribe_wav(self.file_path)
            self.finished.emit(text, "")
        except Exception as e:
            # traceback.print_exc() # optional
            self.finished.emit("", str(e))


# --- TTS worker thread ---
class TtsWorker(QThread):
    finished = Signal(str, str) # file_path, error

    def __init__(self, text, voice="masza"):
        super().__init__()
        self.text = text
        self.voice = voice

    def run(self):
        try:
            # Simplified: Save in documents where recordings are stored
            user_home = os.path.expanduser("~")
            save_folder = os.path.join(user_home, "Documents", "FAQ_VoiceBot_audio_data")
            if not os.path.exists(save_folder):
                os.makedirs(save_folder)
            
            import time
            filename = f"tts_{int(time.time())}.wav"
            out_path = os.path.join(save_folder, filename)
            
            synthesize_audio(self.text, out_path, self.voice)
            self.finished.emit(out_path, "")
        except Exception as e:
            self.finished.emit("", str(e))


# --- Rasa integration worker thread ---
class RasaWorker(QThread):
    finished = Signal(str, str) # text, error

    def __init__(self, user_text):
        super().__init__()
        self.user_text = user_text

    def run(self):
        try:
            # Call the Rasa integration function
            bot_response = send_to_rasa(self.user_text)
            self.finished.emit(bot_response, "")
        except Exception as e:
            self.finished.emit("", str(e))


# --- Analysis window ---
class AnalysisWindow(QDialog):
    def __init__(self, file_path, controller, parent=None):
        super().__init__(parent)
        self.file_path = file_path
        self.controller = controller
        self.setWindowTitle(f"Analysis: {os.path.basename(file_path)}")
        self.resize(1000, 800)
        self.setStyleSheet("background-color: #2b2b2b; color: white;")

        self.layout = QVBoxLayout(self)

        self.loading_widget = QWidget()
        loading_layout = QVBoxLayout(self.loading_widget)
        loading_layout.setAlignment(Qt.AlignCenter)
        
        lbl_loading = QLabel("Analyzing audio file...\nThis may take a few seconds.")
        lbl_loading.setAlignment(Qt.AlignCenter)
        lbl_loading.setStyleSheet("font-size: 16px; color: #BBB;")
        
        self.progress = QProgressBar()
        self.progress.setFixedWidth(400)
        self.progress.setRange(0, 0)
        self.progress.setStyleSheet("QProgressBar { border: 2px solid grey; border-radius: 5px; text-align: center; } QProgressBar::chunk { background-color: #2196F3; width: 10px; margin: 0.5px; }")

        loading_layout.addWidget(lbl_loading)
        loading_layout.addWidget(self.progress)
        self.layout.addWidget(self.loading_widget)

        self.results_widget = QWidget()
        self.results_widget.setVisible(False)
        results_layout = QVBoxLayout(self.results_widget)

        stats_group = QGroupBox("Signal Statistics")
        stats_group.setStyleSheet("QGroupBox { border: 1px solid #555; border-radius: 5px; margin-top: 10px; font-weight: bold; } QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 5px; }")
        stats_grid = QGridLayout(stats_group)

        self.lbl_duration = QLabel("Duration: ...")
        self.lbl_sr = QLabel("Sampling rate (SR): ...")
        self.lbl_rms = QLabel("RMS: ...")
        self.lbl_channels = QLabel("Channels: ...")
        
        for lbl in [self.lbl_duration, self.lbl_sr, self.lbl_rms, self.lbl_channels]:
            lbl.setStyleSheet("font-size: 14px; padding: 5px; border: none;")

        stats_grid.addWidget(self.lbl_duration, 0, 0)
        stats_grid.addWidget(self.lbl_sr, 0, 1)
        stats_grid.addWidget(self.lbl_rms, 1, 0)
        stats_grid.addWidget(self.lbl_channels, 1, 1)

        results_layout.addWidget(stats_group)

        self.figure = Figure(figsize=(5, 8), dpi=100, facecolor='#2b2b2b')
        self.canvas = FigureCanvas(self.figure)
        results_layout.addWidget(self.canvas)

        btn_export = QPushButton("Export samples to .CSV")
        btn_export.setFixedHeight(40)
        btn_export.setStyleSheet("QPushButton { background-color: #2196F3; color: white; border-radius: 5px; font-weight: bold; } QPushButton:hover { background-color: #1976D2; }")
        btn_export.clicked.connect(self.export_csv)
        results_layout.addWidget(btn_export)

        self.layout.addWidget(self.results_widget)
        self.start_analysis_thread()

    def start_analysis_thread(self):
        self.worker = AnalysisWorker(self.controller, self.file_path)
        self.worker.finished.connect(self.on_analysis_finished)
        self.worker.start()

    def on_analysis_finished(self, data):
        self.loading_widget.setVisible(False)
        self.results_widget.setVisible(True)

        if not data:
            QMessageBox.critical(self, "Error", "Failed to analyze the file. The file may be corrupted or the format is unsupported.")
            self.close()
            return

        self.audio_data = data["y"]

        self.lbl_duration.setText(f"Duration: {data['duration']:.2f} s")
        self.lbl_sr.setText(f"Sampling rate (SR): {data['sr']} Hz")
        self.lbl_rms.setText(f"RMS: {data['rms']:.4f}")
        self.lbl_channels.setText(f"Channels: {data['channels']}")

        self.figure.clear()
        
        ax1 = self.figure.add_subplot(211)
        ax1.set_facecolor('#1e1e1e')
        times = np.linspace(0, data['duration'], num=len(data['y']))
        ax1.plot(times, data['y'], color='#00e676', linewidth=0.5)
        ax1.set_title("Waveform", color='white', fontsize=10)
        ax1.set_xlabel("Time [s]", color='#AAA', fontsize=8)
        ax1.set_ylabel("Amplitude", color='#AAA', fontsize=8)
        ax1.tick_params(colors='#AAA', labelsize=8)
        ax1.grid(True, color='#444', linestyle='--', linewidth=0.5)
        
        for spine in ax1.spines.values():
            spine.set_edgecolor('#444')

        ax2 = self.figure.add_subplot(212)
        ax2.set_facecolor('#1e1e1e')
        mfcc_data = data['mfcc']
        cax = ax2.imshow(mfcc_data, aspect='auto', origin='lower', cmap='plasma')
        ax2.set_title("MFCC", color='white', fontsize=10)
        ax2.set_ylabel("Coefficients", color='#AAA', fontsize=8)
        ax2.set_xlabel("Time frames", color='#AAA', fontsize=8)
        ax2.tick_params(colors='#AAA', labelsize=8)
        
        for spine in ax2.spines.values():
            spine.set_edgecolor('#444')

        cb = self.figure.colorbar(cax, ax=ax2)
        cb.ax.yaxis.set_tick_params(color='#AAA')
        cb.outline.set_edgecolor('#444')
        if hasattr(matplotlib, 'pyplot'):
            plt_setp = list(matplotlib.pyplot.getp(cb.ax.axes, 'yticklabels')) 
            for t in cb.ax.get_yticklabels():
                t.set_color('#AAA')

        self.figure.tight_layout()
        self.canvas.draw()
        
    def export_csv(self):
        if not hasattr(self, 'audio_data'):
            return

        save_path, _ = QFileDialog.getSaveFileName(self, "Save CSV Samples", "", "CSV Files (*.csv)")
        if save_path:
            success = self.controller.export_samples_to_csv(save_path, self.audio_data)
            if success:
                QMessageBox.information(self, "Success", "CSV file saved.")
            else:
                QMessageBox.critical(self, "Error", "Failed to save the file.")


# --- Message widget (chat bubble) ---
class AudioMessageBubble(QFrame):
    request_play_signal = Signal(object)

    def __init__(self, file_path, assets_dir, is_user=True, text_content=None, parent=None):
        super().__init__(parent)
        self.file_path = file_path
        self.is_playing = False
        self.assets_dir = assets_dir
        self.text_content = text_content
        self.is_user = is_user

        self.setMaximumWidth(1500) 
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Minimum)
        self.setObjectName("ChatBubble")
        
        # Main layout
        main_layout = QVBoxLayout(self)
        main_layout.setSizeConstraint(QLayout.SetFixedSize)
        main_layout.setContentsMargins(10, 15, 10, 15)
        
        # Audio section (horizontal)
        audio_widget = QWidget()
        # CRITICAL: Forcing width here so SetFixedSize takes it into account
        audio_widget.setMinimumWidth(600) 
        audio_widget.setStyleSheet("background: transparent; border: none;")
        audio_layout = QHBoxLayout(audio_widget)
        audio_layout.setContentsMargins(0, 0, 0, 0)

        self.btn_play = QPushButton()
        self.btn_play.setFixedSize(40, 40) 
        self.btn_play.setStyleSheet("background-color: transparent; border: none;")
        
        icon_path = os.path.join(self.assets_dir, "play_icon.svg") # Changing to play_icon as file.svg might be confusing
        if not os.path.exists(icon_path):
             icon_path = os.path.join(self.assets_dir, "file.svg")

        self.btn_play.setIcon(QIcon(icon_path))
        self.btn_play.setIconSize(QSize(30, 30)) 

        self.btn_play.clicked.connect(self.on_click)
        
        lbl_info = QLabel("Audio Recording")
        lbl_info.setStyleSheet("color: #CCC; font-size: 12px; border: none; background: transparent;")
        
        audio_layout.addWidget(self.btn_play)
        audio_layout.addWidget(lbl_info)
        audio_layout.addStretch()

        main_layout.addWidget(audio_widget)

        # Text section (if transcription exists)
        if self.text_content:
            self.lbl_text = QLabel(self.text_content)
            self.lbl_text.setWordWrap(True)
            self.lbl_text.setStyleSheet("color: white; font-size: 14px; margin-top: 5px; border: none; background: transparent;")
            self.lbl_text.setTextInteractionFlags(Qt.TextSelectableByMouse)
            main_layout.addWidget(self.lbl_text)
            
        self.update_style()

    def update_style(self):
        # Colors: User = Left (default/dark), Bot = Right (different color)
        # User requested: User Left (Standard), Bot Right.
        # Differentiating colors slightly.
        
        border_color = "#444"
        bg_color = "#333" if self.is_user else "#2b3b4b" # Bot slightly blueish
        
        if self.is_playing:
            border_color = "#00FF00"
            
        base_style = f"""
            QFrame#ChatBubble {{
                background-color: {bg_color};
                border-radius: 15px;
                border: 1px solid {border_color};
            }}
        """
        if self.is_playing:
             base_style = f"""
            QFrame#ChatBubble {{
                background-color: {bg_color};
                border-radius: 15px;
                border: 2px solid #00FF00;
            }}
        """
        
        self.setStyleSheet(base_style)

    def on_click(self):
        self.request_play_signal.emit(self)

    def set_playing_state(self, is_playing):
        self.is_playing = is_playing
        self.update_style()


# --- Bottom bar with record button ---
# --- Bottom bar with record button was removed ---


# --- Chat page ---
class ChatPage(QWidget):
    register_chat_bubble_signal = Signal(object)

    def __init__(self, controller, assets_dir, parent=None):
        super().__init__(parent)
        self.controller = controller
        self.assets_dir = assets_dir
        self.current_temp_recording = None
        self.is_uploaded_file = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setStyleSheet("border: none; background-color: transparent;")
        
        self.chat_container = QWidget()
        self.chat_layout = QVBoxLayout(self.chat_container)
        self.chat_layout.setAlignment(Qt.AlignTop) 
        self.chat_layout.setSpacing(10)
        
        self.scroll_area.setWidget(self.chat_container)
        layout.addWidget(self.scroll_area)
        
        # --- Bottom panel (Settings + Controls + Spacer) ---
        bottom_container = QWidget()
        bottom_layout = QHBoxLayout(bottom_container)
        bottom_layout.setContentsMargins(0, 0, 0, 0)
        
        # 1. Settings Button (Bottom left)
        self.btn_settings = QPushButton()
        self.btn_settings.setFixedSize(40, 40)
        self.btn_settings.setToolTip("Settings")
        # Icon
        settings_icon = os.path.join(self.assets_dir, "settings_icon.svg")
        self.btn_settings.setIcon(QIcon(settings_icon))
        self.btn_settings.setIconSize(QSize(28, 28)) 
        self.btn_settings.setStyleSheet("background-color: transparent; border: none;")

        self.btn_settings.clicked.connect(self.open_settings)
        
        # 2. Controls Panel (Center)
        self.controls_widget = QWidget()
        self.controls_widget.setFixedHeight(150)
        controls_layout = QVBoxLayout(self.controls_widget)
        
        self.btn_start_chat = QPushButton("Start new chat")
        self.btn_start_chat.setFixedSize(200, 50)
        self.btn_start_chat.setStyleSheet("background-color: #4CAF50; color: white; border-radius: 25px; font-weight: bold; font-size: 14px;")
        self.btn_start_chat.clicked.connect(self.start_new_chat)
        
        self.recording_panel = QWidget()
        self.recording_panel.setVisible(False)
        
        rec_panel_main_layout = QVBoxLayout(self.recording_panel)
        rec_panel_main_layout.setAlignment(Qt.AlignCenter)
        rec_panel_main_layout.setSpacing(10)
        
        row1_layout = QHBoxLayout()
        row1_layout.addStretch() 
        
        self.btn_upload = QPushButton()
        self.btn_upload.setFixedSize(40, 40)
        self.btn_upload.setToolTip("Load audio file from disk")
        self.set_icon(self.btn_upload, "attachment_icon.svg") 
        self.btn_upload.setIconSize(QSize(22, 22))
            
        self.btn_upload.setStyleSheet("""
            QPushButton { background-color: #444; border-radius: 20px; border: 1px solid #555; }
            QPushButton:hover { background-color: #555; border: 1px solid #777; }
        """)
        self.btn_upload.clicked.connect(self.upload_audio_file)

        self.btn_record = QPushButton()
        self.btn_record.setObjectName("ChatRecordButton") 
        self.btn_record.setFixedSize(60, 60)
        self.set_icon(self.btn_record, "mic_icon.svg")
        
        self.btn_record.setStyleSheet("""
            /* IDLE STATE: GREEN */
            QPushButton#ChatRecordButton {
                background-color: #4CAF50; 
                border-radius: 30px; 
                border: 2px solid #388E3C;
            }
            QPushButton#ChatRecordButton:hover {
                background-color: #43A047;
            }

            /* RECORDING STATE: RED/PINK */
            QPushButton#ChatRecordButton[recording_state="true"] {
                background-color: #E91E63; 
                border: 2px solid #C2185B;
            }
            QPushButton#ChatRecordButton[recording_state="true"]:hover {
                background-color: #D81B60;
            }
        """)
        self.btn_record.clicked.connect(self.toggle_recording)
        
        self.btn_preview = QPushButton()
        self.btn_preview.setFixedSize(40,40)
        self.btn_preview.setToolTip("Preview recording")
        self.set_icon(self.btn_preview, "play_icon.svg")
        self.btn_preview.setStyleSheet("background-color: #444; border-radius: 10px;")
        self.btn_preview.clicked.connect(self.preview_recording)
        self.btn_preview.setIconSize(QSize(22, 22))
        
        row1_layout.addWidget(self.btn_upload) 
        row1_layout.addWidget(self.btn_record) 
        row1_layout.addWidget(self.btn_preview) 
        row1_layout.addStretch() 
        
        row2_layout = QHBoxLayout()
        row2_layout.addStretch() 
        
        self.btn_send = QPushButton("Send")
        self.btn_send.setStyleSheet("""
            QPushButton { background-color: #2196F3; color: white; border-radius: 5px; padding: 5px; font-weight: bold; width: 80px; }
            QPushButton:disabled { background-color: #333; color: #555; }
        """)
        self.btn_send.clicked.connect(self.send_message)
        
        self.btn_delete = QPushButton("Delete")
        self.btn_delete.setStyleSheet("""
            QPushButton { background-color: #F44336; color: white; border-radius: 5px; padding: 5px; font-weight: bold; width: 80px; }
            QPushButton:disabled { background-color: #333; color: #555; }
        """)
        self.btn_delete.clicked.connect(self.delete_current_recording)
        
        row2_layout.addWidget(self.btn_delete)
        row2_layout.addWidget(self.btn_send)
        row2_layout.addStretch()

        rec_panel_main_layout.addLayout(row1_layout)
        rec_panel_main_layout.addLayout(row2_layout)

        controls_layout.addWidget(self.btn_start_chat, alignment=Qt.AlignCenter)
        controls_layout.addWidget(self.recording_panel)
        
        # 3. Dummy Spacer (Bottom right) - to center controls
        dummy_spacer = QWidget()
        dummy_spacer.setFixedSize(40, 40)
        dummy_spacer.setStyleSheet("background: transparent;")

        # Assembling bottom
        bottom_layout.addWidget(self.btn_settings, 0, Qt.AlignBottom | Qt.AlignLeft)
        bottom_layout.addStretch()
        bottom_layout.addWidget(self.controls_widget, 0, Qt.AlignCenter)
        bottom_layout.addStretch()
        bottom_layout.addWidget(dummy_spacer, 0, Qt.AlignBottom | Qt.AlignRight)
        
        layout.addWidget(bottom_container)
        self.reset_recording_ui()

    def set_icon(self, button, icon_name):
        path = os.path.join(self.assets_dir, icon_name)
        if os.path.exists(path):
            button.setIcon(QIcon(path))
            button.setIconSize(QSize(30, 30))

    def start_new_chat(self):
        self.btn_start_chat.setVisible(False)
        self.recording_panel.setVisible(True)
        while self.chat_layout.count():
            item = self.chat_layout.takeAt(0)
            if item.widget(): item.widget().deleteLater()

    def reset_recording_ui(self):
        self.current_temp_recording = None
        self.is_uploaded_file = False 
        self.set_icon(self.btn_record, "mic_icon.svg")
        self.btn_record.setProperty("recording_state", False)
        self.btn_record.style().unpolish(self.btn_record)
        self.btn_record.style().polish(self.btn_record)
        self.btn_preview.setEnabled(False)
        self.btn_send.setEnabled(False)
        self.btn_delete.setEnabled(False)
        self.btn_preview.setStyleSheet("background-color: #222; border-radius: 20px; border: 1px solid #333;")
        self.btn_upload.setEnabled(True)
        self.btn_record.setEnabled(True)

    def upload_audio_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select audio file", "", "Audio files (*.wav *.mp3 *.m4a *.flac);;All files (*.*)"
        )
        if file_path:
            self.current_temp_recording = file_path
            self.is_uploaded_file = True 
            self.btn_preview.setEnabled(True)
            self.btn_send.setEnabled(True)
            self.btn_delete.setEnabled(True)
            self.btn_preview.setStyleSheet("background-color: #444; border-radius: 20px;")

    def toggle_recording(self):
        if not self.btn_record.property("recording_state"):
            self.reset_recording_ui()
            self.btn_record.setProperty("recording_state", True)
            self.set_icon(self.btn_record, "stop_record.svg") 
            self.btn_upload.setEnabled(False) 
            self.controller.start_recording()
        else:
            self.btn_record.setProperty("recording_state", False)
            self.set_icon(self.btn_record, "mic_icon.svg")
            file_path = self.controller.stop_recording()
            if file_path:
                self.current_temp_recording = file_path
                self.is_uploaded_file = False 
                self.btn_preview.setEnabled(True)
                self.btn_send.setEnabled(True)
                self.btn_delete.setEnabled(True)
                self.btn_preview.setStyleSheet("background-color: #444; border-radius: 20px;")
                self.btn_upload.setEnabled(True) 
            else:
                QMessageBox.warning(self, "Error", "Recording is empty or save error.")
                self.btn_upload.setEnabled(True)
        self.btn_record.style().unpolish(self.btn_record)
        self.btn_record.style().polish(self.btn_record)

    def preview_recording(self):
        if self.current_temp_recording:
            self.controller.play_audio(self.current_temp_recording)

    def delete_current_recording(self):
        if self.current_temp_recording:
            self.controller.stop_audio()
            if not self.is_uploaded_file:
                try:
                    os.remove(self.current_temp_recording)
                except:
                    pass
            self.reset_recording_ui()

    def send_message(self):
        if not self.current_temp_recording or not os.path.exists(self.current_temp_recording):
            QMessageBox.warning(self, "Error", "No recording to send.")
            return

        # 1. Add bubble (temporarily without text or with info "Processing...")
        # Actually, the user wants transcription IN the bubble. So we wait with adding the bubble (or update it).
        # Approach: Block UI, start thread, when it returns add bubble with text.
        
        self.toggle_ui_enabled(False)
        
        # Create worker
        self.asr_worker = AsrWorker(self.current_temp_recording)
        self.asr_worker.finished.connect(self.on_asr_finished)
        self.asr_worker.start()

    def on_asr_finished(self, text, error):
        # --- 1. User message (left side) ---
        if error:
            QMessageBox.warning(self, "ASR Error", f"An error occurred during speech recognition:\n{error}")
            bubble = AudioMessageBubble(self.current_temp_recording, self.assets_dir, is_user=True, text_content=f"[ASR Error: {error}]")
            self.chat_layout.addWidget(bubble, alignment=Qt.AlignLeft)
            self.toggle_ui_enabled(True) 
        else:
            bubble = AudioMessageBubble(self.current_temp_recording, self.assets_dir, is_user=True, text_content=text)
            self.chat_layout.addWidget(bubble, alignment=Qt.AlignLeft)
            
            # --- 2. Rasa processing ---
            # Instead of starting TTS right away, we ask Rasa
            self.rasa_worker = RasaWorker(text)
            self.rasa_worker.finished.connect(self.on_rasa_finished)
            self.rasa_worker.start()

        self.register_chat_bubble_signal.emit(bubble)
        
        self.reset_recording_ui()

    def on_rasa_finished(self, bot_text, error):
        if error:
            self.toggle_ui_enabled(True)
            QMessageBox.warning(self, "Rasa Error", f"Failed to communicate with bot:\n{error}")
            return
            
        # Once we have text response, proceed with TTS
        self.start_bot_response(bot_text)

    def start_bot_response(self, text):
        # Get selected voice from MainWindow (if available)
        main_win = self.window()
        voice_name = "masza"
        if isinstance(main_win, MainWindow):
            voice_name = main_win.selected_voice

        self.tts_worker = TtsWorker(text, voice=voice_name)
        self.tts_worker.finished.connect(lambda path, err: self.on_tts_finished(path, err, text))
        self.tts_worker.start()
        
    def on_tts_finished(self, file_path, error, text_content):
        self.toggle_ui_enabled(True)
        
        if error:
            QMessageBox.warning(self, "TTS Error", f"Synthesis error:\n{error}")
            return
            
        # --- 3. Bot message (right side) ---
        bubble = AudioMessageBubble(file_path, self.assets_dir, is_user=False, text_content=text_content)
        self.chat_layout.addWidget(bubble, alignment=Qt.AlignRight)
        
        self.register_chat_bubble_signal.emit(bubble)

    def toggle_ui_enabled(self, enabled):
        self.btn_send.setEnabled(enabled)
        self.btn_record.setEnabled(enabled)
        self.btn_upload.setEnabled(enabled)
        self.btn_delete.setEnabled(enabled)
        if enabled and self.current_temp_recording:
             self.btn_preview.setEnabled(True)
        else:
             self.btn_preview.setEnabled(enabled)

    def open_settings(self):
        main_win = self.window()
        if hasattr(main_win, 'open_settings_dialog'):
            main_win.open_settings_dialog()


# --- Settings dialog window ---
class SettingsDialog(QDialog):
    def __init__(self, controller, main_window, parent=None):
        super().__init__(parent)
        self.controller = controller
        self.main_window = main_window
        self.setWindowTitle("Settings")
        self.resize(500, 600)
        self.setStyleSheet("background-color: #2b2b2b; color: white;")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 40, 40, 40)
        layout.setSpacing(20)

        title = QLabel("Settings")
        title.setStyleSheet("font-size: 24px; font-weight: bold; color: white; margin-bottom: 20px;")
        layout.addWidget(title)
        
        # --- AI Model Selection ---
        group_model = QGroupBox("AI Model")
        group_model.setStyleSheet("QGroupBox { color: #BBB; border: 1px solid #444; border-radius: 5px; margin-top: 10px; font-weight: bold; } QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 5px; }")
        layout_model = QFormLayout(group_model)
        
        self.combo_model = QComboBox()
        self.combo_model.addItems(["Techmo", "Whisper AI"])
        self.combo_model.setCurrentText(self.main_window.selected_model)
        self.combo_model.setStyleSheet("QComboBox { padding: 5px; background-color: #333; color: white; border: 1px solid #555; }")
        self.combo_model.currentTextChanged.connect(self.on_model_changed)
        
        layout_model.addRow("Select model:", self.combo_model)
        layout.addWidget(group_model)
        
        # --- Voice Selection (Techmo only) ---
        self.group_voice = QGroupBox("TTS Voice (Techmo)")
        self.group_voice.setStyleSheet("QGroupBox { color: #BBB; border: 1px solid #444; border-radius: 5px; margin-top: 10px; font-weight: bold; } QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 5px; }")
        self.group_voice.setVisible(self.main_window.selected_model == "Techmo")
        
        layout_voice = QHBoxLayout(self.group_voice)
        
        lbl_voice = QLabel("Select voice:")
        lbl_voice.setStyleSheet("color: #DDD;")
        
        self.combo_voice = QComboBox()
        self.combo_voice.addItems(["masza", "michał"]) 
        self.combo_voice.setCurrentText(self.main_window.selected_voice)
        self.combo_voice.setStyleSheet("QComboBox { padding: 5px; background-color: #333; color: white; border: 1px solid #555; min-width: 100px; }")
        self.combo_voice.currentTextChanged.connect(self.on_voice_changed)
        
        self.btn_preview_voice = QPushButton("Preview")
        self.btn_preview_voice.setStyleSheet("QPushButton { background-color: #4CAF50; color: white; border-radius: 5px; padding: 5px 15px; } QPushButton:hover { background-color: #45a049; }")
        self.btn_preview_voice.clicked.connect(self.preview_voice)
        
        layout_voice.addWidget(lbl_voice)
        layout_voice.addWidget(self.combo_voice)
        layout_voice.addWidget(self.btn_preview_voice)
        layout_voice.addStretch()
        
        layout.addWidget(self.group_voice)

        # --- Audio Devices ---
        group_audio = QGroupBox("Audio Devices")
        group_audio.setStyleSheet("QGroupBox { color: #BBB; border: 1px solid #444; border-radius: 5px; margin-top: 10px; font-weight: bold; } QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 5px; }")
        audio_layout = QFormLayout(group_audio)
        audio_layout.setLabelAlignment(Qt.AlignLeft)
        audio_layout.setFormAlignment(Qt.AlignLeft | Qt.AlignTop)
        
        self.combo_input = QComboBox()
        self.combo_input.setFixedWidth(300)
        self.combo_input.setStyleSheet("QComboBox { background-color: #333; color: white; padding: 5px; border: 1px solid #555; } QComboBox::drop-down { border: none; }")
        self.combo_input.currentIndexChanged.connect(self.change_input_device)
        
        self.combo_output = QComboBox()
        self.combo_output.setFixedWidth(300)
        self.combo_output.setStyleSheet("QComboBox { background-color: #333; color: white; padding: 5px; border: 1px solid #555; } QComboBox::drop-down { border: none; }")
        self.combo_output.currentIndexChanged.connect(self.change_output_device)

        lbl_mic = QLabel("Microphone:")
        lbl_mic.setStyleSheet("color: #DDD;")
        lbl_spk = QLabel("Speakers:")
        lbl_spk.setStyleSheet("color: #DDD;")

        audio_layout.addRow(lbl_mic, self.combo_input)
        audio_layout.addRow(lbl_spk, self.combo_output)
        
        btn_refresh_devices = QPushButton("Refresh device list")
        btn_refresh_devices.setFixedWidth(200)
        btn_refresh_devices.setStyleSheet("background-color: #444; color: white; padding: 5px; border-radius: 4px; margin-top: 10px;")
        btn_refresh_devices.clicked.connect(self.refresh_devices_list)
        audio_layout.addRow(QWidget(), btn_refresh_devices)

        layout.addWidget(group_audio)
        layout.addStretch()

        self.refresh_devices_list()

    def refresh_devices_list(self):
        self.combo_input.blockSignals(True)
        self.combo_input.clear()
        input_devices = self.controller.get_input_devices()
        for idx, name in input_devices:
            self.combo_input.addItem(f"{idx}: {name}", userData=idx)
            # Restore selection
            if idx == self.controller.input_device_index:
                 self.combo_input.setCurrentIndex(self.combo_input.count()-1)

        self.combo_input.blockSignals(False)

        self.combo_output.blockSignals(True)
        self.combo_output.clear()
        output_devices = self.controller.get_output_devices()
        current_out = self.controller.audio_output.device()
        for dev in output_devices:
            self.combo_output.addItem(dev.description(), userData=dev)
             # Restore selection
            if dev.id() == current_out.id():
                self.combo_output.setCurrentIndex(self.combo_output.count()-1)
        self.combo_output.blockSignals(False)

    def change_input_device(self, index):
        if index >= 0:
            dev_idx = self.combo_input.itemData(index)
            self.controller.set_input_device(dev_idx)

    def change_output_device(self, index):
        if index >= 0:
            dev_obj = self.combo_output.itemData(index)
            self.controller.set_output_device(dev_obj)

    def on_model_changed(self, text):
        self.main_window.selected_model = text
        if text == "Techmo":
            self.group_voice.setVisible(True)
        else:
            self.group_voice.setVisible(False)

    def on_voice_changed(self, text):
        self.main_window.selected_voice = text

    def preview_voice(self):
        voice = self.main_window.selected_voice
        text = f"Jestem głos {voice}."
        
        self.btn_preview_voice.setEnabled(False)
        self.btn_preview_voice.setText("Generating...")
        
        self.preview_worker = TtsWorker(text, voice=voice)
        self.preview_worker.finished.connect(self.on_preview_finished)
        self.preview_worker.start()
        
    def on_preview_finished(self, file_path, error):
        self.btn_preview_voice.setEnabled(True)
        self.btn_preview_voice.setText("Preview")
        
        if error:
            QMessageBox.warning(self, "Preview Error", f"Failed to generate preview:\n{error}")
            return
            
        if file_path and os.path.exists(file_path):
            self.controller.play_audio(file_path)


# --- Main window class ---
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("FAQ VoiceBot Interface")
        self.resize(1000, 700)

        # LOGIC INITIALIZATION
        self.controller = AudioController()
        self.controller.playback_finished.connect(self.on_playback_finished)
        
        self.current_playing_widget = None

        self.base_dir = os.path.dirname(__file__)
        self.assets_dir = os.path.join(self.base_dir, "assets")

        self.selected_model = "Techmo"
        self.selected_voice = "masza"

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Chatbot
        self.chat_page = ChatPage(self.controller, self.assets_dir)
        main_layout.addWidget(self.chat_page)
        
        # Connect chat page signals to main window
        self.chat_page.register_chat_bubble_signal.connect(self.register_chat_bubble)

    def open_settings_dialog(self):
        dialog = SettingsDialog(self.controller, self, self)
        dialog.exec()

    def register_chat_bubble(self, bubble):
        # Auxiliary connection for bubble playback with the controller
        bubble.request_play_signal.connect(lambda b: self.controller.play_audio(b.file_path))
        # Handling visual update of the playback state
        bubble.request_play_signal.connect(self.set_active_bubble)
        
    def set_active_bubble(self, bubble):
        if self.current_playing_widget and self.current_playing_widget != bubble:
             self.current_playing_widget.set_playing_state(False)
        
        self.current_playing_widget = bubble
        bubble.set_playing_state(True)
        
    def on_playback_finished(self):
        if self.current_playing_widget:
            self.current_playing_widget.set_playing_state(False)
            self.current_playing_widget = None