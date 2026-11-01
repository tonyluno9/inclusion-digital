import json
import os
import queue
import threading


class STTController:
    """Graba la voz del interlocutor mientras está activo y la pasa a texto.

    Intenta Google (en línea) y después Vosk (local) si está instalado.
    `last_error` describe en español por qué no hubo texto, para mostrarlo en pantalla.
    """

    def __init__(self, model_path, use_online=True):
        self.model_path = model_path
        self.use_online = use_online
        self.is_recording = False
        self.last_error = ""
        self._result_queue = queue.Queue()
        self._audio_thread = None
        self._vosk_model = None
        self._load_vosk()

    def _load_vosk(self):
        if not os.path.exists(self.model_path):
            return
        try:
            from vosk import Model
            self._vosk_model = Model(self.model_path)
            print(f"[STT] Vosk cargado desde {self.model_path}")
        except Exception as e:
            print(f"[STT] Vosk no disponible: {e}")

    def _transcribe_vosk(self, audio_data, sample_rate):
        from vosk import KaldiRecognizer
        rec = KaldiRecognizer(self._vosk_model, sample_rate)
        rec.AcceptWaveform(audio_data)
        return json.loads(rec.FinalResult()).get("text", "").strip()

    def _transcribe_google(self, audio_data, sample_rate):
        import io
        import wave
        import speech_recognition as sr
        wav_buffer = io.BytesIO()
        with wave.open(wav_buffer, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(sample_rate)
            wf.writeframes(audio_data)
        wav_buffer.seek(0)
        recognizer = sr.Recognizer()
        with sr.AudioFile(wav_buffer) as source:
            audio = recognizer.record(source)
        return recognizer.recognize_google(audio, language="es-MX").strip()

    def _record(self, rate=16000, chunk=1024):
        import pyaudio
        p = pyaudio.PyAudio()
        try:
            stream = p.open(format=pyaudio.paInt16, channels=1, rate=rate, input=True, frames_per_buffer=chunk)
            frames = []
            while self.is_recording:
                frames.append(stream.read(chunk, exception_on_overflow=False))
            stream.stop_stream()
            stream.close()
            return b"".join(frames)
        finally:
            p.terminate()

    def transcribe(self, audio_data, rate=16000):
        """Devuelve (texto, error). Prueba los motores disponibles en orden."""
        engines = []
        if self.use_online:
            engines.append(("Google", self._transcribe_google))
        if self._vosk_model is not None:
            engines.append(("Vosk", self._transcribe_vosk))
        if not engines:
            return "", "Voz a texto sin motor: instala requirements-opcional.txt"
        errors = []
        for name, engine in engines:
            try:
                text = engine(audio_data, rate)
                if text:
                    return text, ""
                errors.append(f"{name}: no entendió")
            except ImportError:
                errors.append(f"{name}: no instalado")
            except Exception as e:
                errors.append(f"{name}: {type(e).__name__}")
        return "", "No se entendió la voz (" + "; ".join(errors) + ")"

    def _record_and_transcribe(self):
        try:
            try:
                audio_data = self._record()
            except ImportError:
                self.last_error = "Falta pyaudio: pip install -r requirements-opcional.txt"
                return
            except Exception as e:
                self.last_error = f"No se pudo usar el micrófono ({type(e).__name__})"
                return
            if not audio_data:
                return
            try:
                text, error = self.transcribe(audio_data)
            except Exception as e:
                text, error = "", f"Error al pasar la voz a texto ({type(e).__name__})"
            self.last_error = error
            if text:
                self._result_queue.put(text)
        finally:
            self.is_recording = False

    def start_recording(self):
        if self.is_recording:
            return
        self.last_error = ""
        self.is_recording = True
        self._audio_thread = threading.Thread(target=self._record_and_transcribe, daemon=True)
        self._audio_thread.start()

    def stop_recording(self):
        self.is_recording = False

    def get_result(self):
        try:
            return self._result_queue.get_nowait()
        except queue.Empty:
            return None
