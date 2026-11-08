--[[
	Roblox Asset AI - plugin para Roblox Studio (v2)
	Conecta Studio con la app local (INICIAR.bat debe estar abierto).

	- GUI kits   -> construye el ScreenGui real en StarterGui (editable)
	- Codigo     -> inserta el Script / LocalScript donde corresponde
	- Mundo      -> inserta el script de estetica (luces, atmosfera, sonidos)
	- Prompt     -> genera desde Studio con el agente

	Instalacion: Plugins > Plugins Folder, copia este archivo y reinicia Studio.
	La primera vez Studio pide permiso para conectarse a 127.0.0.1: aceptalo.
]]

local HttpService = game:GetService("HttpService")
local ChangeHistoryService = game:GetService("ChangeHistoryService")
local Selection = game:GetService("Selection")

local SERVIDOR = "http://127.0.0.1:8765"  -- si la app uso otro puerto, el plugin lo busca solo (8765-8779)
local FONDO, PANEL, AZUL, TEXTO, GRIS = Color3.fromRGB(11, 14, 21), Color3.fromRGB(23, 28, 39),
	Color3.fromRGB(47, 123, 255), Color3.fromRGB(233, 237, 245), Color3.fromRGB(138, 148, 168)

local toolbar = plugin:CreateToolbar("Roblox Asset AI")
local boton = toolbar:CreateButton("Asset AI", "Generar e importar assets", "rbxasset://textures/ui/GuiImagePlaceholder.png")
local info = DockWidgetPluginGuiInfo.new(Enum.InitialDockState.Right, false, false, 340, 520, 280, 320)
local ventana = plugin:CreateDockWidgetPluginGui("RobloxAssetAI_v2", info)
ventana.Title = "Roblox Asset AI"

-- ------------------------------------------------------------- UI
local raiz = Instance.new("Frame")
raiz.Size = UDim2.fromScale(1, 1)
raiz.BackgroundColor3 = FONDO
raiz.BorderSizePixel = 0
raiz.Parent = ventana
local pad = Instance.new("UIPadding")
pad.PaddingTop, pad.PaddingLeft, pad.PaddingRight, pad.PaddingBottom = UDim.new(0, 10), UDim.new(0, 10), UDim.new(0, 10), UDim.new(0, 10)
pad.Parent = raiz
local layout = Instance.new("UIListLayout")
layout.Padding = UDim.new(0, 6)
layout.SortOrder = Enum.SortOrder.LayoutOrder
layout.Parent = raiz

local function esquina(o, r)
	local c = Instance.new("UICorner")
	c.CornerRadius = UDim.new(0, r or 8)
	c.Parent = o
end

local function crear(clase, orden, props)
	local o = Instance.new(clase)
	o.LayoutOrder = orden
	o.Size = UDim2.new(1, 0, 0, 32)
	o.BackgroundColor3 = PANEL
	o.BorderSizePixel = 0
	if o:IsA("TextLabel") or o:IsA("TextButton") or o:IsA("TextBox") then
		o.TextColor3 = TEXTO
		o.Font = Enum.Font.GothamMedium
		o.TextSize = 14
	end
	for k, v in props do o[k] = v end
	esquina(o)
	o.Parent = raiz
	return o
end

local herramienta = "chat"
local HERR = { { "chat", "Agente" }, { "gui", "GUI" }, { "iconos", "Iconos" }, { "codigo", "Codigo" }, { "sonido", "Sonido" }, { "mundo", "Mundo" } }

local tabs = crear("Frame", 1, { BackgroundTransparency = 1, Size = UDim2.new(1, 0, 0, 28) })
local tl = Instance.new("UIListLayout")
tl.FillDirection = Enum.FillDirection.Horizontal
tl.Padding = UDim.new(0, 4)
tl.Parent = tabs
local botonesTab = {}
for i, h in HERR do
	local b = Instance.new("TextButton")
	b.LayoutOrder = i
	b.Size = UDim2.new(1 / #HERR, -4, 1, 0)
	b.BackgroundColor3 = PANEL
	b.TextColor3 = TEXTO
	b.Font = Enum.Font.GothamBold
	b.TextSize = 12
	b.Text = h[2]
	b.BorderSizePixel = 0
	esquina(b, 6)
	b.Parent = tabs
	botonesTab[h[1]] = b
	b.MouseButton1Click:Connect(function()
		herramienta = h[1]
		for k, bb in botonesTab do bb.BackgroundColor3 = (k == herramienta) and AZUL or PANEL end
	end)
end
botonesTab.chat.BackgroundColor3 = AZUL

local entrada = crear("TextBox", 2, { PlaceholderText = "Que vamos a crear?", Text = "", ClearTextOnFocus = false,
	Size = UDim2.new(1, 0, 0, 60), TextWrapped = true, TextXAlignment = Enum.TextXAlignment.Left, TextYAlignment = Enum.TextYAlignment.Top })
local p2 = Instance.new("UIPadding")
p2.PaddingLeft, p2.PaddingTop = UDim.new(0, 8), UDim.new(0, 6)
p2.Parent = entrada
local generar = crear("TextButton", 3, { Text = "Generar", BackgroundColor3 = AZUL, Font = Enum.Font.GothamBold })
local estado = crear("TextLabel", 4, { Text = "Listo.", TextWrapped = true, BackgroundTransparency = 1, TextColor3 = GRIS,
	Size = UDim2.new(1, 0, 0, 38), TextXAlignment = Enum.TextXAlignment.Left, TextSize = 12 })
local refrescar = crear("TextButton", 5, { Text = "Actualizar mis assets", Size = UDim2.new(1, 0, 0, 28), TextSize = 13 })

local lista = Instance.new("ScrollingFrame")
lista.LayoutOrder = 6
lista.Size = UDim2.new(1, 0, 1, -230)
lista.BackgroundTransparency = 1
lista.BorderSizePixel = 0
lista.AutomaticCanvasSize = Enum.AutomaticSize.Y
lista.CanvasSize = UDim2.new()
lista.ScrollBarThickness = 5
lista.Parent = raiz
local ll = Instance.new("UIListLayout")
ll.Padding = UDim.new(0, 4)
ll.SortOrder = Enum.SortOrder.LayoutOrder
ll.Parent = lista

-- ------------------------------------------------------------- HTTP
local function buscarServidor()
	for puerto = 8765, 8779 do
		local url = "http://127.0.0.1:" .. puerto
		local ok, res = pcall(function()
			return HttpService:RequestAsync({ Url = url .. "/api/estado", Method = "GET" })
		end)
		if ok and res.Success then
			SERVIDOR = url
			return true
		end
	end
	return false
end

local function pedir(metodo, ruta, cuerpo, reintento)
	local ok, res = pcall(function()
		return HttpService:RequestAsync({
			Url = SERVIDOR .. ruta, Method = metodo,
			Headers = { ["Content-Type"] = "application/json" },
			Body = cuerpo and HttpService:JSONEncode(cuerpo) or nil,
		})
	end)
	if not ok then
		if not reintento and buscarServidor() then return pedir(metodo, ruta, cuerpo, true) end
		return nil, "Sin conexion: abre INICIAR.bat en tu disco."
	end
	if not res.Success then return nil, "Error " .. res.StatusCode end
	return res.Body
end

-- ------------------------------------------------------------- constructor de GUI (mismo formato que CrearGUI.lua)
local ENUMS = { Font = Enum.Font, TextXAlignment = Enum.TextXAlignment, TextYAlignment = Enum.TextYAlignment, ZIndexBehavior = Enum.ZIndexBehavior }
local function valor(k, v)
	if k == "Position" or k == "Size" then return UDim2.new(v[1], v[2], v[3], v[4]) end
	if k == "AnchorPoint" then return Vector2.new(v[1], v[2]) end
	if type(v) == "string" and string.sub(k, -6) == "Color3" then return Color3.fromHex(v) end
	if ENUMS[k] then
		local ok, item = pcall(function() return ENUMS[k][v] end)  -- un nombre invalido lanza error en Luau
		if ok and item then return item end
		return k == "Font" and Enum.Font.GothamBold or nil
	end
	return v
end
local ARTE_IDS, ARTE_TAM = {}, {}
local function decorar(obj, d)
	if d.arte and ARTE_IDS[d.arte] then
		local tam = ARTE_TAM[d.arte] or { 512, 512 }
		local mx, my = math.floor(tam[1] * 0.28), math.floor(tam[2] * 0.28)
		obj.BackgroundTransparency = 1
		local im = Instance.new("ImageLabel")
		im.Name = "Arte"
		im.BackgroundTransparency = 1
		im.Size = UDim2.fromScale(1, 1)
		im.Image = "rbxassetid://" .. ARTE_IDS[d.arte]
		im.ScaleType = Enum.ScaleType.Slice
		im.SliceCenter = Rect.new(mx, my, tam[1] - mx, tam[2] - my)
		im.ZIndex = 0
		im.Parent = obj
		if d.aspecto then
			local a = Instance.new("UIAspectRatioConstraint")
			a.AspectRatio = d.aspecto
			a.Parent = obj
		end
		return
	end
	local function corner(o)
		if d.radio and d.radio > 0 then
			local c = Instance.new("UICorner")
			c.CornerRadius = d.radio >= 99 and UDim.new(0.5, 0) or UDim.new(0, d.radio)
			c.Parent = o
		end
	end
	corner(obj)
	if d.borde then
		local s = Instance.new("UIStroke")
		s.Thickness = d.borde
		s.Color = Color3.fromHex(d.borde_color)
		s.ApplyStrokeMode = Enum.ApplyStrokeMode.Border
		s.Parent = obj
	end
	if d.grad then
		obj.BackgroundColor3 = Color3.new(1, 1, 1)
		local g = Instance.new("UIGradient")
		g.Color = ColorSequence.new(Color3.fromHex(d.grad[1]), Color3.fromHex(d.grad[2]))
		g.Rotation = 90
		g.Parent = obj
	end
	if d.aspecto then
		local a = Instance.new("UIAspectRatioConstraint")
		a.AspectRatio = d.aspecto
		a.Parent = obj
	end
	if d.max_texto then
		local t = Instance.new("UITextSizeConstraint")
		t.MaxTextSize = d.max_texto
		t.Parent = obj
	end
	if d.brillo then
		local b = Instance.new("Frame")
		b.Name = "Brillo"
		b.BackgroundColor3 = Color3.new(1, 1, 1)
		b.BackgroundTransparency = 0.8
		b.BorderSizePixel = 0
		b.Size = UDim2.fromScale(1, 0.45)
		b.Parent = obj
		corner(b)
	end
end
local function construir(n, padre, ids)
	local obj
	if n.c == "Icono" then
		local id = ids[n.i]
		if id and id ~= "" then
			obj = Instance.new("ImageLabel")
			obj.Image = "rbxassetid://" .. id
			obj.ScaleType = Enum.ScaleType.Fit
		else
			obj = Instance.new("TextLabel")
			obj.Text = n.e or "?"
			obj.TextScaled = true
		end
		obj.BackgroundTransparency = 1
	else
		obj = Instance.new(n.c)
	end
	obj.Name = n.n
	if obj:IsA("GuiObject") then obj.BorderSizePixel = 0 end
	for k, v in n.p do pcall(function() obj[k] = valor(k, v) end) end
	decorar(obj, n.d or {})
	for _, h in n.h or {} do construir(h, obj, ids) end
	obj.Parent = padre
	return obj
end

local CONTROL = [==[
local gui = script.Parent
local function alternar(panel)
	for _, p in { gui.PanelTienda, gui.PanelInventario } do p.Visible = (p == panel) and not p.Visible end
end
gui.MenuLateral.BotonTienda.Activated:Connect(function() alternar(gui.PanelTienda) end)
gui.MenuLateral.BotonInventario.Activated:Connect(function() alternar(gui.PanelInventario) end)
gui.PanelTienda.Cerrar.Activated:Connect(function() gui.PanelTienda.Visible = false end)
gui.PanelInventario.Cerrar.Activated:Connect(function() gui.PanelInventario.Visible = false end)
gui.BotonJugar.Activated:Connect(function() gui.BotonJugar.Visible = false end)
task.delay(4, function() if gui:FindFirstChild("Aviso") then gui.Aviso.Visible = false end end)
]==]

local function grabar(nombre, fn)
	local id = ChangeHistoryService:TryBeginRecording(nombre)
	local ok, err = pcall(fn)
	if id then ChangeHistoryService:FinishRecording(id, ok and Enum.FinishRecordingOperation.Commit or Enum.FinishRecordingOperation.Cancel) end
	if not ok then estado.Text = "Error: " .. tostring(err) end
	return ok
end

local function importar(a)
	local carpeta = HttpService:UrlEncode(a.carpeta)
	if a.tipo == "gui" then
		local body, err = pedir("GET", "/api/pack/" .. carpeta .. "/gui.json")
		if not body then estado.Text = err return end
		local spec = HttpService:JSONDecode(body)
		ARTE_IDS, ARTE_TAM = spec.ids_arte or {}, spec.arte_tam or {}
		grabar("Importar GUI", function()
			local sg = game:GetService("StarterGui")
			local viejo = sg:FindFirstChild(spec.raiz.n)
			if viejo then viejo:Destroy() end
			local gui = construir(spec.raiz, sg, spec.ids or {})
			local ls = Instance.new("LocalScript")
			ls.Name = "ControlPaneles"
			ls.Source = CONTROL
			ls.Parent = gui
			Selection:Set({ gui })
		end)
		estado.Text = "GUI creada en StarterGui (" .. (spec.estilo or "") .. "). Edita libremente."
	elseif a.tipo == "codigo" or a.tipo == "mundo" then
		local codigo, err = pedir("GET", "/api/pack/" .. carpeta .. "/script")
		if not codigo then estado.Text = err return end
		grabar("Insertar script", function()
			local esLocal = a.tipo_script == "LocalScript"
			local s = Instance.new(esLocal and "LocalScript" or "Script")
			s.Name = (a.tipo == "mundo" and "Estetica_" or "") .. string.sub(a.carpeta, 1, 40)
			s.Source = codigo
			local destino = a.destino or ""
			local sel = Selection:Get()[1]
			if string.find(destino, "Part") and sel and sel:IsA("BasePart") then
				s.Parent = sel
			elseif esLocal then
				s.Parent = game:GetService("StarterPlayer"):FindFirstChildOfClass("StarterPlayerScripts")
			else
				s.Parent = game:GetService("ServerScriptService")
			end
			Selection:Set({ s })
		end)
		estado.Text = "Script insertado. " .. ((a.destino and string.find(a.destino, "Part")) and "Tip: selecciona la Part antes de importar." or "")
	else
		estado.Text = "Este tipo se importa con File > Import 3D o subiendolo a Roblox desde la app."
	end
end

local function cargar()
	for _, h in lista:GetChildren() do if h:IsA("TextButton") then h:Destroy() end end
	local body, err = pedir("GET", "/api/packs")
	if not body then estado.Text = err return end
	local assets = HttpService:JSONDecode(body)
	local n = 0
	for _, a in assets do
		if a.tipo == "gui" or a.tipo == "codigo" or a.tipo == "mundo" then
			n += 1
			local b = Instance.new("TextButton")
			b.LayoutOrder = n
			b.Size = UDim2.new(1, -6, 0, 40)
			b.BackgroundColor3 = PANEL
			b.BorderSizePixel = 0
			b.TextColor3 = TEXTO
			b.Font = Enum.Font.Gotham
			b.TextSize = 13
			b.TextWrapped = true
			b.TextXAlignment = Enum.TextXAlignment.Left
			b.Text = "  [" .. string.upper(a.tipo) .. "]  " .. (a.tema or a.carpeta)
			esquina(b, 6)
			b.Parent = lista
			b.MouseButton1Click:Connect(function() importar(a) end)
		end
	end
	estado.Text = n .. " assets importables. Haz clic para importar."
end

local ocupado = false
generar.MouseButton1Click:Connect(function()
	if ocupado or entrada.Text == "" then return end
	ocupado = true
	estado.Text = "Generando..."
	local body, err = pedir("POST", "/api/enviar", { prompt = entrada.Text, herramienta = herramienta })
	if not body then estado.Text = err ocupado = false return end
	local trabajo = HttpService:JSONDecode(body).trabajo
	task.spawn(function()
		while true do
			task.wait(1)
			local b = pedir("GET", "/api/trabajo/" .. trabajo)
			if not b then break end
			local t = HttpService:JSONDecode(b)
			estado.Text = t.log[#t.log] or "..."
			if t.estado ~= "corriendo" then
				if t.info and (t.info.tipo == "gui" or t.info.tipo == "codigo") then importar(t.info) end
				break
			end
		end
		ocupado = false
		cargar()
	end)
end)

refrescar.MouseButton1Click:Connect(cargar)
boton.Click:Connect(function()
	ventana.Enabled = not ventana.Enabled
	if ventana.Enabled then cargar() end
end)
