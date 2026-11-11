"""TTSEngine: respaldo sin internet, errores, cola y activación."""
import threading
import time
import unittest
from unittest import mock

from modules.tts import TTSEngine


def wait_for(cond, timeout=3.0):
    end = time.time() + timeout
    while time.time() < end:
        if cond():
            return True
        time.sleep(0.005)
    return cond()


class TTSEngineTest(unittest.TestCase):
    def setUp(self):
        self.tts = TTSEngine()
        self.addCleanup(self.tts.shutdown)
        self.online = mock.Mock()
        self.offline = mock.Mock()
        self.tts._speak_online = self.online
        self.tts._speak_offline = self.offline

    def idle(self):
        return wait_for(lambda: not self.tts.speaking and self.tts._queue.empty())

    def test_en_linea_correcto_no_usa_voz_local(self):
        """RF-06: si la voz en línea funciona no se usa la local."""
        self.tts.speak("hola")
        self.assertTrue(wait_for(lambda: self.online.called))
        self.assertTrue(self.idle())
        self.online.assert_called_once_with("hola")
        self.offline.assert_not_called()
        self.assertEqual(self.tts.last_error, "")

    def test_falla_en_linea_usa_local(self):
        """RF-06: si falla la voz en línea se cae a la voz local."""
        self.online.side_effect = OSError("sin internet")
        self.tts.speak("hola")
        self.assertTrue(wait_for(lambda: self.offline.called))
        self.assertTrue(self.idle())
        self.offline.assert_called_once_with("hola")
        self.assertEqual(self.tts.last_error, "")

    def test_ambas_fallan_registra_error(self):
        """RF-06: si ambas fallan se fija last_error y speaking vuelve a False."""
        self.online.side_effect = OSError("x")
        self.offline.side_effect = RuntimeError("y")
        self.tts.speak("hola")
        self.assertTrue(wait_for(lambda: self.tts.last_error != ""))
        self.assertTrue(self.idle())
        self.assertFalse(self.tts.speaking)

    def test_sin_uso_en_linea_se_salta(self):
        """RF-06: con use_online=False no se intenta la voz en línea."""
        self.tts.use_online = False
        self.tts.speak("hola")
        self.assertTrue(wait_for(lambda: self.offline.called))
        self.assertTrue(self.idle())
        self.online.assert_not_called()

    def test_desactivado_no_habla(self):
        """RF-06: con la voz desactivada speak no hace nada."""
        self.tts.enabled = False
        self.tts.speak("hola")
        self.assertTrue(self.tts._queue.empty())
        time.sleep(0.05)
        self.online.assert_not_called()
        self.offline.assert_not_called()

    def test_texto_vacio_se_ignora(self):
        """RF-06: texto vacío no se encola."""
        self.tts.speak("")
        self.assertTrue(self.tts._queue.empty())

    def test_toggle(self):
        """RF-06: toggle alterna enabled y devuelve el nuevo valor."""
        self.assertFalse(self.tts.toggle())
        self.assertFalse(self.tts.enabled)
        self.assertTrue(self.tts.toggle())

    def test_cola_se_reduce_a_lo_mas_reciente(self):
        """RF-06: lo que sigue en cola se descarta y queda lo último."""
        gate = threading.Event()
        spoken = []

        def slow(text):
            spoken.append(text)
            gate.wait(3)

        self.tts._speak_online = slow
        self.tts.speak("uno")
        self.assertTrue(wait_for(lambda: spoken == ["uno"]))
        self.tts.speak("dos")
        self.tts.speak("tres")
        self.tts.speak("cuatro")
        gate.set()
        self.assertTrue(wait_for(lambda: spoken == ["uno", "cuatro"]))
        self.assertTrue(self.idle())


if __name__ == "__main__":
    unittest.main()
