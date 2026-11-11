from collections import deque

import numpy as np

from modules.landmarks import (HANDS_SIZE, RAW_FRAME_SIZE, body_reference_pose, drop_resting_hands,
                               hands_present, pose_valid, prepare_sequence)


class SignSegmenter:
    """Corta el flujo de la cámara en señas individuales: una seña empieza
    cuando se levantan las manos y termina cuando se bajan (o al llegar al máximo).

    Se usa igual al grabar el dataset y al detectar, para que el modelo siempre
    reciba las señas preparadas de la misma forma.

    También recuerda los últimos frames sin manos levantadas: ahí los brazos no
    tapan los hombros, así que de ellos sale la referencia del cuerpo para la
    seña y para decidir qué manos están "en reposo".
    """

    def __init__(self, length, start_frames, end_frames, min_frames, max_frames,
                 context_frames=15, resting_margin=1.5):
        self.length = length
        self.start_frames = start_frames
        self.end_frames = end_frames
        self.min_frames = min_frames
        self.max_frames = max_frames
        self.resting_margin = resting_margin
        self._idle = deque(maxlen=context_frames)
        self._body = None
        self.reset()

    def reset(self):
        self.frames = []
        self.active = False
        self._absent = 0
        self._wait_release = False   # tras un corte forzado, esperar a que bajen las manos
        self.last_discarded = False  # la última seña terminó pero era muy corta

    @property
    def captured(self):
        return len(self.frames) if self.active else 0

    @property
    def body_visible(self):
        return self._body is not None

    def _reference(self, raw_frame):
        if self._body is not None:
            return self._body
        if pose_valid(raw_frame):
            return np.asarray(raw_frame, dtype=np.float32)[HANDS_SIZE:RAW_FRAME_SIZE]
        return None

    def update(self, raw_frame):
        """Agrega un frame. Cuando termina una seña devuelve la secuencia
        preparada (length x valores); si no, None."""
        frame = drop_resting_hands(raw_frame, self._reference(raw_frame), self.resting_margin)
        present = hands_present(frame)

        if not present and pose_valid(frame):
            self._idle.append(frame)
            self._body = body_reference_pose(list(self._idle))

        if self._wait_release:
            if not present:
                self._wait_release = False
            return None

        if not self.active:
            self.frames = self.frames + [frame] if present else []
            if len(self.frames) >= self.start_frames:
                self.active = True
            return None

        self.frames.append(frame)
        self._absent = 0 if present else self._absent + 1
        forced = len(self.frames) >= self.max_frames and present
        if self._absent >= self.end_frames or forced:
            frames = self.frames
            self.reset()
            self._wait_release = forced
            out = prepare_sequence(frames, self.length, self.min_frames, body=self._body)
            self.last_discarded = out is None
            return out
        return None
