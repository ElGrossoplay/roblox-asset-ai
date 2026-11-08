"""Agente: un LLM (gratis via Ollama/Pollinations, o Claude) entiende el pedido y arma un plan
de herramientas. Sin LLM, se usa un enrutador por palabras clave."""
from . import motor

HERRAMIENTAS_DOC = """Herramientas disponibles (usa exactamente estos nombres):
- iconos: iconos PNG de juego. opciones: {"estilo_icono": "cartoon|plano|neon|pixel|realista|anime|fantasia|terror"}
- gui: interfaz completa de Roblox (HUD, tienda, inventario, botones). opciones: {"estilo_gui": "cartoon|scifi|fantasia|minimal|terror|pixel"}
- miniatura: miniatura 1920x1080 + icono de juego. opciones: {"titulo": "...", "subtitulo": "..."}
- modelo3d: modelos 3D texturizados .glb (objetos, edificios, mascotas, vehiculos, personajes). opciones: {}
- sonido: efectos de sonido. opciones: {"tipo": "sfx"}
- musica: musica en loop. opciones: {"genero": "lofi|chiptune|synthwave|edm|trap|orquestal|terror|acustico|reggaeton|tropical|rock"}
- codigo: script Luau para Roblox. opciones: {}
- mundo: estetica del mapa (iluminacion, cielo, texturas, ambiente). opciones: {}
"""

SISTEMA = """Eres el agente de un estudio de assets para juegos de Roblox. Lee el pedido del usuario y
devuelve un plan JSON: {"respuesta": "una frase en espanol explicando que vas a crear",
"pasos": [{"herramienta": "...", "prompt": "pedido concreto en espanol para esa herramienta", "opciones": {}}]}.
Si el usuario pide un juego completo o una idea general (p.ej. "un tycoon de pizza"), crea entre 5 y 8 pasos:
mundo, gui, iconos (de los objetos del juego), modelo3d (2-4 props clave), sonido (efectos clave), musica, miniatura y codigo
(el sistema principal del juego). Si pide algo concreto, usa solo la herramienta necesaria.
Los prompts de cada paso deben ser especificos y coherentes con el mismo tema y estilo visual.
""" + HERRAMIENTAS_DOC


def planificar(pedido: str, log=print) -> dict | None:
    if not motor.disponible():
        return None
    try:
        plan = motor.texto_json(SISTEMA, pedido, log)
    except Exception as e:  # noqa: BLE001
        log(f"  Agente sin LLM ({str(e)[:80]}); uso el enrutador basico.")
        return None
    if isinstance(plan, list):
        plan = {"respuesta": "", "pasos": plan}
    validas = {"iconos", "gui", "miniatura", "modelo3d", "sonido", "musica", "codigo", "mundo"}
    pasos = [p for p in plan.get("pasos", []) if isinstance(p, dict) and p.get("herramienta") in validas and p.get("prompt")]
    if not pasos:
        return None
    return {"respuesta": str(plan.get("respuesta", ""))[:400], "pasos": pasos[:10]}
