import cv2

from PIL import Image, ImageDraw, ImageFont
import numpy as np

class DisplayUI:
    _font_word = None
    _font_small = None

    @classmethod
    def _get_fonts(cls):
        if cls._font_word is None:
            # Fuentes del sistema Windows para look HD
            paths = ["C:\\Windows\\Fonts\\segoeui.ttf", "C:\\Windows\\Fonts\\arial.ttf"]
            for path in paths:
                try:
                    cls._font_word = ImageFont.truetype(path, 60)
                    cls._font_small = ImageFont.truetype(path, 18)
                    break
                except: continue
            if cls._font_word is None:
                cls._font_word = ImageFont.load_default()
                cls._font_small = ImageFont.load_default()

    @staticmethod
    def draw_info(frame, mode, current_word, action_status, buffer_size=0, max_buffer=30, emotion="NEUTRAL", confidence=0.0, is_recording=False, stt_text="", stt_recording=False):
        h, w, _ = frame.shape
        cls = DisplayUI
        cls._get_fonts()

        # 1. ESQUINAS TIPO "VISOR" (HUD)
        c_len = 50
        th = 2
        col = (180, 180, 180)
        # Top-Left
        cv2.line(frame, (30,30), (30+c_len,30), col, th)
        cv2.line(frame, (30,30), (30,30+c_len), col, th)
        # Top-Right
        cv2.line(frame, (w-30,30), (w-30-c_len,30), col, th)
        cv2.line(frame, (w-30,30), (w-30,30+c_len), col, th)
        # Bottom-Left
        cv2.line(frame, (30,h-30), (30+c_len,h-30), col, th)
        cv2.line(frame, (30,h-30), (30,h-30-c_len), col, th)
        # Bottom-Right
        cv2.line(frame, (w-30,h-30), (w-30-c_len,h-30), col, th)
        cv2.line(frame, (w-30,h-30), (w-30,h-30-c_len), col, th)

        # Flash de grabación — borde rojo pulsante
        if is_recording:
            cv2.rectangle(frame, (15, 15), (w-15, h-15), (0, 0, 220), 3)
            cv2.circle(frame, (55, 55), 10, (0, 0, 220), -1)

        # 1.1 GUIA DE POSICIONAMIENTO (Silueta)
        # Círculo para la cabeza
        cv2.circle(frame, (w//2, h//3), 60, (255, 255, 255), 1, cv2.LINE_AA)
        # Hombros
        cv2.ellipse(frame, (w//2, h//2 + 40), (120, 50), 0, 180, 360, (255, 255, 255), 1, cv2.LINE_AA)
        # Texto guía
        cv2.putText(frame, "ALINEA TU CUERPO AQUI", (w//2 - 80, h//2 + 100), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1, cv2.LINE_AA)

        # 2. PROCESAMIENTO PIL PARA TEXTO HD
        img_pil = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
        draw = ImageDraw.Draw(img_pil)

        # --- Modo actual ---
        mode_text = f"● {mode}"
        mode_col = (50, 255, 50) if mode == "DETECTION" else (255, 50, 50)
        draw.text((w//2 - 50, 20), mode_text, font=cls._font_small, fill=mode_col)

        # --- EMOCIÓN (Arriba Derecha) ---
        emo_text = f"Ánimo: {emotion}"
        ew, eh = draw.textbbox((0, 0), emo_text, font=cls._font_small)[2:]
        draw.rectangle([w - ew - 55, 40, w - 45, 45 + eh + 10], fill=(0, 0, 0, 100))
        draw.text((w - ew - 50, 45), emo_text, font=cls._font_small, fill=(255, 255, 255))

        # --- Subtítulos HD inferiores ---
        if current_word and current_word != "":
            word = current_word.upper()
            # Bounding box del texto
            tw, th_text = draw.textbbox((0, 0), word, font=cls._font_word)[2:]
            tx, ty = (w - tw) // 2, h - 110
            
            # Placa de fondo estilizada
            draw.rectangle([tx - 25, ty - 10, tx + tw + 25, ty + th_text + 15], fill=(0, 0, 0, 160))
            # Texto principal en HD
            draw.text((tx, ty), word, font=cls._font_word, fill=(255, 255, 255))

        # --- Barra de confianza (DETECTION) ---
        if mode == "DETECTION" and current_word and current_word != "":
            bar_x, bar_y, bar_w, bar_h = 45, h - 145, 200, 10
            pct = int(confidence * 100)
            filled = int(confidence * bar_w)
            bar_color = (80, 220, 80) if confidence >= 0.8 else (255, 180, 0) if confidence >= 0.6 else (255, 80, 80)
            draw.rectangle([bar_x, bar_y, bar_x + bar_w, bar_y + bar_h], outline=(100, 100, 100))
            if filled > 0:
                draw.rectangle([bar_x, bar_y, bar_x + filled, bar_y + bar_h], fill=bar_color)
            draw.text((bar_x + bar_w + 10, bar_y - 3), f"{pct}%", font=cls._font_small, fill=bar_color)
            draw.text((bar_x, bar_y - 22), "Confianza", font=cls._font_small, fill=(180, 180, 180))

        # --- Barra progreso (solo si grabamos) ---
        if mode == "TRAINING":
            draw.text((45, 45), action_status, font=cls._font_small, fill=(255, 255, 0))
            bar_y = 75
            draw.rectangle([45, bar_y, 245, bar_y + 8], outline=(100, 100, 100))
            prog_w = int((buffer_size / max_buffer) * 200)
            draw.rectangle([45, bar_y, 45 + prog_w, bar_y + 8], fill=(0, 200, 255))

        # --- Zona STT (superior izquierda) ---
        if stt_recording:
            rec_dot = (220, 50, 50)
            draw.ellipse([45, 75, 57, 87], fill=rec_dot)
            draw.text((63, 72), "Escuchando...", font=cls._font_small, fill=rec_dot)
        elif stt_text:
            draw.text((45, 72), "Interlocutor:", font=cls._font_small, fill=(150, 150, 150))
            tw, th_t = draw.textbbox((0, 0), stt_text, font=cls._font_small)[2:]
            draw.rectangle([43, 90, 55 + tw, 112], fill=(0, 0, 0, 140))
            draw.text((45, 92), stt_text, font=cls._font_small, fill=(100, 220, 255))

        # Volver a formato OpenCV
        return cv2.cvtColor(np.array(img_pil), cv2.RGB2BGR) if hasattr(cv2, 'RGB2BGR') else cv2.cvtColor(np.array(img_pil), cv2.COLOR_RGB2BGR)
