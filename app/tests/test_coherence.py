"""make_coherent: oración con Claude y respaldo sin clave/API (nunca llama a la API real)."""
import os
import unittest
from types import SimpleNamespace as NS
from unittest import mock

from modules import coherence


class FakeClient:
    def __init__(self, response=None, error=None):
        self.calls = 0
        self._response, self._error = response, error
        self.messages = NS(create=self._create)

    def _create(self, **kwargs):
        self.calls += 1
        if self._error:
            raise self._error
        return self._response


def response(text, stop="end_turn"):
    blocks = [NS(type="thinking", text="ignorar"), NS(type="text", text=text)]
    return NS(stop_reason=stop, content=blocks)


class CoherenceTest(unittest.TestCase):
    def setUp(self):
        for p in (mock.patch.object(coherence, "_client", None),
                  mock.patch.object(coherence, "_disabled", False),
                  mock.patch("dotenv.load_dotenv", lambda *a, **k: False)):
            p.start()
            self.addCleanup(p.stop)

    def test_lista_vacia(self):
        """RF-07: sin palabras devuelve cadena vacía."""
        self.assertEqual(coherence.make_coherent([]), "")

    def test_desactivado_une_palabras(self):
        """RF-07: con enabled=False se unen las palabras."""
        self.assertEqual(coherence.make_coherent(["yo", "querer", "agua"], enabled=False),
                         "yo querer agua")

    def test_sin_clave_une_palabras(self):
        """RF-07: sin ANTHROPIC_API_KEY se unen las palabras."""
        with mock.patch.dict(os.environ, {"ANTHROPIC_API_KEY": ""}):
            self.assertEqual(coherence.make_coherent(["hola", "amigo"]), "hola amigo")

    def test_cliente_devuelve_texto(self):
        """RF-07: se devuelve el texto de los bloques de tipo text."""
        client = FakeClient(response("  Quiero agua.  "))
        with mock.patch.object(coherence, "_client", client):
            self.assertEqual(coherence.make_coherent(["yo", "agua"]), "Quiero agua.")
        self.assertEqual(client.calls, 1)

    def test_rechazo_usa_respaldo(self):
        """RF-07: stop_reason 'refusal' devuelve las palabras."""
        client = FakeClient(response("no", stop="refusal"))
        with mock.patch.object(coherence, "_client", client):
            self.assertEqual(coherence.make_coherent(["a", "b"]), "a b")

    def test_error_del_cliente_usa_respaldo(self):
        """RF-07: una excepción del cliente devuelve las palabras."""
        client = FakeClient(error=TimeoutError("lento"))
        with mock.patch.object(coherence, "_client", client):
            self.assertEqual(coherence.make_coherent(["a", "b"]), "a b")

    def test_respuesta_vacia_usa_respaldo(self):
        """RF-07: texto vacío devuelve las palabras."""
        client = FakeClient(response("   "))
        with mock.patch.object(coherence, "_client", client):
            self.assertEqual(coherence.make_coherent(["a", "b"]), "a b")


if __name__ == "__main__":
    unittest.main()
