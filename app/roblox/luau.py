"""Genera el script Luau que aplica toda la estetica del pack en Roblox Studio."""


def _c3(h: str) -> str:
    h = h.lstrip("#")
    return f"Color3.fromRGB({int(h[0:2], 16)}, {int(h[2:4], 16)}, {int(h[4:6], 16)})"


def _valor(v):
    if isinstance(v, str) and v.startswith("#") and len(v) == 7:
        return _c3(v)
    if isinstance(v, bool):
        return "true" if v else "false"
    return repr(v) if isinstance(v, (int, float)) else f'"{v}"'


def _props(var: str, d: dict) -> str:
    return "\n".join(f"\t{var}.{k} = {_valor(v)}" for k, v in d.items())


def _id(manifest: dict, clave: str) -> str:
    aid = manifest.get("asset_ids", {}).get(clave)
    return f"rbxassetid://{aid}" if aid else ""


def script_estetica(estilo: dict, manifest: dict) -> str:
    nombre = estilo["nombre"]
    sky_lines = "\n".join(
        f'\tsky.{cara} = "{_id(manifest, f"skybox/{cara}.png")}"'
        for cara in ("SkyboxBk", "SkyboxDn", "SkyboxFt", "SkyboxLf", "SkyboxRt", "SkyboxUp"))
    sonidos = []
    for s in manifest.get("sfx", []):
        sonidos.append(f'\t{{ nombre = "{s["nombre"]}", id = "{_id(manifest, s["archivo"])}" }},')
    musica = manifest.get("musica")
    musica_id = _id(manifest, musica) if musica else ""
    particulas = []
    for p in estilo.get("particulas", []):
        particulas.append(
            f'\t{{ nombre = "{p["nombre"]}", color = {_c3(p["color"])}, rate = {p["rate"]}, '
            f'lifetime = {p["lifetime"]}, size = {p["size"]}, speed = {p["speed"]} }},')
    paleta = ", ".join(_c3(c) for c in estilo["paleta"])
    mats = []
    for nombre_t, mp in manifest.get("pbr", {}).items():
        mats.append(f'\t\t{{ nombre = "{nombre}_{nombre_t}", base = "{mp["material"]}", color = "{_id(manifest, mp["color"])}", '
                    f'normal = "{_id(manifest, mp["normal"])}", rugosidad = "{_id(manifest, mp["rugosidad"])}" }},')

    plantilla = f'''-- =====================================================================
--  Estetica generada por Roblox Asset AI
--  Tema: {estilo["tema"]}   |   Mood: {estilo["mood"]}
--
--  USO: pega este script en ServerScriptService y presiona Play,
--  o copia todo y ejecutalo en la Command Bar de Studio (View > Command Bar)
--  para aplicarlo de forma permanente al lugar.
--  Los IDs vacios ("") se rellenan al subir el pack con Open Cloud.
-- =====================================================================

local Lighting = game:GetService("Lighting")
local SoundService = game:GetService("SoundService")
local Workspace = game:GetService("Workspace")

local PACK = "{nombre}"
local PALETA = {{ {paleta} }}

local function limpiar(clase: string)
	for _, o in Lighting:GetChildren() do
		if o:IsA(clase) then o:Destroy() end
	end
end

-- ---------------------------------------------------------- Iluminacion
do
	local L = Lighting
{_props("L", {k: v for k, v in estilo["lighting"].items()})}
	pcall(function() L.Technology = Enum.Technology.Future end) -- solo funciona desde Studio/Command Bar
end

-- ---------------------------------------------------------- Atmosfera y efectos
limpiar("Atmosphere"); limpiar("ColorCorrectionEffect"); limpiar("BloomEffect"); limpiar("SunRaysEffect")
do
	local atm = Instance.new("Atmosphere")
{_props("atm", estilo["atmosphere"])}
	atm.Parent = Lighting

	local cc = Instance.new("ColorCorrectionEffect")
{_props("cc", estilo["color_correction"])}
	cc.Parent = Lighting

	local bloom = Instance.new("BloomEffect")
{_props("bloom", estilo["bloom"])}
	bloom.Parent = Lighting

	local rays = Instance.new("SunRaysEffect")
{_props("rays", estilo["sunrays"])}
	rays.Parent = Lighting
end

-- ---------------------------------------------------------- Cielo
do
	local tieneIds = {"true" if manifest.get("asset_ids", {}).get("skybox/SkyboxFt.png") else "false"}
	if tieneIds then
		limpiar("Sky")
		local sky = Instance.new("Sky")
{sky_lines}
		sky.Name = PACK .. "_Sky"
		sky.Parent = Lighting
	else
		warn("[" .. PACK .. "] Skybox sin IDs: sube el pack o importa las imagenes de /skybox manualmente.")
	end
end

-- ---------------------------------------------------------- Materiales PBR (MaterialVariant)
do
	local MaterialService = game:GetService("MaterialService")
	local MATERIALES = {{
__MATERIALES__
	}}
	for _, mv in MATERIALES do
		if mv.color ~= "" then
			local v = MaterialService:FindFirstChild(mv.nombre) or Instance.new("MaterialVariant")
			v.Name = mv.nombre
			v.BaseMaterial = Enum.Material[mv.base]
			v.ColorMap = mv.color
			if mv.normal ~= "" then v.NormalMap = mv.normal end
			if mv.rugosidad ~= "" then v.RoughnessMap = mv.rugosidad end
			v.StudsPerTile = 8
			v.Parent = MaterialService
		end
	end
	-- Usalo en una Part:  Part.Material = Enum.Material.<base>;  Part.MaterialVariant = "<nombre>"
end

-- ---------------------------------------------------------- Musica y sonidos
do
	local carpeta = SoundService:FindFirstChild(PACK) or Instance.new("Folder")
	carpeta.Name = PACK
	carpeta.Parent = SoundService

	local musicaId = "{musica_id}"
	if musicaId ~= "" then
		local m = carpeta:FindFirstChild("Musica") :: Sound? or Instance.new("Sound")
		m.Name = "Musica"
		m.SoundId = musicaId
		m.Looped = true
		m.Volume = 0.4
		m.Parent = carpeta
		if game:GetService("RunService"):IsRunning() then m:Play() end
	end

	local SFX = {{
{chr(10).join(sonidos)}
	}}
	for _, s in SFX do
		if s.id ~= "" then
			local snd = carpeta:FindFirstChild(s.nombre) :: Sound? or Instance.new("Sound")
			snd.Name = s.nombre
			snd.SoundId = s.id
			snd.Volume = 0.7
			snd.Parent = carpeta
		end
	end
	-- Para reproducir un efecto desde otro script:
	--   game.SoundService.{nombre}.moneda:Play()
end

-- ---------------------------------------------------------- Particulas ambientales
do
	local PART = {{
{chr(10).join(particulas)}
	}}
	local ancla = Workspace:FindFirstChild(PACK .. "_Ambiente") :: Part? or Instance.new("Part")
	ancla.Name = PACK .. "_Ambiente"
	ancla.Anchored = true
	ancla.CanCollide = false
	ancla.CanQuery = false
	ancla.Transparency = 1
	ancla.Size = Vector3.new(400, 1, 400)
	ancla.Position = Vector3.new(0, 60, 0)
	ancla.Parent = Workspace
	for _, p in PART do
		local e = ancla:FindFirstChild(p.nombre) :: ParticleEmitter? or Instance.new("ParticleEmitter")
		e.Name = p.nombre
		e.Color = ColorSequence.new(p.color)
		e.Rate = p.rate
		e.Lifetime = NumberRange.new(p.lifetime * 0.8, p.lifetime * 1.2)
		e.Size = NumberSequence.new(p.size)
		e.Speed = NumberRange.new(p.speed * 0.5, p.speed)
		e.EmissionDirection = Enum.NormalId.Bottom
		e.LightEmission = 0.3
		e.Transparency = NumberSequence.new({{NumberSequenceKeypoint.new(0, 1), NumberSequenceKeypoint.new(0.2, 0.2), NumberSequenceKeypoint.new(1, 1)}})
		e.Parent = ancla
	end
end

print("[" .. PACK .. "] Estetica aplicada. Paleta:", #PALETA, "colores")
'''
    return plantilla.replace("__MATERIALES__", "\n".join(mats))
