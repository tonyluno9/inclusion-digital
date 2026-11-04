"""Lógica de la aplicación, separada del bucle de cámara.

`InclusionApp.process_frame(frame)` recibe un frame BGR de la cámara y devuelve
el frame con la interfaz dibujada; `handle_key(key)` procesa una tecla y
devuelve False cuando hay que salir. Así la app completa se puede probar con
frames y teclas simuladas (ver tests/test_app.py).
"""
import threading
import time

import cv2

import config as C
from modules.beep import beep_error, beep_start, beep_stop
from modules.coherence import make_coherent
from modules.data_collector import DataCollector
from modules.gesture_logic import GestureLogic
from modules.landmarks import hands_present, pose_valid
from modules.motion import ClipStore, LiveSender, LiveSmoother, MotionRecorder, make_clip
from modules.segmenter import SignSegmenter
from train_model import train
from ui.display import DisplayUI, View
from ui.text_input import TextPrompt

HELP_LINES = [
    "t\tEntrenar una palabra",
    "a\tAvatar: grabar el movimiento de una palabra",
    "Espacio\t(entrenamiento / avatar) activar / pausar la grabación",
    "z\t(entrenamiento / avatar) deshacer la última toma",
    "d\tModo detección",
    "e\tEntrenar el modelo",
    "r\tRecargar el modelo",
    "i\tEstadísticas del dataset",
    "x\tBorrar una seña del dataset",
    "s\tVoz del interlocutor a texto (iniciar / terminar)",
    "v\tActivar / desactivar la voz",
    "f\tPantalla completa",
    "h\tMostrar / ocultar esta ayuda",
    "q / Esc\tSalir",
]

GREEN = (80, 220, 80)
RED = (40, 40, 230)


class InclusionApp:
    def __init__(self, detector, tts, stt, collector=None, logic=None, coherence=make_coherent,
                 trainer=train, clock=time.monotonic, background=True, clips=None, sender=None):
        self.detector = detector
        self.tts = tts
        self.stt = stt
        self.collector = collector or DataCollector(C.DATASET_PATH, C.BACKUP_DIR, C.BACKUP_EVERY, C.SEQUENCE_LENGTH)
        self.logic = logic or GestureLogic(C.MODEL_PATH, C.FEATURE_VERSION, C.SEQUENCE_LENGTH, C.MIN_CONFIDENCE)
        self.clips = clips or ClipStore(C.AVATAR_DIR)
        self.sender = sender or LiveSender(C.AVATAR_UDP_HOST, C.AVATAR_UDP_PORT)
        # La seña empieza SEGMENT_START_FRAMES frames después de levantar las manos
        self.recorder = MotionRecorder(C.AVATAR_PREROLL_FRAMES + C.SEGMENT_START_FRAMES)
        self.smoother = LiveSmoother()
        self.last_clip = None        # ruta del último clip guardado
        self.coherence = coherence
        self.trainer = trainer
        self.clock = clock
        self.background = background   # False en pruebas: entrenar y armar oración sin hilos
        self.segmenter = SignSegmenter(C.SEQUENCE_LENGTH, C.SEGMENT_START_FRAMES, C.SEGMENT_END_FRAMES,
                                       C.SEGMENT_MIN_FRAMES, C.SEGMENT_MAX_FRAMES,
                                       C.SEGMENT_CONTEXT_FRAMES, C.RESTING_HAND_MARGIN)

        self.mode = "DETECTION"
        self.label = ""
        self.person = "anonimo"
        self.armed = False
        self.prediction = ""
        self.confidence = 0.0
        self.history = []            # lo que se ve en pantalla
        self.pending_words = []      # todo lo que irá a la oración
        self.last_hands_time = self.clock()
        self.sentence = ""
        self.sentence_loading = False
        self.stt_text = ""
        self.prompt = None
        self.status = ""
        self.status_until = 0.0
        self.flash = None
        self.flash_until = 0.0
        self.panel = None            # (título, líneas, hasta cuándo o None = fijo)
        self.training = False
        self.reload_pending = False
        self.body_visible = True
        self.last_saved = None       # última muestra guardada (para pruebas y estadísticas)
        self.timings = {"detect": [], "logic": [], "render": []}

    # ----------------------------------------------------------- utilidades
    def notify(self, text, seconds=3.0):
        print(f"[INFO] {text}")
        self.status = text
        self.status_until = self.clock() + seconds

    def _flash(self, color, seconds=0.5):
        self.flash = color
        self.flash_until = self.clock() + seconds

    def _show_panel(self, title, lines, seconds=None):
        until = None if seconds is None else self.clock() + seconds
        self.panel = (title, lines, until)

    def _run(self, target):
        if self.background:
            threading.Thread(target=target, daemon=True).start()
        else:
            target()

    def _open_prompt(self, prompt):
        # Mientras se escribe no se graba (las manos van al teclado)
        self.armed = False
        self.segmenter.reset()
        self.recorder.cancel()
        self.prompt = prompt

    def _set_mode(self, mode):
        self.mode = mode
        self.armed = False
        self.prediction = ""
        self.segmenter.reset()
        self.recorder.cancel()

    # ------------------------------------------------------------- acciones
    def ask_label(self):
        def on_label(word):
            if not word:
                self.prompt = None
                return
            self._open_prompt(TextPrompt("¿Quién graba? (tu nombre)",
                                         lambda person: on_person(word, person), initial=self.person))

        def on_person(word, person):
            self.prompt = None
            if person is None:
                return
            self.label = word.lower()
            if person:
                self.person = person.lower()
            self._set_mode("TRAINING")
            n = self.collector.count(self.label)
            self.notify(f"'{self.label}' por {self.person} ({n} muestras). Espacio para empezar.")

        self._open_prompt(TextPrompt("Palabra a entrenar:", on_label, initial=self.label))

    def ask_avatar_word(self):
        def on_word(word):
            self.prompt = None
            if not word:
                return
            self.label = word.lower()
            self._set_mode("AVATAR")
            exists = self.label in self.clips.words()
            self.notify(f"Avatar: '{self.label}'{' (ya tiene clip: se reemplaza)' if exists else ''}. "
                        f"Espacio para grabar.")

        self._open_prompt(TextPrompt("Palabra para el avatar:", on_word, initial=self.label))

    def ask_delete(self):
        labels, _ = self.collector.stats()

        def on_word(word):
            self.prompt = None
            if not word:
                return
            removed = self.collector.delete_label(word)
            if removed:
                self.notify(f"Borradas {removed} muestras de '{word}'. Reentrena con 'e'.")
            else:
                self.notify(f"No se encontró '{word}'.")

        question = "Seña a BORRAR: " + (", ".join(sorted(labels)) if labels else "(dataset vacío)")
        self._open_prompt(TextPrompt(question[:70], on_word))

    def start_training(self):
        if self.training:
            self.notify("Ya se está entrenando...")
            return
        self.training = True
        self.notify("Entrenando el modelo... la cámara sigue funcionando.", seconds=600)

        def run():
            ok = False
            try:
                ok = self.trainer(self.collector.file_path, self.logic.model_path, evaluate=False)
            except Exception as e:
                print(f"[TRAIN] Error inesperado: {type(e).__name__}: {e}")
            finally:
                self.training = False
                self.reload_pending = ok
                self.notify("Modelo entrenado y cargado." if ok else
                            "No se pudo entrenar: revisa la consola (¿faltan muestras?).", seconds=5)

        self._run(run)

    def start_sentence(self, words):
        self.sentence_loading = True
        self.sentence = ""

        def run():
            try:
                result = self.coherence(words, enabled=C.USE_CLAUDE)
            except Exception as e:
                print(f"[COHERENCE] Error inesperado: {e}")
                result = " ".join(words)
            self.sentence = result
            self.tts.speak(result)
            self.sentence_loading = False

        self._run(run)

    def show_stats(self):
        labels, persons = self.collector.stats()
        total = sum(labels.values())
        lines = [f"{C.display_name(l)}: {n}" for l, n in sorted(labels.items(), key=lambda kv: -kv[1])]
        lines.append("")
        lines.append("Personas: " + (", ".join(f"{p} ({n})" for p, n in sorted(persons.items())) or "ninguna"))
        if self.logic.model is not None:
            lines.append(f"Modelo cargado: {len(self.logic.classes)} señas")
        clips = self.clips.words()
        lines.append(f"Avatar: {len(clips)} clips" + (f" ({', '.join(clips)})" if clips else ""))
        self._show_panel(f"Dataset: {total} muestras, {len(labels)} señas", lines or ["Sin muestras"], seconds=10)
        print("\n".join([f"Dataset: {total} muestras"] + lines))

    # ---------------------------------------------------------- por frame
    def process_frame(self, frame, render=True):
        now = self.clock()
        frame = cv2.flip(frame, 1)

        t0 = time.perf_counter()
        frame, raw = self.detector.process(frame)
        world = getattr(self.detector, "world", None)
        t1 = time.perf_counter()

        if self.mode == "AVATAR" and world is not None:
            self.sender.send_frame(self.smoother(world, now), now)

        if hands_present(raw):
            self.last_hands_time = now
        self.body_visible = pose_valid(raw) or self.segmenter.body_visible

        if self.reload_pending:
            self.reload_pending = False
            self.logic.load_model()

        action_status = ""
        if self.prompt is None:
            action_status = self._avatar(raw, world, now) if self.mode == "AVATAR" else self._segment(raw)

        stt_result = self.stt.get_result()
        if stt_result:
            self.stt_text = stt_result
        if self.stt.last_error:
            self.notify(self.stt.last_error, seconds=5)
            self.stt.last_error = ""
        if self.tts.last_error:
            self.notify(self.tts.last_error + " (¿hay internet o voz del sistema?)", seconds=5)
            self.tts.last_error = ""

        if self.status and now > self.status_until:
            self.status = ""
        if self.flash is not None and now > self.flash_until:
            self.flash = None
        if self.panel and self.panel[2] is not None and now > self.panel[2]:
            self.panel = None
        t2 = time.perf_counter()

        if render:
            view = View(
                mode=self.mode,
                word=C.display_name(self.prediction) if self.mode == "DETECTION" else self.label,
                confidence=self.confidence,
                action_status=action_status,
                capture_progress=self.segmenter.captured / C.SEGMENT_MAX_FRAMES,
                capturing=self.segmenter.active,
                armed=self.armed,
                flash=self.flash,
                stt_text=self.stt_text,
                stt_recording=self.stt.is_recording,
                history=self.history,
                sentence=self.sentence,
                sentence_loading=self.sentence_loading,
                prompt_question=self.prompt.question if self.prompt else None,
                prompt_text=self.prompt.text if self.prompt else "",
                status=self.status,
                panel_title=self.panel[0] if self.panel else "",
                panel_lines=self.panel[1] if self.panel else None,
                tts_enabled=self.tts.enabled,
                tts_speaking=self.tts.speaking,
                body_visible=self.body_visible,
            )
            frame = DisplayUI.render(frame, view)
        t3 = time.perf_counter()
        self.timings["detect"].append(t1 - t0)
        self.timings["logic"].append(t2 - t1)
        self.timings["render"].append(t3 - t2)
        return frame

    def _avatar(self, raw, world, now):
        """Modo avatar: la seña se corta igual que al grabar muestras (manos
        arriba -> abajo), pero se guarda el movimiento 3D con su ritmo real."""
        was_active = self.segmenter.active
        sequence = self.segmenter.update(raw) if self.armed else None
        if world is not None:
            self.recorder.push(world, now)
        if self.armed and not was_active and self.segmenter.active:
            self.recorder.begin()
            beep_start()
        if was_active and not self.segmenter.active:
            frames = self.recorder.finish()
            if sequence is not None and len(frames) > 1:
                clip = make_clip(frames, self.label, self.person)
                self.last_clip = self.clips.save(clip)
                self.sender.send_clip(self.label, self.last_clip)
                beep_stop()
                self._flash(GREEN)
                self.notify(f"Movimiento guardado: '{self.label}' ({clip['duration']:.1f} s)")
            else:
                beep_error()
                self._flash(RED)
                self.notify("Seña muy corta o sin cuerpo detectado, no se guardó.")

        if self.segmenter.active:
            return f"GRABANDO movimiento de '{self.label}'... baja las manos al terminar"
        target = f"en vivo a {C.AVATAR_UDP_HOST}:{C.AVATAR_UDP_PORT}"
        if self.armed:
            return f"Avatar '{self.label}' ({target}): levanta las manos y haz la seña"
        return f"Avatar '{self.label}' ({target}): Espacio para grabar"

    def _segment(self, raw):
        """Segmentación: el mismo camino al grabar y al detectar."""
        was_active = self.segmenter.active
        sequence = None
        if self.mode == "DETECTION" or self.armed:
            sequence = self.segmenter.update(raw)
        finished = was_active and not self.segmenter.active

        if self.mode == "TRAINING":
            if not was_active and self.segmenter.active:
                beep_start()
            if finished:
                if sequence is not None:
                    self.collector.save_sequence(self.label, sequence, person=self.person)
                    self.last_saved = (self.label, self.person)
                    beep_stop()
                    self._flash(GREEN)
                    self.notify(f"Muestra guardada: '{self.label}' ({self.collector.count(self.label)} en total)")
                else:
                    beep_error()
                    self._flash(RED)
                    self.notify("Seña muy corta, no se guardó.")
            n = self.collector.count(self.label)
            if self.segmenter.active:
                return f"GRABANDO '{self.label}'... baja las manos al terminar"
            if self.armed:
                return f"'{self.label}' ({n} muestras): levanta las manos y haz la seña"
            return f"'{self.label}' ({n} muestras): Espacio para empezar a grabar"

        if finished and sequence is not None:
            pred, conf = self.logic.predict(sequence)
            self.confidence = conf
            if pred:
                self.prediction = pred
                shown = C.display_name(pred)
                self.tts.speak(shown)
                self.pending_words.append(shown)
                self.history = (self.history + [shown])[-C.SUBTITLE_HISTORY:]
            elif self.logic.model is not None:
                self.prediction = ""
                self.notify(f"Seña no reconocida ({conf:.0%})", seconds=1.5)

        # Oración tras un silencio sin manos
        if (self.pending_words and not self.sentence_loading
                and self.clock() - self.last_hands_time > C.SILENCE_SECONDS):
            words, self.pending_words = self.pending_words, []
            self.history = []
            self.start_sentence(words)

        if self.logic.model is None:
            return "Sin modelo: graba señas con 't' y entrena con 'e' (h = ayuda)"
        return ""

    # ------------------------------------------------------------- teclas
    def handle_key(self, key):
        """Procesa una tecla. Devuelve False si hay que salir."""
        if key < 0 or key == 255:
            return True

        # Mientras hay una pregunta en pantalla, todas las teclas van a ella
        if self.prompt is not None:
            prompt = self.prompt
            prompt.handle_key(key)
            if prompt.finished and self.prompt is prompt:
                self.prompt = None
            return True

        if 65 <= key <= 90:      # mayúsculas / Bloq Mayús
            key += 32
        ch = chr(key) if key < 128 else ""

        if key == 27:
            if self.panel is not None:
                self.panel = None
                return True
            return False
        if ch == "q":
            return False
        if ch == "h":
            if self.panel and self.panel[0] == "Teclas":
                self.panel = None
            else:
                self._show_panel("Teclas", HELP_LINES)
        elif ch == "t":
            self.ask_label()
        elif ch == "a":
            self.ask_avatar_word()
        elif ch == " " and self.mode in ("TRAINING", "AVATAR"):
            self.armed = not self.armed
            self.segmenter.reset()
            self.recorder.cancel()
            self.notify("Grabación activada" if self.armed else "Grabación en pausa")
        elif ch == "z" and self.mode == "TRAINING":
            removed = self.collector.remove_last()
            self._flash(RED if removed else GRAY_FLASH)
            self.notify(f"Se deshizo la última muestra ('{removed}')" if removed else "No hay muestras.")
        elif ch == "z" and self.mode == "AVATAR":
            result = self.clips.undo(self.label)
            self._flash(RED if result else GRAY_FLASH)
            self.notify({"restaurado": f"Se deshizo la toma: '{self.label}' vuelve a la anterior",
                         "borrado": f"Se borró el clip de '{self.label}'",
                         None: f"'{self.label}' no tiene clip."}[result])
        elif ch == "d":
            self._set_mode("DETECTION")
            self.logic.load_model()
            self.notify("Modo detección")
        elif ch == "r":
            self.logic.load_model()
            self.prediction = ""
            self.notify("Modelo recargado" if self.logic.model is not None else "No hay modelo para cargar")
        elif ch == "e":
            self.start_training()
        elif ch == "i":
            self.show_stats()
        elif ch == "x":
            self.ask_delete()
        elif ch == "v":
            self.notify(f"Voz {'activada' if self.tts.toggle() else 'desactivada'}")
        elif ch == "s":
            if not self.stt.is_recording:
                self.stt_text = ""
                self.stt.start_recording()
            else:
                self.stt.stop_recording()
        return True

    def close(self):
        self.sender.close()

    def benchmark_summary(self):
        import numpy as np
        parts = {k: 1000 * float(np.median(v[5:] or v)) for k, v in self.timings.items() if v}
        total = sum(parts.values())
        lines = [f"{k}: {ms:.1f} ms" for k, ms in parts.items()]
        lines.append(f"total: {total:.1f} ms/frame (unos {1000 / total:.0f} fps sin contar la cámara)" if total else "")
        return lines


GRAY_FLASH = (120, 120, 120)
