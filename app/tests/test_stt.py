"""STTController: motores de voz a texto simulados (sin micrófono ni red)."""
import unittest
from unittest import mock

from modules.stt import STTController

NO_MODEL = "ruta/que/no/existe/vosk"


def make(use_online=True):
    return STTController(NO_MODEL, use_online=use_online)


class TranscribeTest(unittest.TestCase):
    def test_google_devuelve_texto(self):
        """RF-08: Google devuelve texto y no hay error."""
        stt = make()
        with mock.patch.object(stt, "_transcribe_google", return_value="hola mundo"):
            self.assertEqual(stt.transcribe(b"\x00"), ("hola mundo", ""))

    def test_google_falla_sin_vosk(self):
        """RF-08: si Google falla y no hay Vosk, se informa el error en español."""
        stt = make()
        with mock.patch.object(stt, "_transcribe_google", side_effect=OSError("red")):
            text, err = stt.transcribe(b"\x00")
        self.assertEqual(text, "")
        self.assertIn("No se entendió la voz", err)
        self.assertIn("Google", err)

    def test_google_vacio(self):
        """RF-08: texto vacío cuenta como 'no entendió'."""
        stt = make()
        with mock.patch.object(stt, "_transcribe_google", return_value=""):
            text, err = stt.transcribe(b"\x00")
        self.assertEqual(text, "")
        self.assertIn("no entendió", err)

    def test_google_no_instalado(self):
        """RF-08: ImportError se reporta como 'no instalado'."""
        stt = make()
        with mock.patch.object(stt, "_transcribe_google", side_effect=ImportError):
            _, err = stt.transcribe(b"\x00")
        self.assertIn("no instalado", err)

    def test_respaldo_vosk(self):
        """RF-08: si Google falla se usa Vosk."""
        stt = make()
        stt._vosk_model = object()
        with mock.patch.object(stt, "_transcribe_google", side_effect=OSError), \
                mock.patch.object(stt, "_transcribe_vosk", return_value="adiós"):
            self.assertEqual(stt.transcribe(b"\x00"), ("adiós", ""))

    def test_sin_motor(self):
        """RF-08: sin Google ni Vosk se avisa que falta un motor."""
        stt = make(use_online=False)
        text, err = stt.transcribe(b"\x00")
        self.assertEqual(text, "")
        self.assertIn("sin motor", err)

    def test_modelo_inexistente_no_carga_vosk(self):
        """RF-08: una ruta inexistente deja Vosk sin cargar."""
        self.assertIsNone(make()._vosk_model)


class RecordTest(unittest.TestCase):
    def run_with(self, **record_kwargs):
        stt = make()
        stt.is_recording = True
        with mock.patch.object(stt, "_record", **record_kwargs):
            stt._record_and_transcribe()
        return stt

    def test_import_error(self):
        """RF-08: sin pyaudio queda un error en español y se deja de grabar."""
        stt = self.run_with(side_effect=ImportError)
        self.assertFalse(stt.is_recording)
        self.assertIn("Falta pyaudio", stt.last_error)

    def test_os_error(self):
        """RF-08: un fallo del micrófono queda como error en español."""
        stt = self.run_with(side_effect=OSError("sin dispositivo"))
        self.assertFalse(stt.is_recording)
        self.assertIn("micrófono", stt.last_error)

    def test_audio_vacio(self):
        """RF-08: audio vacío termina sin resultado y sin grabar."""
        stt = self.run_with(return_value=b"")
        self.assertFalse(stt.is_recording)
        self.assertIsNone(stt.get_result())

    def test_texto_llega_a_la_cola(self):
        """RF-08: el texto transcrito se entrega con get_result."""
        stt = make()
        stt.is_recording = True
        with mock.patch.object(stt, "_record", return_value=b"\x00\x01"), \
                mock.patch.object(stt, "_transcribe_google", return_value="hola"):
            stt._record_and_transcribe()
        self.assertFalse(stt.is_recording)
        self.assertEqual(stt.get_result(), "hola")
        self.assertIsNone(stt.get_result())

    def test_error_inesperado_en_transcribe_deja_de_grabar(self):
        """RNF-06: si transcribe falla, no se cae el hilo, se avisa y is_recording vuelve a False."""
        stt = make()
        stt.is_recording = True
        with mock.patch.object(stt, "_record", return_value=b"\x00"), \
                mock.patch.object(stt, "transcribe", side_effect=RuntimeError):
            stt._record_and_transcribe()
        self.assertFalse(stt.is_recording)
        self.assertIn("RuntimeError", stt.last_error)


if __name__ == "__main__":
    unittest.main()
