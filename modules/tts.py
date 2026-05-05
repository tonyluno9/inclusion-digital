import queue
import threading
import os
import tempfile

class TTSEngine:
    def __init__(self, lang="es"):
        self.lang = lang
        self.enabled = True
        self._last_word = ""
        self._queue = queue.Queue()
        self._thread = threading.Thread(target=self._worker, daemon=True)
        self._thread.start()
        print("[TTS] Motor iniciado correctamente")

    def _worker(self):
        while True:
            word = self._queue.get()
            if word is None:
                break
            try:
                from gtts import gTTS
                from playsound import playsound

                tmp_fd, tmp_path = tempfile.mkstemp(suffix=".mp3")
                os.close(tmp_fd)

                tts = gTTS(text=word, lang=self.lang, slow=False)
                tts.save(tmp_path)
                playsound(tmp_path)

                try:
                    os.remove(tmp_path)
                except Exception:
                    pass

                print(f"[TTS] Dijo: {word}")

            except Exception as e:
                print(f"[TTS] Error: {e}")

    def speak(self, word: str):
        if not self.enabled:
            return
        if not word:
            return
        while not self._queue.empty():
            try:
                self._queue.get_nowait()
            except queue.Empty:
                break
        self._queue.put(word)

    def process(self):
        pass  # ya no se necesita, el hilo corre solo

    def toggle(self):
        self.enabled = not self.enabled
        self._last_word = ""
        estado = "Activado" if self.enabled else "Desactivado"
        print(f"[TTS] {estado}")
        return self.enabled

    def reset(self):
        self._last_word = ""

    def shutdown(self):
        self._queue.put(None)
