class TextPrompt:
    """Pregunta de texto dentro de la ventana de OpenCV (sin usar la consola).

    Mientras está activa recibe todas las teclas: Enter confirma,
    Esc cancela y Backspace borra. Acepta letras con acento y ñ
    (OpenCV en Windows las entrega como códigos Latin-1).
    """

    ENTER = (13, 10)
    ESC = 27
    BACKSPACE = (8, 127)
    MAX_LENGTH = 40

    def __init__(self, question, on_done, initial=""):
        self.question = question
        self.text = initial
        self.on_done = on_done
        self.finished = False

    def handle_key(self, key):
        if key in self.ENTER:
            self.finished = True
            self.on_done(self.text.strip())
        elif key == self.ESC:
            self.finished = True
            self.on_done(None)
        elif key in self.BACKSPACE:
            self.text = self.text[:-1]
        elif (32 <= key < 127 or 160 <= key <= 255) and len(self.text) < self.MAX_LENGTH:
            self.text += bytes([key]).decode("latin-1")
