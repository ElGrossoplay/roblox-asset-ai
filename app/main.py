"""Servidor local (solo biblioteca estandar): interfaz web + API para el plugin de Studio y el MCP.

Ejecutar:  python -m app.main      (INICIAR.bat lo hace por ti)
"""
import io
import json
import mimetypes
import threading
import time
import urllib.parse
import uuid
import webbrowser
import zipfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from .paths import force_portable_env, OUTPUT_DIR, WEB_DIR, LOGS_DIR, ROOT

force_portable_env()

from . import config, pipeline  # noqa: E402
from .forge import studio, studio_ia, scripts_lib, iconos, gui_kit  # noqa: E402
from .ia import motor as motor_ia  # noqa: E402
from .forge.util import paleta_desde_base64, fuentes_disponibles  # noqa: E402

TRABAJOS: dict[str, dict] = {}
CONV_DIR = ROOT / "output" / "_conversaciones"
CONV_DIR.mkdir(parents=True, exist_ok=True)
_lock = threading.Lock()


# ------------------------------------------------------------- conversaciones
def _conv_ruta(cid: str) -> Path:
    return CONV_DIR / f"{''.join(ch for ch in cid if ch.isalnum())}.json"


def conv_cargar(cid: str) -> dict | None:
    r = _conv_ruta(cid)
    return json.loads(r.read_text(encoding="utf-8")) if r.exists() else None


def conv_guardar(c: dict) -> None:
    c["actualizado"] = time.strftime("%Y-%m-%d %H:%M:%S")
    with _lock:
        _conv_ruta(c["id"]).write_text(json.dumps(c, ensure_ascii=False, indent=1), encoding="utf-8")


def conv_lista() -> list:
    out = []
    for r in CONV_DIR.glob("*.json"):
        try:
            c = json.loads(r.read_text(encoding="utf-8"))
            out.append({"id": c["id"], "titulo": c["titulo"], "actualizado": c.get("actualizado", "")})
        except Exception:  # noqa: BLE001
            continue
    return sorted(out, key=lambda c: c["actualizado"], reverse=True)


# ------------------------------------------------------------- trabajos
def nuevo_trabajo(fn, prompt, opciones, backend=None, al_terminar=None):
    jid = uuid.uuid4().hex[:8]
    t = {"id": jid, "estado": "corriendo", "log": [], "resultado": None}
    TRABAJOS[jid] = t

    def log(msg):
        t["log"].append(str(msg))
        with open(LOGS_DIR / "app.log", "a", encoding="utf-8") as f:
            f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} [{jid}] {msg}\n")

    def correr():
        config.usar_backend(backend)
        try:
            res = fn(prompt, opciones or {}, log)
            t["resultado"] = res.name if isinstance(res, Path) else res
            t["estado"] = "listo"
        except Exception as e:  # noqa: BLE001
            log("ERROR: " + pipeline.error_texto(e))
            t["estado"] = "error"
        if al_terminar:
            al_terminar(t)
    threading.Thread(target=correr, daemon=True).start()
    return t


def info_carpeta(carpeta: Path) -> dict:
    """Normaliza cualquier carpeta de output (packs de mundo y herramientas) para la interfaz."""
    try:
        m = json.loads((carpeta / "manifest.json").read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return {"carpeta": carpeta.name, "tipo": "?", "tema": carpeta.name}
    if "tipo" not in m:  # pack de mundo
        imgs = m.get("texturas", []) + m.get("modelos_preview", []) + m.get("skybox", [])
        return {"carpeta": carpeta.name, "tipo": "mundo", "tema": m.get("tema"), "creado": m.get("creado"),
                "preview": "skybox/SkyboxFt.png" if m.get("skybox") else (imgs[0] if imgs else None),
                "imagenes": imgs, "audios": [s["archivo"] for s in m.get("sfx", [])] + ([m["musica"]] if m.get("musica") else []),
                "modelos": m.get("modelos", []), "scripts": ["AplicarEstetica.lua"], "subidos": len(m.get("asset_ids", {})),
                "backends": m.get("backends", {}), "musica_info": m.get("musica_info")}
    out = {"carpeta": carpeta.name, **{k: m.get(k) for k in ("tipo", "tema", "creado", "preview", "estilo", "fuente", "relacionados", "destino", "tipo_script", "partes", "musica_info", "modificadores")},
           "imagenes": m.get("iconos", []) + m.get("imagenes", []), "audios": m.get("audios", []),
           "modelos": m.get("modelos", []), "scripts": m.get("scripts", []), "subidos": len(m.get("asset_ids", {}))}
    out["descargas"] = _descargas(carpeta)
    out["info3d"] = m.get("info3d")
    if m["tipo"] == "codigo" and out["scripts"]:
        out["codigo"] = (carpeta / out["scripts"][0]).read_text(encoding="utf-8")
    if m["tipo"] == "juego":
        out["partes"] = [info_carpeta(OUTPUT_DIR / p) for p in m.get("partes", []) if (OUTPUT_DIR / p).is_dir()]
    return out


def _descargas(carpeta: Path) -> list:
    return sorted(str(f.relative_to(carpeta)).replace("\\", "/") for f in carpeta.rglob("*") if f.suffix.lower() in (".fbx", ".obj"))


def carpeta_segura(nombre: str) -> Path:
    c = (OUTPUT_DIR / nombre).resolve()
    if c.parent != OUTPUT_DIR.resolve() or not c.is_dir() or c.name.startswith("_"):
        raise FileNotFoundError(nombre)
    return c


def zip_carpeta(c: Path) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for f in c.rglob("*"):
            if f.is_file():
                z.write(f, f.relative_to(c))
        m = json.loads((c / "manifest.json").read_text(encoding="utf-8"))
        for parte in m.get("partes", []):  # juego completo: incluye sus partes
            p = OUTPUT_DIR / parte
            for f in p.rglob("*"):
                if f.is_file():
                    z.write(f, Path(parte) / f.relative_to(p))
    return buf.getvalue()


HERRAMIENTAS = {**studio_ia.HERRAMIENTAS, "chat": studio_ia.chat_ia}


CLAVES = ["HF_TOKEN", "POLLINATIONS_API_KEY", "ANTHROPIC_API_KEY", "REPLICATE_API_TOKEN", "ROBLOX_API_KEY"]


def leer_ajustes() -> dict:
    import os
    config.get(reload=True)
    out = {}
    for k in CLAVES:
        v = os.environ.get(k, "")
        out[k] = (v[:4] + "…" + v[-3:]) if len(v) > 10 else ("•••" if v else "")
    out["creator_id"] = str(config.get()["roblox"].get("creator_id", ""))
    return out


def guardar_ajustes(datos: dict) -> dict:
    import os
    import re as _re
    ruta = ROOT / "config" / "secrets.env"
    actuales = {}
    if ruta.exists():
        for linea in ruta.read_text(encoding="utf-8").splitlines():
            if "=" in linea and not linea.strip().startswith("#"):
                k, v = linea.split("=", 1)
                actuales[k.strip()] = v.strip()
    for k in CLAVES:
        v = str(datos.get(k, "")).strip()
        if v and "…" not in v and "•" not in v:
            actuales[k] = v
            os.environ[k] = v
        elif datos.get(k) == "":
            pass
    ruta.write_text("# Claves guardadas desde Ajustes (no compartas este archivo)\n" +
                    "\n".join(f"{k}={v}" for k, v in actuales.items()) + "\n", encoding="utf-8")
    if "creator_id" in datos:
        toml = ROOT / "config" / "config.toml"
        texto = toml.read_text(encoding="utf-8")
        texto = _re.sub(r'creator_id = ".*?"', f'creator_id = "{_re.sub(r"[^0-9]", "", str(datos["creator_id"]))}"', texto)
        toml.write_text(texto, encoding="utf-8")
    return leer_ajustes()


def enviar(datos: dict) -> dict:
    """Mensaje del chat: crea/actualiza la conversacion y lanza la herramienta."""
    prompt = str(datos.get("prompt", "")).strip()
    herramienta = datos.get("herramienta", "chat")
    if not prompt:
        raise ValueError("Escribe algo")
    if herramienta not in HERRAMIENTAS:
        raise ValueError("Herramienta desconocida")
    conv = conv_cargar(datos.get("conversacion") or "") or {
        "id": uuid.uuid4().hex[:10], "titulo": prompt[:48], "creado": time.strftime("%Y-%m-%d %H:%M:%S"), "mensajes": []}
    conv["mensajes"].append({"rol": "usuario", "texto": prompt, "herramienta": herramienta})
    conv_guardar(conv)

    def al_terminar(t):
        c = conv_cargar(conv["id"]) or conv
        c["mensajes"].append({"rol": "ia", "estado": t["estado"], "log": t["log"][-6:], "carpeta": t["resultado"]})
        conv_guardar(c)
    t = nuevo_trabajo(HERRAMIENTAS[herramienta], prompt, datos.get("opciones"), datos.get("backend"), al_terminar)
    return {"conversacion": conv["id"], "trabajo": t["id"]}


# ------------------------------------------------------------- HTTP
class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _enviar(self, cuerpo: bytes, tipo: str, code=200, extra=None):
        self.send_response(code)
        self.send_header("Content-Type", tipo)
        self.send_header("Content-Length", str(len(cuerpo)))
        self.send_header("Cache-Control", "no-store")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(cuerpo)

    def _json(self, data, code=200):
        self._enviar(json.dumps(data, ensure_ascii=False).encode(), "application/json; charset=utf-8", code)

    def _archivo(self, ruta: Path, tipo=None):
        if not ruta.is_file():
            return self._json({"error": "no encontrado"}, 404)
        self._enviar(ruta.read_bytes(), tipo or mimetypes.guess_type(ruta.name)[0] or "application/octet-stream")

    def _body(self):
        n = int(self.headers.get("Content-Length") or 0)
        return json.loads(self.rfile.read(n) or b"{}")

    def do_GET(self):
        url = urllib.parse.urlparse(self.path)
        ruta = urllib.parse.unquote(url.path)
        q = urllib.parse.parse_qs(url.query)
        partes = [p for p in ruta.split("/") if p]
        try:
            if ruta in ("/", "/index.html"):
                return self._archivo(WEB_DIR / "index.html", "text/html; charset=utf-8")
            if ruta == "/docs":
                return self._archivo(ROOT / "LEEME.md", "text/plain; charset=utf-8")
            if ruta == "/api/estado":
                cfg = config.get(reload=True)
                from . import blender as _bl
                _inf = _bl.info()
                return self._json({"backends": {m: cfg[m]["backend"] for m in ("director", "imagen", "musica", "sfx", "malla3d")},
                                   "blender": _inf.get("texto"), "version": __import__("app").__version__,
                                   "fuentes": list(fuentes_disponibles()), "iconos": list(iconos.CATALOGO),
                                   "estilos_gui": list(gui_kit.ESTILOS),
                                   "plantillas": {k: v["titulo"] for k, v in scripts_lib.PLANTILLAS.items()}})
            if ruta == "/api/packs":
                tipo = (q.get("tipo") or [None])[0]
                carpetas = sorted((c for c in OUTPUT_DIR.iterdir() if c.is_dir() and not c.name.startswith("_")),
                                  key=lambda c: c.stat().st_mtime, reverse=True)
                info = [info_carpeta(c) for c in carpetas]
                return self._json([i for i in info if not tipo or i.get("tipo") == tipo])
            if ruta == "/api/ajustes":
                return self._json(leer_ajustes())
            if ruta == "/api/conversaciones":
                return self._json(conv_lista())
            if len(partes) == 3 and partes[:2] == ["api", "conversacion"]:
                c = conv_cargar(partes[2])
                if not c:
                    return self._json({"error": "no existe"}, 404)
                for msj in c["mensajes"]:
                    if msj.get("carpeta") and (OUTPUT_DIR / msj["carpeta"]).is_dir():
                        msj["info"] = info_carpeta(OUTPUT_DIR / msj["carpeta"])
                return self._json(c)
            if len(partes) == 3 and partes[:2] == ["api", "trabajo"]:
                t = TRABAJOS.get(partes[2])
                if not t:
                    return self._json({"error": "trabajo no existe"}, 404)
                out = dict(t)
                if t["estado"] == "listo" and isinstance(t["resultado"], str) and (OUTPUT_DIR / t["resultado"]).is_dir():
                    out["info"] = info_carpeta(OUTPUT_DIR / t["resultado"])
                return self._json(out)
            if len(partes) == 3 and partes[:2] == ["api", "zip"]:
                c = carpeta_segura(partes[2])
                return self._enviar(zip_carpeta(c), "application/zip", extra={"Content-Disposition": f'attachment; filename="{c.name}.zip"'})
            if len(partes) == 4 and partes[:2] == ["api", "pack"]:
                c = carpeta_segura(partes[2])
                if partes[3] == "estetica.lua":
                    return self._archivo(c / "AplicarEstetica.lua", "text/plain; charset=utf-8")
                if partes[3] == "gui.json":
                    m = json.loads((c / "manifest.json").read_text(encoding="utf-8"))
                    spec = json.loads((c / "gui.json").read_text(encoding="utf-8"))
                    spec["ids"] = {Path(k).stem: v for k, v in m.get("asset_ids", {}).items() if k.startswith("iconos/")}
                    spec["ids_arte"] = {Path(k).stem: v for k, v in m.get("asset_ids", {}).items() if k.startswith("arte/")}
                    return self._json(spec)
                if partes[3] == "script":
                    m = json.loads((c / "manifest.json").read_text(encoding="utf-8"))
                    s = (m.get("scripts") or ["AplicarEstetica.lua"])[0]
                    return self._archivo(c / s, "text/plain; charset=utf-8")
            if partes and partes[0] == "output" and len(partes) >= 3:
                c = carpeta_segura(partes[1])
                f = (c / "/".join(partes[2:])).resolve()
                if c in f.parents:
                    return self._archivo(f)
            return self._json({"error": "ruta desconocida"}, 404)
        except FileNotFoundError:
            return self._json({"error": "no encontrado"}, 404)

    def do_POST(self):
        ruta = urllib.parse.urlparse(self.path).path
        try:
            datos = self._body()
            if ruta == "/api/enviar":
                return self._json(enviar(datos))
            if ruta == "/api/generar":  # compatibilidad con el plugin v1
                return self._json(enviar({"prompt": datos.get("tema"), "herramienta": datos.get("herramienta", "mundo"),
                                          "opciones": datos.get("opciones")}))
            if ruta == "/api/ajustes":
                return self._json(guardar_ajustes(datos))
            if ruta == "/api/diagnostico":
                from . import diagnostico
                t = nuevo_trabajo(lambda _p, _o, log: diagnostico.ejecutar(log), "", {})
                return self._json({"trabajo": t["id"]})
            if ruta == "/api/ia/probar":
                t = nuevo_trabajo(lambda _p, _o, log: motor_ia.probar_conexiones(log), "", {})
                return self._json({"trabajo": t["id"]})
            if ruta == "/api/paleta":
                return self._json({"paleta": paleta_desde_base64(datos["imagen"])})
            if ruta == "/api/subir":
                c = carpeta_segura(datos["carpeta"])
                t = nuevo_trabajo(lambda _p, _o, log: studio.subir(c, log), "", {})
                return self._json({"trabajo": t["id"]})
            if ruta == "/api/borrar":
                c = carpeta_segura(datos["carpeta"])
                import shutil
                shutil.rmtree(c)
                return self._json({"ok": True})
            if ruta == "/api/conversacion/borrar":
                r = _conv_ruta(datos["id"])
                if r.exists():
                    r.unlink()
                return self._json({"ok": True})
            return self._json({"error": "ruta desconocida"}, 404)
        except (FileNotFoundError, KeyError):
            return self._json({"error": "no encontrado"}, 404)
        except ValueError as e:
            return self._json({"error": str(e)}, 400)


def main():
    cfg = config.get()["server"]
    host, port = cfg.get("host", "127.0.0.1"), int(cfg.get("port", 8765))
    srv = None
    for intento in range(port, port + 15):
        try:
            srv = ThreadingHTTPServer((host, intento), Handler)
            port = intento
            break
        except OSError:
            continue
    if srv is None:
        raise SystemExit(f"No hay puertos libres entre {cfg.get('port', 8765)} y {port + 14}. Cierra otra copia de la app.")
    if port != int(cfg.get("port", 8765)):
        print(f"  Aviso: el puerto {cfg.get('port', 8765)} estaba ocupado; uso {port}. "
              f"(El plugin de Studio lo encuentra solo.)")
    url = f"http://{host}:{port}"
    print(f"\n  Roblox Asset AI corriendo en {url}\n  (cierra esta ventana para apagarlo)\n")
    if cfg.get("abrir_navegador", True):
        threading.Timer(1.0, lambda: webbrowser.open(url)).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
