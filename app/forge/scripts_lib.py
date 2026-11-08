"""Generador de scripts Luau.

Gratis y offline: una biblioteca de sistemas comunes (monedas, guardado, tienda,
rondas, obby, puertas, ranking...). Si configuras un LLM (Ollama local = gratis,
o Claude), escribe scripts a medida y puede adaptar las plantillas.
"""
import json
import re
import urllib.request

from .. import config

PLANTILLAS = {
    "leaderstats_guardado": {
        "titulo": "Monedas + guardado (DataStore)",
        "keywords": ["moneda", "dinero", "cash", "leaderstats", "guardar", "datastore", "save", "currency", "puntos"],
        "tipo": "Script", "destino": "ServerScriptService",
        "codigo": '''-- Crea leaderstats (Monedas) y los guarda con DataStoreService.
-- Activa en Studio: Game Settings > Security > Enable Studio Access to API Services.
local Players = game:GetService("Players")
local DataStoreService = game:GetService("DataStoreService")
local store = DataStoreService:GetDataStore("DatosJugador_v1")

local function cargar(jugador)
	local stats = Instance.new("Folder")
	stats.Name = "leaderstats"
	stats.Parent = jugador
	local monedas = Instance.new("IntValue")
	monedas.Name = "Monedas"
	monedas.Parent = stats

	local ok, datos = pcall(function() return store:GetAsync("j_" .. jugador.UserId) end)
	if ok and datos then
		monedas.Value = datos.Monedas or 0
	elseif not ok then
		warn("No se pudieron cargar datos de", jugador.Name, datos)
	end
end

local function guardar(jugador)
	local stats = jugador:FindFirstChild("leaderstats")
	if not stats then return end
	local datos = { Monedas = stats.Monedas.Value }
	for intento = 1, 3 do
		local ok, err = pcall(function() store:SetAsync("j_" .. jugador.UserId, datos) end)
		if ok then return end
		warn("Reintentando guardado", intento, err)
		task.wait(1)
	end
end

Players.PlayerAdded:Connect(cargar)
Players.PlayerRemoving:Connect(guardar)
game:BindToClose(function()
	for _, j in Players:GetPlayers() do task.spawn(guardar, j) end
	task.wait(2)
end)
''',
    },
    "moneda_recoger": {
        "titulo": "Moneda recogible que reaparece",
        "keywords": ["recoger", "coleccionable", "pickup", "reaparece", "respawn", "coin"],
        "tipo": "Script", "destino": "Dentro de la Part de la moneda",
        "codigo": '''-- Pon este Script dentro de la Part de la moneda. Requiere leaderstats.Monedas.
local parte = script.Parent
local VALOR = 10
local TIEMPO_REAPARICION = 5
local activa = true

parte.Touched:Connect(function(toque)
	if not activa then return end
	local jugador = game.Players:GetPlayerFromCharacter(toque.Parent)
	if not jugador or not jugador:FindFirstChild("leaderstats") then return end
	activa = false
	jugador.leaderstats.Monedas.Value += VALOR
	parte.Transparency = 1
	parte.CanTouch = false
	local sonido = parte:FindFirstChildOfClass("Sound")
	if sonido then sonido:Play() end
	task.wait(TIEMPO_REAPARICION)
	parte.Transparency = 0
	parte.CanTouch = true
	activa = true
end)

-- giro decorativo
task.spawn(function()
	while parte.Parent do
		parte.CFrame *= CFrame.Angles(0, math.rad(3), 0)
		task.wait(0.03)
	end
end)
''',
    },
    "tienda_remote": {
        "titulo": "Tienda segura con RemoteEvent",
        "keywords": ["tienda", "shop", "comprar", "buy", "remote", "item", "vender"],
        "tipo": "Script", "destino": "ServerScriptService",
        "codigo": '''-- Servidor: valida compras. Crea ReplicatedStorage.Comprar automaticamente.
-- Cliente (LocalScript en el boton):  game.ReplicatedStorage.Comprar:FireServer("Espada")
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local ServerStorage = game:GetService("ServerStorage")

local evento = ReplicatedStorage:FindFirstChild("Comprar") or Instance.new("RemoteEvent")
evento.Name = "Comprar"
evento.Parent = ReplicatedStorage

-- Precios definidos SOLO en el servidor (el cliente no puede cambiarlos)
local PRECIOS = { Espada = 250, Pocion = 80, Escudo = 400 }
-- Las herramientas deben estar en ServerStorage.Items con el mismo nombre
local items = ServerStorage:FindFirstChild("Items")

local ultimo = {}
evento.OnServerEvent:Connect(function(jugador, nombre)
	if typeof(nombre) ~= "string" or not PRECIOS[nombre] then return end
	if ultimo[jugador] and os.clock() - ultimo[jugador] < 0.5 then return end -- anti spam
	ultimo[jugador] = os.clock()
	local monedas = jugador:FindFirstChild("leaderstats") and jugador.leaderstats:FindFirstChild("Monedas")
	if not monedas or monedas.Value < PRECIOS[nombre] then return end
	monedas.Value -= PRECIOS[nombre]
	if items and items:FindFirstChild(nombre) then
		items[nombre]:Clone().Parent = jugador.Backpack
	end
end)

game.Players.PlayerRemoving:Connect(function(j) ultimo[j] = nil end)
''',
    },
    "rondas": {
        "titulo": "Sistema de rondas (lobby / intermedio / partida)",
        "keywords": ["ronda", "round", "intermedio", "intermission", "partida", "minijuego", "lobby", "temporizador"],
        "tipo": "Script", "destino": "ServerScriptService",
        "codigo": '''-- Bucle de rondas. Necesita Parts llamadas "SpawnLobby" y "SpawnArena" en Workspace.
-- Muestra el estado en ReplicatedStorage.Estado (StringValue) para tu GUI.
local Players = game:GetService("Players")
local RS = game:GetService("ReplicatedStorage")

local MIN_JUGADORES = 2
local INTERMEDIO = 15
local DURACION = 90

local estado = RS:FindFirstChild("Estado") or Instance.new("StringValue")
estado.Name = "Estado"
estado.Parent = RS

local function teletransportar(jugadores, destino)
	for _, j in jugadores do
		local raiz = j.Character and j.Character:FindFirstChild("HumanoidRootPart")
		if raiz then raiz.CFrame = destino.CFrame + Vector3.new(math.random(-6, 6), 4, math.random(-6, 6)) end
	end
end

while true do
	repeat
		estado.Value = "Esperando jugadores (" .. #Players:GetPlayers() .. "/" .. MIN_JUGADORES .. ")"
		task.wait(1)
	until #Players:GetPlayers() >= MIN_JUGADORES

	for t = INTERMEDIO, 1, -1 do
		estado.Value = "Intermedio: " .. t
		task.wait(1)
	end

	local vivos = Players:GetPlayers()
	teletransportar(vivos, workspace.SpawnArena)
	for t = DURACION, 1, -1 do
		for i = #vivos, 1, -1 do
			local hum = vivos[i].Character and vivos[i].Character:FindFirstChildOfClass("Humanoid")
			if not vivos[i].Parent or not hum or hum.Health <= 0 then table.remove(vivos, i) end
		end
		if #vivos <= 1 then break end
		estado.Value = "Partida: " .. t .. "s | Vivos: " .. #vivos
		task.wait(1)
	end

	estado.Value = (#vivos == 1) and ("¡Gano " .. vivos[1].Name .. "!") or "¡Tiempo!"
	for _, j in vivos do
		local m = j:FindFirstChild("leaderstats") and j.leaderstats:FindFirstChild("Monedas")
		if m then m.Value += 50 end
	end
	task.wait(4)
	teletransportar(Players:GetPlayers(), workspace.SpawnLobby)
end
''',
    },
    "lava": {
        "titulo": "Bloque de lava (mata al tocar)",
        "keywords": ["lava", "kill", "matar", "trampa", "obby", "obstaculo", "muerte", "daño"],
        "tipo": "Script", "destino": "Dentro de la Part de lava",
        "codigo": '''-- Pon este Script dentro de una Part. Mata (o daña) al tocarla.
local parte = script.Parent
local DANO = 100 -- usa 20 para dano parcial
local enfriamiento = {}

parte.Material = Enum.Material.Neon
parte.Color = Color3.fromRGB(255, 85, 0)

parte.Touched:Connect(function(toque)
	local hum = toque.Parent:FindFirstChildOfClass("Humanoid")
	if not hum or enfriamiento[hum] then return end
	enfriamiento[hum] = true
	hum:TakeDamage(DANO)
	task.wait(0.5)
	enfriamiento[hum] = nil
end)
''',
    },
    "checkpoints": {
        "titulo": "Checkpoints de obby (guarda la etapa)",
        "keywords": ["checkpoint", "etapa", "stage", "obby", "parkour", "spawn", "progreso"],
        "tipo": "Script", "destino": "ServerScriptService",
        "codigo": '''-- Crea una carpeta Workspace.Checkpoints con Parts llamadas 1, 2, 3...
-- El jugador reaparece en el ultimo checkpoint tocado. Etapa visible en leaderstats.
local Players = game:GetService("Players")
local carpeta = workspace:WaitForChild("Checkpoints")

Players.PlayerAdded:Connect(function(jugador)
	local stats = jugador:FindFirstChild("leaderstats") or Instance.new("Folder")
	stats.Name = "leaderstats"
	stats.Parent = jugador
	local etapa = Instance.new("IntValue")
	etapa.Name = "Etapa"
	etapa.Value = 1
	etapa.Parent = stats

	jugador.CharacterAdded:Connect(function(personaje)
		local cp = carpeta:FindFirstChild(tostring(etapa.Value))
		if cp then
			local raiz = personaje:WaitForChild("HumanoidRootPart")
			task.wait()
			raiz.CFrame = cp.CFrame + Vector3.new(0, 4, 0)
		end
	end)
end)

for _, cp in carpeta:GetChildren() do
	local numero = tonumber(cp.Name)
	if cp:IsA("BasePart") and numero then
		cp.Touched:Connect(function(toque)
			local jugador = Players:GetPlayerFromCharacter(toque.Parent)
			if jugador and jugador.leaderstats.Etapa.Value == numero - 1 then
				jugador.leaderstats.Etapa.Value = numero
			end
		end)
	end
end
''',
    },
    "puerta_tween": {
        "titulo": "Puerta que se abre (ProximityPrompt + Tween)",
        "keywords": ["puerta", "door", "abrir", "tween", "prompt", "proximity", "interactuar"],
        "tipo": "Script", "destino": "Dentro de la Part de la puerta",
        "codigo": '''-- Pon este Script dentro de la Part de la puerta (Anchored).
local TweenService = game:GetService("TweenService")
local puerta = script.Parent
local cerrada = puerta.CFrame
local abierta = cerrada * CFrame.new(0, puerta.Size.Y, 0) -- sube; cambia por un giro si prefieres
local info = TweenInfo.new(0.8, Enum.EasingStyle.Quad, Enum.EasingDirection.Out)

local prompt = Instance.new("ProximityPrompt")
prompt.ActionText = "Abrir"
prompt.ObjectText = "Puerta"
prompt.HoldDuration = 0.2
prompt.Parent = puerta

local abiertaAhora = false
prompt.Triggered:Connect(function()
	abiertaAhora = not abiertaAhora
	prompt.ActionText = abiertaAhora and "Cerrar" or "Abrir"
	TweenService:Create(puerta, info, { CFrame = abiertaAhora and abierta or cerrada }):Play()
end)
''',
    },
    "ranking_global": {
        "titulo": "Tabla de lideres global (OrderedDataStore)",
        "keywords": ["ranking", "leaderboard", "lideres", "top", "global", "tabla", "mejores"],
        "tipo": "Script", "destino": "ServerScriptService",
        "codigo": '''-- Guarda las monedas en un OrderedDataStore y muestra el top 10 en
-- una Part llamada "Ranking" (con SurfaceGui > ScrollingFrame) o en la consola.
local Players = game:GetService("Players")
local ods = game:GetService("DataStoreService"):GetOrderedDataStore("RankingMonedas_v1")
local INTERVALO = 60

local function actualizar()
	for _, j in Players:GetPlayers() do
		local m = j:FindFirstChild("leaderstats") and j.leaderstats:FindFirstChild("Monedas")
		if m then pcall(function() ods:SetAsync(tostring(j.UserId), m.Value) end) end
	end
	local ok, pagina = pcall(function() return ods:GetSortedAsync(false, 10):GetCurrentPage() end)
	if not ok then return end
	local tabla = workspace:FindFirstChild("Ranking")
	local lista = tabla and tabla:FindFirstChildWhichIsA("SurfaceGui", true)
	lista = lista and lista:FindFirstChildWhichIsA("ScrollingFrame", true)
	if lista then
		for _, h in lista:GetChildren() do if h:IsA("TextLabel") then h:Destroy() end end
		if not lista:FindFirstChildOfClass("UIListLayout") then Instance.new("UIListLayout", lista) end
	end
	for pos, entrada in pagina do
		local nombre = "?"
		pcall(function() nombre = Players:GetNameFromUserIdAsync(tonumber(entrada.key)) end)
		local linea = ("#%d  %s  -  %d"):format(pos, nombre, entrada.value)
		if lista then
			local t = Instance.new("TextLabel")
			t.Size = UDim2.new(1, 0, 0, 40)
			t.BackgroundTransparency = 1
			t.TextScaled = true
			t.Text = linea
			t.TextColor3 = Color3.new(1, 1, 1)
			t.Parent = lista
		else
			print(linea)
		end
	end
end

while true do
	actualizar()
	task.wait(INTERVALO)
end
''',
    },
    "correr_shift": {
        "titulo": "Correr con Shift (sprint con estamina)",
        "keywords": ["correr", "sprint", "shift", "velocidad", "estamina", "stamina", "run"],
        "tipo": "LocalScript", "destino": "StarterPlayer > StarterPlayerScripts",
        "codigo": '''local Players = game:GetService("Players")
local UIS = game:GetService("UserInputService")
local RunService = game:GetService("RunService")

local NORMAL, RAPIDO = 16, 28
local estamina, MAX, GASTO, RECARGA = 100, 100, 25, 15
local corriendo = false

local function humanoide()
	local c = Players.LocalPlayer.Character
	return c and c:FindFirstChildOfClass("Humanoid")
end

UIS.InputBegan:Connect(function(i, gp)
	if not gp and i.KeyCode == Enum.KeyCode.LeftShift then corriendo = true end
end)
UIS.InputEnded:Connect(function(i)
	if i.KeyCode == Enum.KeyCode.LeftShift then corriendo = false end
end)

RunService.Heartbeat:Connect(function(dt)
	local hum = humanoide()
	if not hum then return end
	local moviendose = hum.MoveDirection.Magnitude > 0
	if corriendo and moviendose and estamina > 0 then
		estamina = math.max(0, estamina - GASTO * dt)
		hum.WalkSpeed = RAPIDO
	else
		estamina = math.min(MAX, estamina + RECARGA * dt)
		hum.WalkSpeed = NORMAL
	end
	Players.LocalPlayer:SetAttribute("Estamina", estamina) -- lee esto desde tu GUI
end)
''',
    },
    "plataforma_desaparece": {
        "titulo": "Plataforma que desaparece al pisarla",
        "keywords": ["plataforma", "desaparece", "cae", "fragil", "platform", "vanish"],
        "tipo": "Script", "destino": "Dentro de la Part",
        "codigo": '''local p = script.Parent
local ESPERA, OCULTA = 0.6, 3
local ocupada = false

p.Touched:Connect(function(t)
	if ocupada or not t.Parent:FindFirstChildOfClass("Humanoid") then return end
	ocupada = true
	for i = 1, 6 do
		p.Transparency = (i % 2 == 0) and 0.2 or 0.6
		task.wait(ESPERA / 6)
	end
	p.Transparency, p.CanCollide = 1, false
	task.wait(OCULTA)
	p.Transparency, p.CanCollide = 0, true
	ocupada = false
end)
''',
    },
}


def buscar(pedido: str) -> list:
    t = pedido.lower()
    puntos = []
    for clave, pl in PLANTILLAS.items():
        s = sum(1 for k in pl["keywords"] if k in t)
        if s:
            puntos.append((s, clave))
    return [c for _, c in sorted(puntos, reverse=True)]


SYSTEM = """Eres un experto programador de Roblox (Luau moderno). Escribe codigo listo para usar,
seguro (valida todo en el servidor, nunca confies en el cliente), con comentarios breves en espanol.
Indica al inicio, en un comentario, donde va el script (ServerScriptService, StarterPlayerScripts, dentro de una Part...)
y si es Script o LocalScript. Usa task.wait/task.spawn, no wait(). Devuelve SOLO un bloque ```lua.```"""


def _llm(pedido: str, base: str | None) -> str:
    cfg = config.get()["director"]
    user = pedido if not base else f"{pedido}\n\nPuedes partir de esta plantilla:\n```lua\n{base}\n```"
    if cfg["backend"] == "anthropic":
        key = config.secret("ANTHROPIC_API_KEY")
        body = {"model": cfg.get("anthropic_model", "claude-haiku-5-5"), "max_tokens": 4000, "system": SYSTEM,
                "messages": [{"role": "user", "content": user}]}
        req = urllib.request.Request("https://api.anthropic.com/v1/messages", data=json.dumps(body).encode(),
                                     headers={"x-api-key": key, "anthropic-version": "2023-06-01", "content-type": "application/json"})
        with urllib.request.urlopen(req, timeout=180) as r:
            texto = "".join(b.get("text", "") for b in json.loads(r.read())["content"])
    elif cfg["backend"] == "ollama":
        body = {"model": cfg.get("ollama_model", "llama3.2"), "stream": False,
                "messages": [{"role": "system", "content": SYSTEM}, {"role": "user", "content": user}]}
        req = urllib.request.Request(cfg.get("ollama_url", "http://127.0.0.1:11434") + "/api/chat",
                                     data=json.dumps(body).encode(), headers={"content-type": "application/json"})
        with urllib.request.urlopen(req, timeout=600) as r:
            texto = json.loads(r.read())["message"]["content"]
    else:
        raise RuntimeError("offline")
    m = re.search(r"```(?:lua|luau)?\s*\n(.*?)```", texto, re.S)
    return (m.group(1) if m else texto).strip() + "\n"


def generar(pedido: str, log=print) -> dict:
    coincidencias = buscar(pedido)
    base = PLANTILLAS[coincidencias[0]]["codigo"] if coincidencias else None
    backend = config.get()["director"]["backend"]
    if backend != "offline":
        try:
            log(f"Escribiendo script con IA ({backend})...")
            return {"titulo": pedido[:60], "codigo": _llm(pedido, base), "fuente": backend, "relacionados": coincidencias[1:4]}
        except Exception as e:  # noqa: BLE001
            log(f"IA no disponible ({e}); uso la biblioteca offline.")
    if not coincidencias:
        return {"titulo": "Sin coincidencias", "fuente": "offline", "relacionados": list(PLANTILLAS)[:6],
                "codigo": "-- No encontre una plantilla para eso en modo offline.\n"
                          "-- Prueba con: monedas, tienda, rondas, lava, checkpoints, puerta, ranking, correr...\n"
                          "-- O activa un LLM gratis (Ollama) en config.toml para scripts a medida.\n"}
    pl = PLANTILLAS[coincidencias[0]]
    cabecera = f"-- {pl['titulo']}\n-- Tipo: {pl['tipo']}   |   Donde: {pl['destino']}\n"
    return {"titulo": pl["titulo"], "codigo": cabecera + pl["codigo"], "fuente": "offline",
            "tipo": pl["tipo"], "destino": pl["destino"], "relacionados": coincidencias[1:4]}
