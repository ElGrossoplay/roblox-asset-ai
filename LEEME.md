# Roblox Asset AI

Estudio **portable y gratuito** de assets para Roblox, con el mismo flujo de trabajo que ForgeGUI:

| ForgeGUI | Aquí |
|---|---|
| Home "What are we building?" con **Agents / Tools** | Inicio "¿Qué vamos a crear?" con **Agentes / Herramientas** |
| Pestañas Chat, Icons, Thumbnails, Code, Sound, GUI, More Tools | Chat, Íconos, Miniaturas, Código, Sonido, GUI, Más herramientas (3D, Mundo) |
| Conversations | Conversaciones guardadas en el disco, con los resultados dentro del chat |
| Community Assets | **Mis Assets**: galería con filtros, búsqueda y ZIP |
| Game Studio | **Game Studio**: mundo completo (luces, cielo, texturas, sonidos, música, 3D) |
| GUI Studio & Import | GUI **real** (ScreenGui editable), no solo una imagen + plugin que la importa |
| Reference-guided style | "Copiar estilo de una imagen": extrae la paleta y la aplica |
| Fine-grained controls | "Más opciones": estilo, colores, bordes, contorno, títulos, BPM… |
| ForgeMCP | Servidor **MCP** para Claude Desktop / Claude Code / Codex |
| Créditos | Ilimitado: todo corre en tu PC o con servicios gratis |

## IA generativa real (v3)

Todo se genera con **modelos de IA abiertos y gratuitos**, igual que ForgeGUI genera con sus modelos:

| Asset | Modelo IA (gratis) | Cómo |
|---|---|---|
| Íconos, arte de GUI, miniaturas, GFX, texturas, cielos | **FLUX.1-schnell** (Apache 2.0) vía Hugging Face Spaces / Pollinations / tu GPU | prompt profesional por tipo de asset + quitar fondo + recorte; texturas se vuelven *tileables*; el cielo es un panorama 360° convertido a las 6 caras del Sky |
| Modelos 3D **con textura** y personajes | **Hunyuan3D-2** (o TRELLIS / Stable Fast 3D) | texto → imagen de referencia FLUX → malla 3D texturizada → centrada, escalada en studs y dividida si pasa los 20.000 triángulos de Roblox. También **imagen propia → 3D** |
| Efectos de sonido | **Stable Audio Open** | cualquier descripción ("rugido de dragón lejano") |
| Música | **ACE-Step** (Apache 2.0) / MusicGen | por género, duración y letra opcional |
| Agente, código Luau, traducción de prompts | **Ollama** (local) / Pollinations / HF Inference / Claude | el agente arma un plan con varias herramientas |

Los motores y su orden están en `config\ia.toml`. El programa **descubre solo** los parámetros de cada
Space de Hugging Face; si uno deja de existir, agrega otro a la lista. Si ninguna IA responde, usa el
generador procedural (marcado como *procedural* en los resultados).

**Recomendado:** crea un token gratis en huggingface.co/settings/tokens y pégalo en **Ajustes e IA**
dentro de la app (te da más cuota de GPU). Usa **Probar conexiones** para ver qué motores responden.

## Blender (opcional, recomendado para 3D profesional)

`INSTALAR_BLENDER.bat` descarga **Blender LTS oficial portable** (download.blender.org, verificado con SHA-256)
a `runtime\blender`. Si ya tienes Blender instalado (3.6 o superior), se detecta solo. Con Blender:

- **Modelos IA:** se unen en una sola malla, se limpian (vértices duplicados, geometría suelta, normales) y se
  **reducen conservando la textura** (Decimate *collapse*) hasta el límite de Roblox. Pivote abajo al centro, escala en studs.
- **Modelos procedurales:** biseles en aristas, normales ponderadas, suavizado por ángulo; los orgánicos (árboles,
  rocas, hongos) se suavizan y reciben ruido leve para no verse geométricos.
- **Exporta GLB y FBX** (texturas embebidas) y renderiza una **vista previa con Cycles en CPU** (funciona sin GPU dedicada).
- Si Blender falla en algo, el modelo se procesa con el método interno: nunca se pierde el resultado.
  El detalle queda en `logs\blender_ultimo.log`.

Al importar en Studio (File → Import 3D) usa **Scale Unit: Stud** si el tamaño no coincide.

## Compatibilidad y diagnóstico

- `DIAGNOSTICO.bat` (o **Ajustes e IA → Diagnóstico completo**) revisa Python, paquetes, permisos de escritura,
  espacio libre, puerto, fuentes, Blender (con una prueba real) y los motores de IA. Guarda `logs\diagnostico.txt`.
- Si el puerto 8765 está ocupado, la app usa el siguiente libre y el plugin de Studio lo encuentra solo.
- Los archivos de configuración se pueden editar con el Bloc de notas (se tolera el BOM UTF-8).
- Todo queda dentro de la carpeta del proyecto: Python, paquetes, modelos, caché de Blender, temporales y resultados.
- Requisitos: Windows 10/11 de 64 bits (Windows 10 1803+ para `tar.exe`), ~200 MB sin Blender, ~1,2 GB con Blender,
  internet para la IA gratuita (sin internet funciona el modo procedural).

El **Agente** (pestaña Chat) entiende el pedido: si pides "íconos de espada" usa la herramienta
de íconos; si pides "haz un tycoon de pizza" arma el juego completo (mundo + GUI + miniatura).

## Herramientas

| Herramienta | Qué genera |
|---|---|
| Íconos | 20 íconos de juego (moneda, gema, corazón, espada, cofre, trofeo…) en estilos cartoon, plano, neón y pixel |
| Miniaturas | Miniatura 1920×1080 + ícono de juego 512×512 con título grande, cinta e íconos |
| Código | Biblioteca de sistemas Luau (monedas + DataStore, tienda segura, rondas, checkpoints, lava, puerta, ranking global, sprint…); con Ollama/Claude, scripts a medida |
| Sonido | **55 efectos** diseñados por capas (UI, combate, magia, explosiones, pasos en 7 superficies, ambientes en loop) con variaciones y modificadores en el prompt: *grave/agudo, corto/largo, retro 8bit, con eco*. **Música** en 11 géneros (lofi, chiptune, synthwave, EDM, trap, orquestal, terror, acústico, reggaetón, tropical, rock), estéreo, con loop perfecto y stems opcionales |
| GUI | Kit con HUD, monedas/gemas, barra de vida y XP, menú lateral, tienda, inventario, aviso y botón Jugar, en 6 estilos |
| Texto a 3D | **39 modelos** low-poly `.glb` (+ `.obj` opcional) con vista previa PNG: árboles, pinos, palmeras, cerezos, arbustos, flores, hongos, rocas, cristales, casa, torre, pozo, puesto de mercado, cerca, banca, farol, antorcha, barril, caja, cofre, moneda, gema, espada, escudo, poción, cohete, calabaza, lápida, cactus, personaje, mesa, silla… Entiende cantidades y colores: *"3 rocas grises, una casa roja y dos palmeras"* |
| Mundo | Pack de estética (ver abajo) |

## Pack de mundo

Las texturas ahora incluyen **mapas PBR** (`_normal.png` y `_rugosidad.png`) y el script crea
**MaterialVariants** en MaterialService cuando subes el pack (Part.MaterialVariant = "<pack>_<textura>").
Texturas: piedra, madera, ladrillo, metal (oxidado), pasto, hojas, arena, nieve, hielo, asfalto,
baldosa, panel sci-fi, **lava, agua, adoquín y tejas**.

| Qué | Formato | Cómo se usa en Roblox |
|---|---|---|
| Iluminación, atmósfera, color, bloom, rayos de sol, partículas | `AplicarEstetica.lua` | Pegar en ServerScriptService o en la Command Bar |
| Skybox (6 caras) | PNG | Propiedades de `Sky` |
| Texturas tileables | PNG | Decals / SurfaceAppearance / MaterialVariant |
| Efectos de sonido | WAV | `Sound` (SoundService) |
| Música en loop | WAV | `Sound` con `Looped = true` |
| Props 3D low-poly | GLB | File → Import 3D |

## Todo queda en el disco externo

- `runtime\` — Python 3.12 portable (no se instala en Windows)
- `models\` — modelos de IA descargados (solo si usas IA local)
- `cache\` — temporales y cache de pip (se puede borrar con `LIMPIAR_CACHE.bat`)
- `output\` — tus packs generados
- `config\` — configuración y claves

Las rutas son relativas, así que funciona aunque el disco cambie de letra (E:, F:…).
Lo único que va fuera del disco es el plugin de Studio (unos KB), y solo si lo instalas.

## Inicio rápido

1. **`INSTALAR.bat`** (una sola vez, necesita internet). Descarga Python portable, numpy y Pillow (~60 MB en total).
2. **`INICIAR.bat`**: abre la app en el navegador (`http://127.0.0.1:8765`).
3. Escribe un tema y presiona **Generar pack**.

Funciona **sin internet, sin GPU y sin claves**: el modo `offline` genera todo
por código (síntesis de audio, ruido procedural, mallas low-poly). Para más calidad
activa los backends de IA.

## Backends (config\config.toml)

Cada módulo (`director`, `imagen`, `musica`, `sfx`, `malla3d`) tiene su `backend`:

- **offline**: procedural, gratis, instantáneo. Siempre es el respaldo si algo falla.
- **cloud**: APIs pagadas por uso. Pon tus claves en `config\secrets.env`:
  - `ANTHROPIC_API_KEY` → director con Claude (`director.backend = "anthropic"`), que ajusta paleta, luces y prompts al tema exacto.
  - `REPLICATE_API_TOKEN` → imagen (FLUX), música (MusicGen), SFX y 3D (imagen → malla).
    Los nombres y parámetros de modelos en Replicate cambian; verifica en replicate.com
    el identificador exacto y ponlo en `cloud_model`.
- **local**: tu GPU NVIDIA. Ejecuta `INSTALAR_IA_LOCAL.bat` (≈5–6 GB) y cambia a `backend = "local"`.
  Los modelos se descargan la primera vez a `models\huggingface` (2–7 GB cada uno).
  El director también puede usar **Ollama** (`director.backend = "ollama"`); para que Ollama guarde
  sus modelos en el disco, arráncalo con la variable `OLLAMA_MODELS` apuntando a `models\ollama`.

> ⚠️ **Licencias**: MusicGen y AudioLDM2 publican sus pesos bajo licencias **no comerciales**.
> Si vas a monetizar el juego, usa el modo offline o un modelo/servicio con licencia comercial.

## Subir a Roblox automáticamente (opcional)

1. Crea una API key en <https://create.roblox.com/dashboard/credentials> con permiso **Assets (read + write)**.
2. Ponla en `config\secrets.env` como `ROBLOX_API_KEY` y tu ID de usuario en `config.toml` → `[roblox] creator_id`.
3. En la app presiona **Subir a Roblox**. El script `AplicarEstetica.lua` se regenera con los `rbxassetid://`.

Límites de Roblox: el audio tiene cupo mensual (100 subidas con cuenta verificada por ID, 10 sin verificar)
y todo pasa por moderación. Si el skybox sale en blanco con los IDs subidos, en Studio pega el ID
en la propiedad del `Sky` a mano: Studio lo convierte de ID de Decal a ID de imagen.

## Plugin de Roblox Studio

`studio-plugin\RobloxAssetAI.plugin.lua`: en Studio, **Plugins → Plugins Folder**, copia el archivo y reinicia.
Con `INICIAR.bat` abierto puedes generar desde Studio e importar con un clic:
las **GUI se construyen en StarterGui**, el **código** se inserta como Script/LocalScript donde corresponde
(si es "dentro de una Part", selecciona la Part antes), y los **mundos** insertan su script de estética.
Studio pedirá permiso para conectarse a `127.0.0.1`: acéptalo.

Sin plugin: botón **Copiar CrearGUI.lua** y pégalo en la Command Bar (View → Command Bar).

## MCP (como ForgeMCP)

Copia el contenido de `MCP_CONFIG_EJEMPLO.json` en la configuración MCP de Claude Desktop
(Settings → Developer → Edit Config) o de tu agente. Si el disco no es `E:`, cambia la letra.
Herramientas: `generar_juego`, `generar_iconos`, `generar_gui`, `generar_miniatura`, `generar_sonido`,
`generar_codigo`, `generar_modelo3d`, `generar_mundo`, `listar_assets`.

## Opciones gratis para más calidad

- **Ollama** (LLM local, gratis): instala Ollama, `ollama pull llama3.2` y pon `director.backend = "ollama"`.
  Activa el chat inteligente, el estilo a medida y los scripts a medida.
- **Pollinations** (imágenes IA, plan gratis): crea una clave en enter.pollinations.ai, ponla en
  `secrets.env` y elige "Pollinations" en el selector del prompt. Sirve para texturas y fondos de miniaturas.
- **GPU local**: `INSTALAR_IA_LOCAL.bat` y selector "GPU local".

## Consola

`GENERAR_DESDE_CONSOLA.bat`, o bien:
```
runtime\python\python.exe -m app.cli "reino medieval con dragones" --subir
```

## Estructura del código

```
app/
  main.py            servidor web local + API (solo librería estándar)
  pipeline.py        orquestador: tema → estilo → assets → pack
  director.py        "cerebro" que define el estilo (offline / Claude / Ollama)
  presets.py         estéticas base: terror, tropical, espacio, fantasía, invierno, cyberpunk, desierto, bosque
  generators/
    audio_offline.py síntesis de 25 efectos + compositor de música en loop
    image_offline.py texturas tileables + PBR + skybox de 6 caras
    dsp.py           motor de audio: osciladores PolyBLEP, filtros, reverb por convolución
    sfx_pro.py       55 efectos de sonido por capas
    musica_pro.py    compositor por géneros (motivos, acordes, bajo, batería, mezcla estéreo)
    mesh_pro.py      39 modelos 3D, exportación GLB/OBJ y render de vista previa
    cloud.py         Replicate (imagen, audio, 3D)
    local.py         diffusers / transformers en GPU
  roblox/
    luau.py          genera AplicarEstetica.lua
    opencloud.py     subida con Open Cloud Assets API
  forge/
    studio.py        herramientas + agente (chat) + subida
    gui_kit.py       GUI real: spec JSON, render PNG, constructor Luau
    iconos.py        íconos procedurales
    miniaturas.py    miniaturas e ícono de juego
    scripts_lib.py   biblioteca de scripts Luau + LLM
  mcp_server.py      servidor MCP (stdio)
  diagnostico.py     revisión de compatibilidad
  ia/                motor IA: espacios (HF), motor, prompts, creador, agente, malla3d, fondo, imagenes
  blender/           puente con Blender + scripts bpy (limpiar_ia, pulir_procedural, render)
web/index.html       interfaz
studio-plugin/       plugin de Studio
assets/fonts/        fuentes libres (puedes agregar más .ttf)
```

Para agregar una estética nueva, copia un bloque en `app/presets.py` y cambia sus `keywords`.
