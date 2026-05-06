import os
import anthropic
from dotenv import load_dotenv

# Cargar variables desde .env
load_dotenv()

# Inicializar cliente de Anthropic usando la variable de entorno
client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

def make_coherent(words: list) -> str:
    """
    Toma una lista de palabras detectadas y usa Claude (LLM) 
    para generar una oración coherente en español.
    """
    if not words:
        return ""
        
    try:
        words_str = ", ".join(words)
        # Usamos claude-3-5-haiku-20241022 por ser rápido y eficiente para esta tarea
        message = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=100,
            messages=[
                {
                    "role": "user",
                    "content": (
                        f"Eres un traductor de Lengua de Señas Mexicana (LSM) al español. "
                        f"Convierte estas palabras detectadas por señas en una oración natural "
                        f"y coherente en español. Responde SOLO con la oración, sin explicaciones: "
                        f"{words_str}"
                    )
                }
            ]
        )
        return message.content[0].text.strip()
    except Exception as e:
        print(f"[COHERENCE] Error tipo: {type(e).__name__}")
        print(f"[COHERENCE] Error detalle: {e}")
        # Si falla la IA, devolvemos las palabras unidas por espacio como fallback
        return " ".join(words)
