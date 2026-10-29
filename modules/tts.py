import queue
import threading
import os
import tempfile


class TTSEngine:
    """Lee en voz alta con gTTS (requiere internet) y reproduce con pygame."""

    def __init__(self, lang="es"):
        self.lang = lang
        self.enabled = True
        self._queue = queue.Queue()
        self._thread = threading.Thread(target=self._worker, daemon=True)
        self._thread.start()
        print("[TTS] Motor iniciado correctamente")

    def _worker(self):
        mixer = None
        while True:
            word = self._queue.get()
            if word is None:
                break
            tmp_path = None
            try:
                from gtts import gTTS
                if mixer is None:
                    os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
                    from pygame import mixer as pg_mixer
                    pg_mixer.init()
                    mixer = pg_mixer

                tmp_fd, tmp_path = tempfile.mkstemp(suffix=".mp3")
                os.close(tmp_fd)
                gTTS(text=word, lang=self.lang, slow=False).save(tmp_path)

                mixer.music.load(tmp_path)
                mixer.music.play()
                while mixer.music.get_busy():
                    threading.Event().wait(0.05)
                mixer.music.unload()
                print(f"[TTS] Dijo: {word}")
            except Exception as e:
                print(f"[TTS] Error: {e}")
            finally:
                if tmp_path:
                    try:
                        os.remove(tmp_path)
                    except OSError:
                        pass

    def speak(self, word: str):
        if not self.enabled or not word:
            return
        # Solo importa lo más reciente: descartar lo que siga en cola
        while not self._queue.empty():
            try:
                self._queue.get_nowait()
            except queue.Empty:
                break
        self._queue.put(word)

    def toggle(self):
        self.enabled = not self.enabled
        estado = "Activado" if self.enabled else "Desactivado"
        print(f"[TTS] {estado}")
        return self.enabled

    def shutdown(self):
        self._queue.put(None)
