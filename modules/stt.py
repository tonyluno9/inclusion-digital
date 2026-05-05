import threading
import queue
import os

class STTController:
    def __init__(self, model_path, lang="es"):
        self.model_path = model_path
        self.lang = lang
        self.enabled = True
        self.is_recording = False
        self._result_queue = queue.Queue()
        self._audio_thread = None
        self._vosk_model = None
        self._load_vosk()

    def _load_vosk(self):
        try:
            from vosk import Model
            if os.path.exists(self.model_path):
                self._vosk_model = Model(self.model_path)
                print(f"[STT] Vosk cargado desde {self.model_path}")
            else:
                print(f"[STT] Modelo Vosk no encontrado en {self.model_path}")
        except Exception as e:
            print(f"[STT] Vosk no disponible: {e}")

    def _transcribe_vosk(self, audio_data, sample_rate):
        try:
            from vosk import KaldiRecognizer
            import json
            rec = KaldiRecognizer(self._vosk_model, sample_rate)
            rec.AcceptWaveform(audio_data)
            result = json.loads(rec.FinalResult())
            return result.get("text", "").strip()
        except Exception as e:
            print(f"[STT] Error Vosk: {e}")
            return ""

    def _transcribe_google(self, audio_data, sample_rate):
        try:
            import speech_recognition as sr
            import io
            import wave
            recognizer = sr.Recognizer()
            wav_buffer = io.BytesIO()
            with wave.open(wav_buffer, 'wb') as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(sample_rate)
                wf.writeframes(audio_data)
            wav_buffer.seek(0)
            with sr.AudioFile(wav_buffer) as source:
                audio = recognizer.record(source)
            text = recognizer.recognize_google(audio, language="es-MX")
            return text.strip()
        except Exception as e:
            print(f"[STT] Google STT falló: {e}")
            return ""

    def _record_and_transcribe(self):
        try:
            import pyaudio
            RATE = 16000
            CHUNK = 1024
            p = pyaudio.PyAudio()
            stream = p.open(
                format=pyaudio.paInt16,
                channels=1,
                rate=RATE,
                input=True,
                frames_per_buffer=CHUNK
            )
            print("[STT] Grabando...")
            frames = []
            while self.is_recording:
                data = stream.read(CHUNK, exception_on_overflow=False)
                frames.append(data)
            stream.stop_stream()
            stream.close()
            p.terminate()
            print("[STT] Procesando audio...")
            audio_data = b"".join(frames)
            if not audio_data:
                return
            # Intentar Google primero, fallback a Vosk
            text = self._transcribe_google(audio_data, RATE)
            if not text and self._vosk_model:
                print("[STT] Fallback a Vosk...")
                text = self._transcribe_vosk(audio_data, RATE)
            if text:
                print(f"[STT] Transcripción: {text}")
                self._result_queue.put(text)
            else:
                print("[STT] No se detectó texto")
        except Exception as e:
            print(f"[STT] Error en grabación: {e}")

    def start_recording(self):
        if self.is_recording:
            return
        self.is_recording = True
        self._audio_thread = threading.Thread(
            target=self._record_and_transcribe,
            daemon=True
        )
        self._audio_thread.start()

    def stop_recording(self):
        self.is_recording = False

    def get_result(self):
        try:
            return self._result_queue.get_nowait()
        except queue.Empty:
            return None

    def toggle(self):
        self.enabled = not self.enabled
        estado = "Activado" if self.enabled else "Desactivado"
        print(f"[STT] {estado}")
        return self.enabled
