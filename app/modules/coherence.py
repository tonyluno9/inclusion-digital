"""Convierte las palabras detectadas en una oración con Claude (opcional).

Si no hay ANTHROPIC_API_KEY o el paquete anthropic no está instalado, devuelve
las palabras unidas por espacios y la app sigue funcionando.
"""
import os

MODEL = "claude-haiku-5-5"

_client = None
_disabled = False


def _get_client():
    global _client, _disabled
    if _client is not None or _disabled:
        return _client
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass
    if not os.getenv("ANTHROPIC_API_KEY"):
        print("[COHERENCE] Sin ANTHROPIC_API_KEY: se mostrarán las palabras tal cual.")
        _disabled = True
        return None
    try:
        import anthropic
        _client = anthropic.Anthropic(timeout=15.0, max_retries=1)
    except Exception as e:
        print(f"[COHERENCE] Claude no disponible: {e}")
        _disabled = True
    return _client


def make_coherent(words: list, enabled: bool = True) -> str:
    """Toma una lista de palabras detectadas y devuelve una oración en español.
    Con `enabled=False` (o sin clave / sin internet) devuelve las palabras unidas."""
    if not words:
        return ""
    fallback = " ".join(words)
    client = _get_client() if enabled else None
    if client is None:
        return fallback

    try:
        message = client.messages.create(
            model=MODEL,
            max_tokens=1024,
            output_config={"effort": "low"},
            messages=[
                {
                    "role": "user",
                    "content": (
                        "Eres un traductor de Lengua de Señas Mexicana (LSM) al español. "
                        "Convierte estas palabras detectadas por señas en una oración natural "
                        "y coherente en español. Responde SOLO con la oración, sin explicaciones: "
                        + ", ".join(words)
                    ),
                }
            ],
        )
        if message.stop_reason == "refusal":
            return fallback
        text = "".join(b.text for b in message.content if b.type == "text").strip()
        return text or fallback
    except Exception as e:
        print(f"[COHERENCE] Error ({type(e).__name__}): {e}")
        return fallback
