"""Backend local con GPU. Requiere ejecutar INSTALAR_IA_LOCAL.bat (instala
PyTorch, diffusers y transformers DENTRO del disco externo). Los modelos se
descargan la primera vez a .\\models\\huggingface (varios GB).

Ojo con las licencias: MusicGen y AudioLDM2 tienen pesos para uso no comercial.
"""
from pathlib import Path

_pipes = {}


def _dispositivo():
    import torch
    if torch.cuda.is_available():
        return "cuda", torch.float16
    return "cpu", torch.float32


def imagen(modelo: str, prompt: str, destino: Path, tamano: int = 1024) -> Path:
    from diffusers import AutoPipelineForText2Image
    dev, dtype = _dispositivo()
    if modelo not in _pipes:
        _pipes[modelo] = AutoPipelineForText2Image.from_pretrained(modelo, torch_dtype=dtype).to(dev)
    pipe = _pipes[modelo]
    turbo = "turbo" in modelo.lower()
    img = pipe(prompt=prompt, num_inference_steps=2 if turbo else 30,
               guidance_scale=0.0 if turbo else 7.0,
               height=min(tamano, 512) if turbo else tamano, width=min(tamano, 512) if turbo else tamano).images[0]
    destino.parent.mkdir(parents=True, exist_ok=True)
    img.save(destino)
    return destino


def musica(modelo: str, prompt: str, destino: Path, duracion: float) -> Path:
    import scipy.io.wavfile
    from transformers import pipeline
    if modelo not in _pipes:
        dev, _ = _dispositivo()
        _pipes[modelo] = pipeline("text-to-audio", model=modelo, device=0 if dev == "cuda" else -1)
    tokens = int(duracion * 51.2)  # MusicGen ~50 tokens por segundo
    out = _pipes[modelo](prompt, forward_params={"do_sample": True, "max_new_tokens": min(tokens, 1500)})
    destino.parent.mkdir(parents=True, exist_ok=True)
    scipy.io.wavfile.write(destino, out["sampling_rate"], out["audio"].squeeze())
    return destino


def sfx(modelo: str, prompt: str, destino: Path, duracion: float) -> Path:
    import scipy.io.wavfile
    from diffusers import AudioLDM2Pipeline
    dev, dtype = _dispositivo()
    if modelo not in _pipes:
        _pipes[modelo] = AudioLDM2Pipeline.from_pretrained(modelo, torch_dtype=dtype).to(dev)
    audio = _pipes[modelo](prompt, num_inference_steps=100, audio_length_in_s=max(1.0, duracion)).audios[0]
    destino.parent.mkdir(parents=True, exist_ok=True)
    scipy.io.wavfile.write(destino, 16000, audio)
    return destino


def sfx_stable_audio(modelo: str, prompt: str, destino: Path, duracion: float) -> Path:
    """Stable Audio Open (efectos de sonido de alta calidad, licencia Stability Community)."""
    import scipy.io.wavfile
    import torch
    from diffusers import StableAudioPipeline
    dev, dtype = _dispositivo()
    if modelo not in _pipes:
        _pipes[modelo] = StableAudioPipeline.from_pretrained(modelo, torch_dtype=dtype).to(dev)
    gen = torch.Generator(dev).manual_seed(0)
    audio = _pipes[modelo](prompt, negative_prompt="low quality, noise", num_inference_steps=100,
                           audio_end_in_s=max(1.0, min(duracion, 47)), generator=gen).audios[0]
    destino.parent.mkdir(parents=True, exist_ok=True)
    scipy.io.wavfile.write(destino, _pipes[modelo].vae.sampling_rate, audio.T.float().cpu().numpy())
    return destino
