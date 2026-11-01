import queue
import threading
import os
import tempfile


def pick_spanish_voice(voices):
    """Elige la voz del sistema: español de México, luego cualquier español."""
    def score(voice):
        desc = f"{voice.id} {voice.name} {getattr(voice, 'languages', '')}".lower()
        if "es-mx" in desc or "es_mx" in desc or "mexic" in desc:
            return 2
        if "spanish" in desc or "español" in desc or "es-" in desc or "es_" in desc:
            return 1
        return 0
    best = max(voices, key=score, default=None)
    return best if best is not None and score(best) > 0 else None


class TTSEngine:
    """Lee en voz alta en un hilo aparte.

    Usa la voz de Google (gTTS, requiere internet) y si falla o está apagada,
    la voz del sistema (pyttsx3). Expone `speaking` y `last_error` para que la
    interfaz muestre el estado: la persona Sorda no oye si la voz funcionó.
    """

    def __init__(self, lang="es", use_online=True):
        self.lang = lang
        self.use_online = use_online
        self.enabled = True
        self.speaking = False
        self.last_error = ""
        self._queue = queue.Queue()
        self._mixer = None
        self._offline = None
        self._thread = threading.Thread(target=self._worker, daemon=True)
        self._thread.start()

    def _speak_online(self, text):
        from gtts import gTTS
        if self._mixer is None:
            os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
            from pygame import mixer
            mixer.init()
            self._mixer = mixer
        tmp_fd, tmp_path = tempfile.mkstemp(suffix=".mp3")
        os.close(tmp_fd)
        try:
            gTTS(text=text, lang=self.lang, slow=False).save(tmp_path)
            self._mixer.music.load(tmp_path)
            self._mixer.music.play()
            while self._mixer.music.get_busy():
                threading.Event().wait(0.05)
            self._mixer.music.unload()
        finally:
            try:
                os.remove(tmp_path)
            except OSError:
                pass

    def _speak_offline(self, text):
        import pyttsx3
        if self._offline is None:
            engine = pyttsx3.init()
            voice = pick_spanish_voice(engine.getProperty("voices"))
            if voice is not None:
                engine.setProperty("voice", voice.id)
            self._offline = engine
        self._offline.say(text)
        self._offline.runAndWait()

    def _worker(self):
        while True:
            text = self._queue.get()
            if text is None:
                break
            self.speaking = True
            errors = []
            for speak in ((self._speak_online, self._speak_offline) if self.use_online else (self._speak_offline,)):
                try:
                    speak(text)
                    self.last_error = ""
                    break
                except Exception as e:
                    errors.append(f"{type(e).__name__}: {e}")
            else:
                self.last_error = "No se pudo reproducir la voz"
                print(f"[TTS] Error: {' | '.join(errors)}")
            self.speaking = False

    def speak(self, text: str):
        if not self.enabled or not text:
            return
        # Solo importa lo más reciente: descartar lo que siga en cola
        while not self._queue.empty():
            try:
                self._queue.get_nowait()
            except queue.Empty:
                break
        self._queue.put(text)

    def toggle(self):
        self.enabled = not self.enabled
        return self.enabled

    def shutdown(self):
        self._queue.put(None)
