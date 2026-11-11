"""TextPrompt: entrada de texto dentro de la ventana de OpenCV."""
import unittest

from ui.text_input import TextPrompt


def prompt(initial=""):
    done = []
    return TextPrompt("¿Seña?", done.append, initial), done


def type_keys(p, keys):
    for k in keys:
        p.handle_key(k)


class TextPromptTest(unittest.TestCase):
    def test_ascii(self):
        """RF-09: se escribe texto ASCII."""
        p, _ = prompt()
        type_keys(p, map(ord, "Hola 1"))
        self.assertEqual(p.text, "Hola 1")

    def test_enie_y_acento_latin1(self):
        """RF-09: los códigos Latin-1 241 y 225 dan ñ y á."""
        p, _ = prompt()
        type_keys(p, [241, 225])
        self.assertEqual(p.text, "ñá")

    def test_backspace(self):
        """RF-09: Backspace (8 y 127) borra el último carácter, también en vacío."""
        p, _ = prompt("abc")
        type_keys(p, [8, 127, 8, 8])
        self.assertEqual(p.text, "")

    def test_enter_entrega_texto_sin_espacios(self):
        """RF-09: Enter llama on_done con el texto recortado."""
        p, done = prompt()
        type_keys(p, map(ord, "  hola  "))
        p.handle_key(13)
        self.assertEqual(done, ["hola"])
        self.assertTrue(p.finished)

    def test_esc_cancela(self):
        """RF-09: Esc llama on_done(None)."""
        p, done = prompt("x")
        p.handle_key(27)
        self.assertEqual(done, [None])
        self.assertTrue(p.finished)

    def test_longitud_maxima(self):
        """RF-09: no se acepta más de 40 caracteres."""
        p, _ = prompt()
        type_keys(p, [ord("a")] * 60)
        self.assertEqual(len(p.text), 40)

    def test_teclas_no_imprimibles_se_ignoran(self):
        """RF-09: códigos de control o fuera de rango no cambian el texto."""
        p, done = prompt("ab")
        type_keys(p, [0, 1, 9, 31, 128, 159, 256, 2555904, -1])
        self.assertEqual(p.text, "ab")
        self.assertEqual(done, [])
        self.assertFalse(p.finished)


if __name__ == "__main__":
    unittest.main()
