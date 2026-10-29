from modules.landmarks import hands_present, prepare_sequence


class SignSegmenter:
    """Corta el flujo de la cámara en señas individuales: una seña empieza
    cuando aparecen las manos y termina cuando se bajan (o al llegar al máximo).

    Se usa igual al grabar el dataset y al detectar, para que el modelo siempre
    reciba las señas preparadas de la misma forma.
    """

    def __init__(self, length, start_frames, end_frames, min_frames, max_frames):
        self.length = length
        self.start_frames = start_frames
        self.end_frames = end_frames
        self.min_frames = min_frames
        self.max_frames = max_frames
        self.reset()

    def reset(self):
        self.frames = []
        self.active = False
        self._absent = 0

    @property
    def captured(self):
        return len(self.frames) if self.active else 0

    def update(self, raw_frame):
        """Agrega un frame. Cuando termina una seña devuelve la secuencia
        preparada (length x valores); si no, None."""
        present = hands_present(raw_frame)

        if not self.active:
            if present:
                self.frames.append(raw_frame)
                if len(self.frames) >= self.start_frames:
                    self.active = True
            else:
                self.frames = []
            return None

        self.frames.append(raw_frame)
        self._absent = 0 if present else self._absent + 1
        if self._absent >= self.end_frames or len(self.frames) >= self.max_frames:
            frames = self.frames
            self.reset()
            return prepare_sequence(frames, self.length, self.min_frames)
        return None
