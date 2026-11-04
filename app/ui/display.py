"""Dibuja la interfaz sobre el video.

Los textos se dibujan con PIL (acentos y ñ) en una capa transparente que se
guarda en caché mientras su contenido no cambia; cada frame solo se copia
sobre el video. Lo que cambia en cada frame (barra de progreso, destellos,
guía) se dibuja directo con OpenCV.
"""
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

_FONT_PATHS = [
    "C:\\Windows\\Fonts\\segoeui.ttf",
    "C:\\Windows\\Fonts\\arial.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/System/Library/Fonts/Supplemental/Arial.ttf",
]

WHITE = (255, 255, 255)
GRAY = (170, 170, 170)
WARNING = (255, 165, 60)     # avisos de encuadre (RGB)
PLATE = (0, 0, 0, 255)
MARGIN = 40
MIN_HEIGHT = 720
MODE_LABELS = {   # texto y color (RGB) de cada modo en la barra superior
    "DETECTION": ("● DETECCIÓN", (60, 230, 90)),
    "TRAINING": ("● ENTRENAMIENTO", (255, 90, 90)),
    "AVATAR": ("● AVATAR", (190, 130, 255)),
}


@dataclass
class View:
    """Todo lo que la interfaz necesita saber para dibujar un frame."""
    mode: str = "DETECTION"
    word: str = ""
    confidence: float = 0.0
    action_status: str = ""
    capture_progress: float = 0.0
    capturing: bool = False
    armed: bool = False
    flash: Optional[Tuple[int, int, int]] = None   # color BGR del destello
    stt_text: str = ""
    stt_recording: bool = False
    history: List[str] = field(default_factory=list)
    sentence: str = ""
    sentence_loading: bool = False
    prompt_question: Optional[str] = None
    prompt_text: str = ""
    status: str = ""
    panel_title: str = ""
    panel_lines: Optional[List[str]] = None
    tts_enabled: bool = True
    tts_speaking: bool = False
    body_visible: bool = True
    framing_hint: str = ""
    show_guide: bool = True


class DisplayUI:
    _fonts = {}
    _cache_key = None
    _cache = None   # (índices opacos, colores opacos, índices parciales, rgb, alpha)

    @classmethod
    def font(cls, size):
        if size not in cls._fonts:
            for path in _FONT_PATHS:
                try:
                    cls._fonts[size] = ImageFont.truetype(path, size)
                    break
                except OSError:
                    continue
            else:
                cls._fonts[size] = ImageFont.load_default()
        return cls._fonts[size]

    @staticmethod
    def wrap(draw, text, font, max_width):
        """Parte el texto en líneas que caben en max_width."""
        lines = []
        for paragraph in text.split("\n"):
            words, line = paragraph.split(" "), ""
            for word in words:
                candidate = f"{line} {word}".strip()
                if line and draw.textlength(candidate, font=font) > max_width:
                    lines.append(line)
                    line = word
                else:
                    line = candidate
            lines.append(line)
        return lines

    @staticmethod
    def line_height(font):
        return int(getattr(font, "size", 14) * 1.35)

    @classmethod
    def block_height(cls, lines, font, pad=8):
        return len(lines) * cls.line_height(font) + 2 * pad if lines else 0

    @classmethod
    def _text_block(cls, draw, lines, font, x, y, color, plate=True, pad=8, columns=False):
        """Dibuja líneas con placa oscura detrás; devuelve la altura usada.
        Con `columns`, cada línea "tecla\tdescripción" se alinea en dos columnas."""
        if not lines:
            return 0
        lh = cls.line_height(font)
        if columns:
            cells = [line.split("\t", 1) if "\t" in line else [line] for line in lines]
            key_w = max((draw.textlength(c[0], font=font) for c in cells if len(c) == 2), default=0) + 24
            width = max(key_w + draw.textlength(c[1], font=font) if len(c) == 2 else draw.textlength(c[0], font=font)
                        for c in cells)
        else:
            width = max(draw.textlength(line, font=font) for line in lines)
        total = lh * len(lines)
        if plate:
            draw.rectangle([x - pad, y - pad, x + width + pad, y + total + pad], fill=PLATE)
        for i, line in enumerate(lines):
            cy = y + i * lh
            if columns and "\t" in line:
                key, desc = line.split("\t", 1)
                draw.text((x, cy), key, font=font, fill=(255, 220, 120))
                draw.text((x + key_w, cy), desc, font=font, fill=color)
            else:
                draw.text((x, cy), line, font=font, fill=color)
        return total + 2 * pad

    @classmethod
    def _render_layer(cls, w, h, v: View):
        layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        draw = ImageDraw.Draw(layer)
        small, medium, big = cls.font(20), cls.font(28), cls.font(60)
        max_w = w - 2 * MARGIN

        # --- Barra superior: modo e indicadores ---
        mode, mode_col = MODE_LABELS.get(v.mode, MODE_LABELS["DETECTION"])
        indicators = [f"Voz: {'sí' if v.tts_enabled else 'no'}"]
        if v.tts_speaking:
            indicators.append("Hablando...")
        warning = "No veo tus hombros" if not v.body_visible else v.framing_hint
        if warning:
            indicators.append(warning)
        top = "   ".join([mode] + indicators)
        y = 22
        y += cls._text_block(draw, [top], small, MARGIN, y, WHITE) + 14
        draw.text((MARGIN, 22), mode, font=small, fill=mode_col)
        if warning:   # el aviso de encuadre resalta (va al final de la barra)
            x = MARGIN + draw.textlength(top[:-len(warning)], font=small)
            draw.text((x, 22), warning, font=small, fill=WARNING)

        # --- Estado de la acción (entrenamiento / avisos) ---
        if v.action_status:
            y += cls._text_block(draw, cls.wrap(draw, v.action_status, small, max_w), small, MARGIN, y, (255, 230, 80)) + 14

        # --- Texto del interlocutor (para la persona Sorda: grande y arriba) ---
        if v.stt_recording:
            y += cls._text_block(draw, ["Escuchando al interlocutor... (s para terminar)"], medium, MARGIN, y, (255, 120, 120)) + 14
        elif v.stt_text:
            lines = cls.wrap(draw, v.stt_text, medium, max_w)[:3]
            draw.text((MARGIN, y), "Interlocutor dice:", font=small, fill=GRAY)
            y += cls.line_height(small) + 8
            y += cls._text_block(draw, lines, medium, MARGIN, y, (130, 220, 255)) + 14

        # --- Mensaje temporal (resultado de una acción) ---
        if v.status:
            lines = cls.wrap(draw, v.status, small, max_w)[:2]
            y += cls._text_block(draw, lines, small, MARGIN, y, (130, 255, 170)) + 14
        top_limit = y

        # --- Pila inferior: palabra, confianza/historial, oración ---
        # Se dibuja de abajo hacia arriba y se omite lo que ya no cabe.
        bottom = h - MARGIN
        if v.word:
            word = v.word.upper()
            font = big
            while draw.textlength(word, font=font) > max_w - 50 and getattr(font, "size", 20) > 28:
                font = cls.font(font.size - 8)
            tw = draw.textlength(word, font=font)
            th = cls.line_height(font)
            tx = max(MARGIN, int((w - tw) // 2))
            bottom -= th
            draw.rectangle([tx - 25, bottom - 6, tx + tw + 25, bottom + th], fill=PLATE)
            draw.text((tx, bottom), word, font=font, fill=WHITE)
            bottom -= 24

        info = []
        if v.mode == "DETECTION" and v.word:
            info.append(f"Confianza {int(v.confidence * 100)}%")
        if v.mode == "DETECTION" and v.history:
            info.append("  →  ".join(v.history))
        if info:
            lines = cls.wrap(draw, "     ".join(info), small, max_w)
            hgt = cls.block_height(lines, small)
            if bottom - hgt > top_limit:
                bottom -= hgt
                cls._text_block(draw, lines, small, MARGIN, bottom + 8, GRAY)
                bottom -= 12

        if v.sentence_loading or v.sentence:
            if v.sentence_loading:
                lines, font, color = ["Armando la oración..."], small, (230, 220, 80)
            else:
                lines, font, color = cls.wrap(draw, v.sentence, medium, max_w), medium, WHITE
            hgt = cls.block_height(lines, font) + cls.line_height(small)
            while lines and bottom - hgt <= top_limit:
                lines = lines[1:]                        # si no cabe, mostrar el final
                hgt = cls.block_height(lines, font) + cls.line_height(small)
            if lines:
                bottom -= hgt
                draw.text((MARGIN, bottom), "Traducción:", font=small, fill=GRAY)
                cls._text_block(draw, lines, font, MARGIN, bottom + cls.line_height(small) + 8, color)

        # --- Panel central (ayuda / estadísticas) ---
        if v.panel_lines:
            box_w = min(max_w, 680)
            lines = []
            for line in v.panel_lines:
                lines.extend([line] if "\t" in line else cls.wrap(draw, line, small, box_w))
            if v.panel_title:
                lines = [v.panel_title, ""] + lines
            max_lines = max(1, (h - 2 * MARGIN - 40) // cls.line_height(small))
            lines = lines[:max_lines]
            hgt = cls.block_height(lines, small, pad=20)
            cls._text_block(draw, lines, small, (w - box_w) // 2, max(MARGIN, (h - hgt) // 2), WHITE,
                            pad=20, columns=True)

        # --- Pregunta de texto (reemplaza a input() de la consola) ---
        if v.prompt_question is not None:
            box_w = min(max_w, 620)
            x0, y0 = (w - box_w) // 2, h // 2 - 70
            draw.rectangle([x0, y0, x0 + box_w, y0 + 140], fill=(20, 20, 20, 255), outline=(0, 200, 255), width=2)
            draw.text((x0 + 20, y0 + 15), v.prompt_question, font=small, fill=(210, 210, 210))
            text = v.prompt_text + "_"
            while draw.textlength(text, font=medium) > box_w - 40 and len(text) > 1:
                text = text[1:]
            draw.text((x0 + 20, y0 + 50), text, font=medium, fill=WHITE)
            draw.text((x0 + 20, y0 + 102), "Enter: aceptar    Esc: cancelar", font=small, fill=(130, 130, 130))

        rgba = np.asarray(layer)
        alpha = rgba[..., 3]
        opaque = np.nonzero(alpha == 255)
        partial = np.nonzero((alpha > 0) & (alpha < 255))
        bgr = rgba[..., 2::-1]
        return (opaque, bgr[opaque], partial, bgr[partial].astype(np.float32),
                (alpha[partial].astype(np.float32) / 255.0)[:, None])

    @classmethod
    def render(cls, frame, v: View):
        """Dibuja la interfaz. Los frames de menos de MIN_HEIGHT de alto se
        agrandan primero para que el texto sea legible (RNF-05)."""
        h, w = frame.shape[:2]
        if h < MIN_HEIGHT:
            scale = MIN_HEIGHT / h
            frame = cv2.resize(frame, (int(round(w * scale)), MIN_HEIGHT), interpolation=cv2.INTER_LINEAR)
            h, w = frame.shape[:2]

        if v.show_guide and v.mode == "TRAINING":
            cv2.circle(frame, (w // 2, h // 3), 60, WHITE, 1, cv2.LINE_AA)
            cv2.ellipse(frame, (w // 2, h // 2 + 40), (120, 50), 0, 180, 360, WHITE, 1, cv2.LINE_AA)

        key = (w, h, v.mode, v.word, round(v.confidence, 2), v.action_status, v.stt_text, v.stt_recording,
               tuple(v.history), v.sentence, v.sentence_loading, v.prompt_question, v.prompt_text, v.status,
               v.panel_title, tuple(v.panel_lines or ()), v.tts_enabled, v.tts_speaking, v.body_visible, v.framing_hint)
        if key != cls._cache_key:
            cls._cache = cls._render_layer(w, h, v)
            cls._cache_key = key
        opaque, opaque_bgr, partial, partial_bgr, partial_a = cls._cache
        frame[opaque] = opaque_bgr
        if len(partial[0]):
            base = frame[partial].astype(np.float32)
            frame[partial] = (base * (1 - partial_a) + partial_bgr * partial_a).astype(np.uint8)

        # Elementos que cambian en cada frame
        recording_mode = v.mode in ("TRAINING", "AVATAR")
        if recording_mode and v.capturing:
            cv2.rectangle(frame, (8, 8), (w - 8, h - 8), (0, 0, 230), 6)
            x0, y0 = w - MARGIN - 220, 18
            cv2.rectangle(frame, (x0, y0), (x0 + 220, y0 + 14), (90, 90, 90), 1)
            cv2.rectangle(frame, (x0, y0), (x0 + int(220 * min(v.capture_progress, 1.0)), y0 + 14), (0, 200, 255), -1)
        elif recording_mode and v.armed:
            cv2.rectangle(frame, (8, 8), (w - 8, h - 8), (0, 200, 255), 2)
        if v.flash is not None:
            cv2.rectangle(frame, (0, 0), (w - 1, h - 1), v.flash, 18)
        return frame
