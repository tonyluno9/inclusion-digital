"""Lógica de la aplicación, separada del bucle de cámara.

`InclusionApp.process_frame(frame)` recibe un frame BGR de la cámara y devuelve
el frame con la interfaz dibujada; `handle_key(key)` procesa una tecla y
devuelve False cuando hay que salir. Así la app completa se puede probar con
frames y teclas simuladas (ver tests/test_app.py).
"""
import json
import os
import threading
import time
from collections import deque

import cv2

import config as C
from modules.beep import beep_error, beep_start, beep_stop
from modules.coherence import make_coherent
from modules.data_collector import DataCollector
from modules.gesture_logic import GestureLogic
from modules.landmarks import elbows_visible, hands_present, keep_hands, missing_hands, pose_valid
from modules.progreso import Progreso, normalizar
from modules.motion import (ClipStore, LiveSender, LiveSmoother, MotionRecorder, make_clip, rest_arm,
                            resting_side, trim_clip)
from modules.segmenter import SignSegmenter
from train_model import train
from ui.display import DisplayUI, View
from ui.text_input import TextPrompt

HELP_LINES = [
    "t\tEntrenar una palabra",
    "a\tAvatar: grabar el movimiento de una palabra",
    "Espacio\t(entrenamiento / avatar) activar / pausar la grabación",
    "z\t(entrenamiento / avatar) deshacer la última toma",
    "m\t(entrenamiento / avatar) seña de dos manos / mano derecha / mano izquierda",
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
                 trainer=train, clock=time.monotonic, background=True, clips=None, sender=None,
                 review_takes=False):
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
        # Con review_takes (la app web), la toma del avatar no se guarda sola: queda
        # pendiente para revisarla y recortarla (save_take / discard_take)
        self.review_takes = review_takes
        self.pending_take = None
        self.take_seq = 0
        # Manos de cada seña ("dos", "derecha", "izquierda"), recordadas por palabra
        self.hands = "dos"
        self.hands_path = os.path.join(os.path.dirname(os.path.abspath(self.collector.file_path)),
                                       "manos_por_sena.json")
        self.hands_by_word = self._load_hands()
        # Modo Aprender: progreso junto al dataset; en práctica no se arman oraciones
        self.progreso = Progreso(os.path.join(os.path.dirname(self.hands_path), "progreso.json"))
        self.practice = False
        self.live_world = None       # frame 3D suavizado (modo avatar), para el avatar de la app web
        self.word_seq = 0            # sube con cada seña reconocida
        self.text_seq = 0            # sube con cada texto nuevo del interlocutor
        self.clip_seq = 0            # sube con cada clip guardado
        self.action_status = ""
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
        self.framing_hint = ""       # aviso de encuadre ("Aléjate: no veo tus codos")
        self._elbows_seen = deque(maxlen=C.FRAMING_WINDOW)   # ¿se vieron los codos? en los frames que cuentan
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
        self.pending_take = None
        self.practice = False
        self._elbows_seen.clear()
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
            self.train_word(word, person)

        self._open_prompt(TextPrompt("Palabra a entrenar:", on_label, initial=self.label))

    def ask_avatar_word(self):
        def on_word(word):
            self.prompt = None
            if word:
                self.avatar_word(word)

        self._open_prompt(TextPrompt("Palabra para el avatar:", on_word, initial=self.label))

    def ask_delete(self):
        labels, _ = self.collector.stats()

        def on_word(word):
            self.prompt = None
            if word:
                self.delete_sign(word)

        question = "Seña a BORRAR: " + (", ".join(sorted(labels)) if labels else "(dataset vacío)")
        self._open_prompt(TextPrompt(question[:70], on_word))

    def _load_hands(self):
        try:
            with open(self.hands_path, encoding="utf-8") as f:
                data = json.load(f)
            return {str(k): v for k, v in data.items() if v in C.HANDS_MODES}
        except (OSError, ValueError, AttributeError):
            return {}

    def _remember_hands(self):
        if not self.label:
            return
        self.hands_by_word[self.label] = self.hands
        try:
            os.makedirs(os.path.dirname(self.hands_path), exist_ok=True)
            tmp = self.hands_path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(self.hands_by_word, f, ensure_ascii=False, indent=1, sort_keys=True)
            os.replace(tmp, self.hands_path)
        except OSError as e:
            print(f"[MANOS] No se pudo guardar {self.hands_path}: {e}")

    def set_hands(self, mode):
        """La seña se hace con las dos manos o con una sola ("derecha" / "izquierda")."""
        if mode not in C.HANDS_MODES:
            raise ValueError(f"modo de manos desconocido: {mode}")
        self.hands = mode
        self.segmenter.reset()
        self.recorder.cancel()
        self._remember_hands()
        self.notify({"dos": "Seña de dos manos",
                     "derecha": "Seña de una mano: la derecha (la izquierda no se graba)",
                     "izquierda": "Seña de una mano: la izquierda (la derecha no se graba)"}[mode])
        return mode

    def cycle_hands(self):
        modes = C.HANDS_MODES
        return self.set_hands(modes[(modes.index(self.hands) + 1) % len(modes)])

    def _word_hands(self):
        """Al elegir una palabra se recupera con qué manos se hace (si ya se eligió antes)."""
        self.hands = self.hands_by_word.get(self.label, self.hands)

    def _hands_label(self):
        return {"dos": "dos manos", "derecha": "mano derecha", "izquierda": "mano izquierda"}[self.hands]

    def train_word(self, word, person=""):
        """Modo entrenamiento para grabar muestras de `word`."""
        self.label = word.strip().lower()
        if person and person.strip():
            self.person = person.strip().lower()
        self._set_mode("TRAINING")
        self._word_hands()
        n = self.collector.count(self.label)
        self.notify(f"'{self.label}' por {self.person} ({n} muestras, {self._hands_label()}). Espacio para empezar.")

    def avatar_word(self, word):
        """Modo avatar para grabar el movimiento de `word`. Sin palabra, el avatar
        solo imita a la persona en vivo (no se puede grabar)."""
        self.label = word.strip().lower()
        self._set_mode("AVATAR")
        if not self.label:
            self.notify("Avatar en vivo. Escribe una palabra para grabar su movimiento.")
            return
        self._word_hands()
        exists = self.label in self.clips.words()
        self.notify(f"Avatar: '{self.label}' ({self._hands_label()}){' (ya tiene clip: se reemplaza)' if exists else ''}. "
                    f"Espacio para grabar.")

    def detection_mode(self, practice=False):
        """Detección; con `practice` (pantalla Aprender) las señas no forman oraciones."""
        self._set_mode("DETECTION")
        self.practice = bool(practice)
        if practice:
            self.pending_words, self.history = [], []
        self.logic.load_model()
        self.notify("Modo práctica" if practice else "Modo detección")

    def toggle_recording(self):
        if self.mode not in ("TRAINING", "AVATAR"):
            return False
        if not self.label:
            self.notify("Primero escribe la palabra que vas a grabar.")
            return False
        if self.pending_take is not None:
            self.notify("Primero guarda o descarta la toma que estás revisando.")
            return False
        self.armed = not self.armed
        self.segmenter.reset()
        self.recorder.cancel()
        self.notify("Grabación activada" if self.armed else "Grabación en pausa")
        return self.armed

    def undo(self):
        """Deshace la última muestra (entrenamiento) o la última toma (avatar)."""
        if self.mode == "TRAINING":
            removed = self.collector.remove_last()
            self._flash(RED if removed else GRAY_FLASH)
            self.notify(f"Se deshizo la última muestra ('{removed}')" if removed else "No hay muestras.")
        elif self.mode == "AVATAR":
            if self.pending_take is not None:
                self.discard_take()
                return
            result = self.clips.undo(self.label)
            self._flash(RED if result else GRAY_FLASH)
            self.notify({"restaurado": f"Se deshizo la toma: '{self.label}' vuelve a la anterior",
                         "borrado": f"Se borró el clip de '{self.label}'",
                         None: f"'{self.label}' no tiene clip."}[result])

    def reload_model(self):
        self.logic.load_model()
        self.prediction = ""
        self.notify("Modelo recargado" if self.logic.model is not None else "No hay modelo para cargar")

    def toggle_voice(self):
        enabled = self.tts.toggle()
        self.notify(f"Voz {'activada' if enabled else 'desactivada'}")
        return enabled

    def toggle_listening(self):
        """Voz del interlocutor a texto: iniciar / terminar."""
        if not self.stt.is_recording:
            self.stt_text = ""
            self.stt.start_recording()
        else:
            self.stt.stop_recording()
        return self.stt.is_recording

    def delete_sign(self, word):
        removed = self.collector.delete_label(word)
        if removed:
            self.notify(f"Borradas {removed} muestras de '{word}'. Reentrena con 'e'.")
        else:
            self.notify(f"No se encontró '{word}'.")
        return removed

    def delete_clip(self, word):
        """Borra el clip del avatar de `word` (y su toma anterior)."""
        removed = 0
        while self.clips.undo(word):
            removed += 1
        self.notify(f"Se borró el movimiento de '{word}'." if removed else f"'{word}' no tiene movimiento.")
        return bool(removed)

    def save_take(self, start=None, end=None):
        """Guarda la toma pendiente del avatar, recortada entre `start` y `end` (s)."""
        if self.pending_take is None:
            raise ValueError("no hay ninguna toma por guardar")
        clip = self.pending_take
        if start is not None or end is not None:
            clip = trim_clip(clip, 0.0 if start is None else start,
                             clip["duration"] if end is None else end)
        self.pending_take = None
        self._store_clip(clip)
        return self.last_clip

    def discard_take(self):
        if self.pending_take is None:
            return False
        self.pending_take = None
        self._flash(GRAY_FLASH)
        self.notify("Toma descartada. Espacio para grabar otra.")
        return True

    def _store_clip(self, clip):
        self.last_clip = self.clips.save(clip)
        self.clip_seq += 1
        self.sender.send_clip(clip["word"], self.last_clip)
        self._flash(GREEN)
        self.notify(f"Movimiento guardado: '{clip['word']}' ({clip['duration']:.1f} s)")

    # -------------------------------------------------------- aprender y diccionario
    @staticmethod
    def _categorias():
        try:
            with open(C.CATEGORIAS_PATH, encoding="utf-8") as f:
                return {c["id"]: c["palabras"] for c in json.load(f)["categorias"]}
        except (OSError, ValueError, KeyError, TypeError):
            return {}

    def _evaluar_insignias(self):
        return self.progreso.evaluar(self._categorias(), self.logic.classes if self.logic.model is not None else [],
                                     len(self.clips.words()), self.logic.model is not None)

    def practice_result(self, word, correct, confidence=0.0):
        """Resultado de un intento en Aprender: estrellas, insignias nuevas y el resumen."""
        stars = self.progreso.registrar_intento(word, correct, confidence)
        nuevas = self._evaluar_insignias()
        self.progreso.guardar()
        return {"estrellas": stars, "nuevas": nuevas, "resumen": self.progreso.resumen()}

    def progress_summary(self):
        nuevas = self._evaluar_insignias()
        if nuevas:
            self.progreso.guardar()
        return {**self.progreso.resumen(), "nuevas": nuevas}

    def vocabulary(self):
        """Todas las palabras que la app conoce (dataset, traductor y avatar), una por palabra."""
        labels, _ = self.collector.stats()
        model = self.logic.classes if self.logic.model is not None else []
        out = {}

        def entry(label):
            key = normalizar(label)
            return key, out.setdefault(key, {"palabra": label, "clave": key, "nombre": C.display_name(label),
                                             "muestras": 0, "traductor": False, "movimiento": None,
                                             "manos": self.hands_by_word.get(label)})

        for label, n in labels.items():
            entry(label)[1]["muestras"] += n
        for label in model:
            entry(label)[1]["traductor"] = True
        for word in self.clips.words():
            entry(word)[1]["movimiento"] = word
        return sorted(out.values(), key=lambda e: e["clave"])

    def interlocutor_text(self, text):
        """Texto del interlocutor escrito a mano (en vez de dictado)."""
        self.stt_text = text.strip()
        self.text_seq += 1

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
            try:
                self.progreso.registrar_oracion()
                self.progreso.guardar()
            except OSError as e:
                print(f"[PROGRESO] No se pudo guardar: {e}")

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

        recording_modes = ("TRAINING", "AVATAR")
        if self.mode in recording_modes and self.hands != "dos":
            # Seña de una mano: la otra no cuenta (ni para cortar la seña ni en el avatar)
            raw = keep_hands(raw, self.hands)
            if world is not None:
                world = rest_arm(world, resting_side(self.hands))

        self.live_world = None
        if self.mode == "AVATAR" and world is not None:
            self.live_world = self.smoother(world, now)
            self.sender.send_frame(self.live_world, now)

        if hands_present(raw):
            self.last_hands_time = now
        self.body_visible = pose_valid(raw) or self.segmenter.body_visible
        self.framing_hint = self._framing(raw)

        if self.reload_pending:
            self.reload_pending = False
            self.logic.load_model()

        action_status = ""
        if self.prompt is None:
            action_status = self._avatar(raw, world, now) if self.mode == "AVATAR" else self._segment(raw)
        self.action_status = action_status

        stt_result = self.stt.get_result()
        if stt_result:
            self.stt_text = stt_result
            self.text_seq += 1
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
                framing_hint=self.framing_hint,
            )
            frame = DisplayUI.render(frame, view)
        t3 = time.perf_counter()
        self.timings["detect"].append(t1 - t0)
        self.timings["logic"].append(t2 - t1)
        self.timings["render"].append(t3 - t2)
        return frame

    def _framing(self, raw):
        """Aviso cuando la persona está tan cerca de la cámara que no se ven sus
        codos. Cuenta en modo avatar siempre, y en los otros modos solo mientras
        hay manos (con las manos abajo, que los codos queden fuera es normal)."""
        if not pose_valid(raw):
            return ""                # sin hombros ya se avisa "No veo tus hombros"
        if self.mode == "AVATAR" or hands_present(raw):
            self._elbows_seen.append(elbows_visible(raw))
        seen = self._elbows_seen
        if len(seen) == seen.maxlen and sum(seen) < C.FRAMING_MIN_SEEN * len(seen):
            return "Aléjate: no veo tus codos"
        return ""

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
                clip = make_clip(frames, self.label, self.person, self.hands)
                beep_stop()
                if self.review_takes:
                    # Se revisa y recorta en la app antes de guardarla; mientras, no se graba otra
                    self.pending_take = clip
                    self.take_seq += 1
                    self.armed = False
                    self.notify("Revisa la toma: recórtala si hace falta y guárdala.")
                else:
                    self._store_clip(clip)
            else:
                beep_error()
                self._flash(RED)
                self.notify("Seña muy corta o sin cuerpo detectado, no se guardó.")

        if self.segmenter.active:
            return f"GRABANDO movimiento de '{self.label}'... baja las manos al terminar"
        if self.pending_take is not None:
            return f"Revisando la toma de '{self.label}'"
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
            missing = missing_hands(sequence, self.hands, C.MIN_HAND_COVERAGE) if finished and sequence is not None else []
            if missing:
                beep_error()
                self._flash(RED)
                if self.hands == "dos" and len(missing) == 1:
                    self.notify(f"No vi tu mano {missing[0]} en casi toda la seña: no se guardó. "
                                f"Si la seña es de una mano, elige «una mano».", seconds=5)
                else:
                    self.notify(f"No vi tu mano {' ni la '.join(missing)} en casi toda la seña: no se guardó. "
                                "Repítela.", seconds=5)
            elif finished:
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
                self.word_seq += 1          # la app web reproduce la seña con el avatar
                shown = C.display_name(pred)
                self.tts.speak(shown)
                if not self.practice:            # en Aprender no se arman oraciones
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
        elif ch == " ":
            self.toggle_recording()
        elif ch == "z":
            self.undo()
        elif ch == "m" and self.mode in ("TRAINING", "AVATAR"):
            self.cycle_hands()
        elif ch == "d":
            self.detection_mode()
        elif ch == "r":
            self.reload_model()
        elif ch == "e":
            self.start_training()
        elif ch == "i":
            self.show_stats()
        elif ch == "x":
            self.ask_delete()
        elif ch == "v":
            self.toggle_voice()
        elif ch == "s":
            self.toggle_listening()
        return True

    def close(self):
        self.sender.close()

    def state(self):
        """Estado para la interfaz web (lo que la ventana de OpenCV dibuja con View)."""
        flash = {GREEN: "ok", RED: "error", GRAY_FLASH: "neutro"}.get(self.flash) if self.flash else None
        return {
            "modo": self.mode,
            "palabra": self.label,
            "persona": self.person,
            "muestras_palabra": self.collector.count(self.label) if self.label else 0,
            "armado": self.armed,
            "grabando": self.segmenter.active,
            "progreso": min(1.0, self.segmenter.captured / C.SEGMENT_MAX_FRAMES),
            "prediccion": C.display_name(self.prediction) if self.prediction else "",
            "confianza": round(float(self.confidence), 3),
            "historial": list(self.history),
            "oracion": self.sentence,
            "oracion_cargando": self.sentence_loading,
            "interlocutor": self.stt_text,
            "escuchando": bool(self.stt.is_recording),
            "aviso": self.status,
            "accion": self.action_status,
            "destello": flash,
            "voz": bool(self.tts.enabled),
            "hablando": bool(self.tts.speaking),
            "cuerpo_visible": self.body_visible,
            "aviso_encuadre": self.framing_hint,
            "entrenando": self.training,
            "modelo_senas": sorted(self.logic.classes) if self.logic.model is not None else [],
            "seq_palabra": self.word_seq,
            "seq_texto": self.text_seq,
            "seq_clip": self.clip_seq,
            "manos": self.hands,
            "practica": self.practice,
            "toma_seq": self.take_seq,
            "toma_pendiente": self.pending_take is not None,
        }

    def benchmark_summary(self):
        import numpy as np
        parts = {k: 1000 * float(np.median(v[5:] or v)) for k, v in self.timings.items() if v}
        total = sum(parts.values())
        lines = [f"{k}: {ms:.1f} ms" for k, ms in parts.items()]
        lines.append(f"total: {total:.1f} ms/frame (unos {1000 / total:.0f} fps sin contar la cámara)" if total else "")
        return lines


GRAY_FLASH = (120, 120, 120)
