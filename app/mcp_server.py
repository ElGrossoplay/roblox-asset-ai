"""Servidor MCP (stdio) para que Claude Desktop, Claude Code u otros agentes usen el estudio.

Configuracion (Claude Desktop -> Settings -> Developer -> Edit Config), ver MCP_CONFIG_EJEMPLO.json:
  "roblox-asset-ai": {"command": "E:\\\\IA  Roblox\\\\runtime\\\\python\\\\python.exe", "args": ["-m", "app.mcp_server"]}
"""
import json
import sys

from .paths import force_portable_env, OUTPUT_DIR

force_portable_env()

from .forge import studio, studio_ia  # noqa: E402

PROTOCOLO = "2025-06-18"


def _schema(extra=None):
    props = {"prompt": {"type": "string", "description": "Descripcion en lenguaje natural (espanol o ingles)"}}
    props.update(extra or {})
    return {"type": "object", "properties": props, "required": ["prompt"]}


HERRAMIENTAS = {
    "generar_juego": ("Agente completo: mundo (luces, cielo, texturas, sonidos, musica, 3D) + GUI + miniatura.", studio_ia.chat_ia, {}),
    "generar_iconos": ("Iconos PNG de juego (moneda, gema, corazon, espada...). Estilos: cartoon, plano, neon, pixel.", studio_ia.iconos_ia,
                       {"estilo_icono": {"type": "string", "enum": ["cartoon", "plano", "neon", "pixel"]}}),
    "generar_gui": ("GUI kit REAL para Roblox (ScreenGui con HUD, barras, tienda, inventario) + PNG + script para Command Bar.",
                    studio_ia.gui_ia, {"estilo_gui": {"type": "string", "enum": ["cartoon", "scifi", "fantasia", "minimal", "terror", "pixel"]}}),
    "generar_miniatura": ("Miniatura 1920x1080 e icono de juego 512x512 con titulo grande.", studio_ia.miniatura_ia,
                          {"titulo": {"type": "string"}, "subtitulo": {"type": "string"}}),
    "generar_sonido": ("Efectos de sonido o musica en loop (WAV).", studio_ia.sonido_ia, {"tipo": {"type": "string", "enum": ["sfx", "musica"]}}),
    "generar_codigo": ("Script Luau para Roblox (monedas, guardado, tienda, rondas, obby, puertas, ranking...).", studio_ia.codigo_ia, {}),
    "generar_modelo3d": ("Props 3D low-poly .glb (arbol, roca, barril, cristal, palmera, personaje...).", studio_ia.modelo3d_ia, {}),
    "generar_musica": ("Musica en loop generada por IA (ACE-Step/MusicGen) o compositor procedural.", studio_ia.musica_ia,
                       {"genero": {"type": "string"}}),
    "generar_mundo": ("Pack de estetica: iluminacion, atmosfera, skybox, texturas, SFX, musica y props.", studio.mundo_tool, {}),
}


def _resumen(carpeta):
    archivos = sorted(str(p.relative_to(carpeta)) for p in carpeta.rglob("*") if p.is_file())
    texto = f"Carpeta: {carpeta}\nArchivos:\n" + "\n".join(f"- {a}" for a in archivos)
    codigo = [carpeta / a for a in archivos if a.endswith(".lua")]
    if codigo and len(codigo[0].read_text(encoding="utf-8")) < 12000:
        texto += f"\n\n--- {codigo[0].name} ---\n" + codigo[0].read_text(encoding="utf-8")
    return texto


def manejar(msg):
    metodo, mid = msg.get("method"), msg.get("id")
    if metodo == "initialize":
        return {"protocolVersion": msg.get("params", {}).get("protocolVersion", PROTOCOLO),
                "capabilities": {"tools": {}}, "serverInfo": {"name": "roblox-asset-ai", "version": "0.2.0"}}
    if metodo == "tools/list":
        return {"tools": [{"name": n, "description": d, "inputSchema": _schema(x)} for n, (d, _, x) in HERRAMIENTAS.items()]
                + [{"name": "listar_assets", "description": "Lista los ultimos assets generados.", "inputSchema": {"type": "object", "properties": {}}}]}
    if metodo == "tools/call":
        p = msg["params"]
        nombre, args = p["name"], dict(p.get("arguments") or {})
        try:
            if nombre == "listar_assets":
                carpetas = sorted((c for c in OUTPUT_DIR.iterdir() if c.is_dir() and not c.name.startswith("_")),
                                  key=lambda c: c.stat().st_mtime, reverse=True)[:30]
                return {"content": [{"type": "text", "text": "\n".join(str(c) for c in carpetas) or "Sin assets"}]}
            _, fn, _ = HERRAMIENTAS[nombre]
            prompt = args.pop("prompt")
            carpeta = fn(prompt, args, lambda m: print(m, file=sys.stderr))
            return {"content": [{"type": "text", "text": _resumen(carpeta)}]}
        except Exception as e:  # noqa: BLE001
            return {"content": [{"type": "text", "text": f"Error: {e}"}], "isError": True}
    if mid is not None and metodo == "ping":
        return {}
    if mid is not None:
        raise LookupError(metodo)
    return None


def main():
    for flujo in (sys.stdin, sys.stdout):
        try:
            flujo.reconfigure(encoding="utf-8")
        except Exception:  # noqa: BLE001
            pass
    for linea in sys.stdin:
        linea = linea.strip()
        if not linea:
            continue
        try:
            msg = json.loads(linea)
        except json.JSONDecodeError:
            continue
        try:
            res = manejar(msg)
            if msg.get("id") is None:
                continue
            out = {"jsonrpc": "2.0", "id": msg["id"], "result": res}
        except LookupError as e:
            out = {"jsonrpc": "2.0", "id": msg.get("id"), "error": {"code": -32601, "message": f"Metodo no soportado: {e}"}}
        sys.stdout.write(json.dumps(out, ensure_ascii=False) + "\n")
        sys.stdout.flush()


if __name__ == "__main__":
    main()
