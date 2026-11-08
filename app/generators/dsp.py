"""Motor de audio (solo numpy): osciladores sin aliasing, filtros, reverb por convolucion,
delay, saturacion, envolventes y exportacion WAV mono/estereo."""
import wave
from pathlib import Path

import numpy as np

SR = 44100


# ------------------------------------------------------------- basicos
def t(dur):
    return np.arange(int(SR * dur)) / SR


def n_muestras(dur):
    return max(1, int(SR * dur))


def env_adsr(n, a=0.005, d=0.1, s=0.7, r=0.1):
    """ADSR en segundos; r se aplica al final de las n muestras."""
    a_n, d_n, r_n = int(a * SR), int(d * SR), int(r * SR)
    env = np.full(n, s, dtype=float)
    a_n = min(a_n, n)
    if a_n:
        env[:a_n] = np.linspace(0, 1, a_n, endpoint=False)
    fin_d = min(n, a_n + d_n)
    if fin_d > a_n:
        env[a_n:fin_d] = np.linspace(1, s, fin_d - a_n, endpoint=False)
    r_n = min(r_n, n)
    if r_n:
        env[n - r_n:] *= np.linspace(1, 0, r_n)
    return env


def env_exp(n, decay, a=0.002):
    """Ataque lineal corto + caida exponencial (decay = segundos hasta -60 dB)."""
    tt = np.arange(n) / SR
    e = np.exp(-6.9 * tt / max(decay, 1e-4))
    a_n = min(n, max(1, int(a * SR)))
    e[:a_n] *= np.linspace(0, 1, a_n)
    return e


def _fase(freq, n):
    f = np.broadcast_to(np.asarray(freq, float), (n,))
    return np.cumsum(f) / SR, f / SR


def _blep(tf, dt):
    """Correccion PolyBLEP (reduce aliasing de saw/square)."""
    out = np.zeros_like(tf)
    m = tf < dt
    x = tf[m] / dt[m]
    out[m] = x + x - x * x - 1
    m2 = tf > 1 - dt
    x = (tf[m2] - 1) / dt[m2]
    out[m2] = x * x + x + x + 1
    return out


def osc(freq, dur=None, forma="sin", n=None, fase0=0.0, ancho=0.5):
    n = n or n_muestras(dur)
    ph, dt = _fase(freq, n)
    ph = ph + fase0
    if forma == "sin":
        return np.sin(2 * np.pi * ph)
    tf = ph % 1.0
    dt = np.maximum(dt, 1e-6)
    if forma == "saw":
        return 2 * tf - 1 - _blep(tf, dt)
    if forma in ("square", "pulse"):
        y = np.where(tf < ancho, 1.0, -1.0)
        y += _blep(tf, dt)
        y -= _blep((tf - ancho) % 1.0, dt)
        return y
    if forma == "tri":
        return 2 * np.abs(2 * tf - 1) - 1
    raise ValueError(forma)


def fm(fc, ratio, indice, dur=None, n=None, env_indice=None):
    """Sintesis FM simple (campanas, pianos electricos, steel drums)."""
    n = n or n_muestras(dur)
    tt = np.arange(n) / SR
    idx = indice * (env_indice if env_indice is not None else 1.0)
    mod = np.sin(2 * np.pi * fc * ratio * tt)
    return np.sin(2 * np.pi * fc * tt + idx * mod)


def ruido(n, rng, color="blanco"):
    x = rng.standard_normal(n)
    if color == "blanco":
        return x / 3
    X = np.fft.rfft(x)
    f = np.fft.rfftfreq(n, 1 / SR)
    f[0] = 1
    X *= 1 / np.sqrt(f) if color == "rosa" else 1 / f
    y = np.fft.irfft(X, n)
    return y / (np.max(np.abs(y)) + 1e-9)


# ------------------------------------------------------------- filtros (dominio de frecuencia)
def _resp(f, tipo, fc, q):
    w = f / max(fc, 1.0)
    if tipo == "lp":
        return 1 / np.sqrt((1 - w ** 2) ** 2 + (w / q) ** 2)
    if tipo == "hp":
        return w ** 2 / np.sqrt((1 - w ** 2) ** 2 + (w / q) ** 2)
    if tipo == "bp":
        return (w / q) / np.sqrt((1 - w ** 2) ** 2 + (w / q) ** 2)
    raise ValueError(tipo)


def filtro(x, tipo, fc, q=0.707, orden=1):
    n = len(x)
    if n < 4:
        return x
    X = np.fft.rfft(x)
    f = np.fft.rfftfreq(n, 1 / SR)
    H = _resp(f, tipo, fc, q) ** orden
    return np.fft.irfft(X * H, n)


def filtro_barrido(x, tipo, fc_ini, fc_fin, q=0.9, bloque=1024):
    """Filtro con frecuencia de corte variable (STFT con solapamiento)."""
    n = len(x)
    if n < bloque * 2:
        return filtro(x, tipo, (fc_ini + fc_fin) / 2, q)
    salto = bloque // 2
    ventana = np.hanning(bloque)
    pad = np.concatenate([x, np.zeros(bloque)])
    out = np.zeros(len(pad))
    norma = np.zeros(len(pad))
    f = np.fft.rfftfreq(bloque, 1 / SR)
    pasos = range(0, n, salto)
    fcs = np.geomspace(max(fc_ini, 20), max(fc_fin, 20), len(pasos))
    for i, ini in enumerate(pasos):
        trozo = pad[ini:ini + bloque] * ventana
        y = np.fft.irfft(np.fft.rfft(trozo) * _resp(f, tipo, fcs[i], q), bloque)
        out[ini:ini + bloque] += y * ventana
        norma[ini:ini + bloque] += ventana ** 2
    return out[:n] / np.maximum(norma[:n], 1e-3)


# ------------------------------------------------------------- efectos
def conv_fft(a, b):
    n = len(a) + len(b) - 1
    N = 1 << (n - 1).bit_length()
    return np.fft.irfft(np.fft.rfft(a, N) * np.fft.rfft(b, N), N)[:n]


def impulso(tiempo=1.8, brillo=6000, rng=None, predelay=0.012):
    rng = rng or np.random.default_rng(3)
    n = n_muestras(tiempo)
    ir = rng.standard_normal(n) * env_exp(n, tiempo, a=0.004)
    ir = filtro(ir, "lp", brillo, 0.6)
    # el agudo decae antes que el grave (mas natural)
    oscuro = filtro(ir, "lp", brillo * 0.25, 0.6)
    mezcla = np.linspace(0, 1, n) ** 0.7
    ir = ir * (1 - mezcla) + oscuro * mezcla
    ir = np.concatenate([np.zeros(int(predelay * SR)), ir])
    for d, g in ((0.007, 0.5), (0.013, 0.35), (0.021, 0.28)):  # reflexiones tempranas
        k = int(d * SR)
        if k < len(ir):
            ir[k] += g
    return ir / (np.sqrt(np.sum(ir ** 2)) + 1e-9)


def reverb(x, tiempo=1.6, mezcla=0.25, brillo=6000, semilla=3):
    ir = impulso(tiempo, brillo, np.random.default_rng(semilla))
    mojado = conv_fft(x, ir)
    seco = np.concatenate([x, np.zeros(len(mojado) - len(x))])
    return seco * (1 - mezcla * 0.5) + mojado * mezcla


def delay(x, tiempo=0.25, feedback=0.35, mezcla=0.3, repeticiones=6, lp=5000):
    k = int(tiempo * SR)
    out = np.concatenate([x, np.zeros(k * repeticiones)])
    eco = x * mezcla
    for i in range(1, repeticiones + 1):
        eco = filtro(eco, "lp", lp)
        out[k * i:k * i + len(eco)] += eco
        eco = eco * feedback
    return out


def saturar(x, drive=2.0):
    return np.tanh(x * drive) / np.tanh(drive)


def bitcrush(x, bits=6, reduccion=4):
    y = np.repeat(x[::reduccion], reduccion)[:len(x)]
    q = 2 ** (bits - 1)
    return np.round(y * q) / q


def cambiar_tono(x, factor):
    """Sube/baja el tono re-muestreando (tambien cambia la duracion, como un sampler)."""
    if abs(factor - 1) < 1e-3:
        return x
    n = int(len(x) / factor)
    return np.interp(np.arange(n) * factor, np.arange(len(x)), x)


def fundido(x, ini=0.002, fin=0.01):
    x = x.copy()
    a, b = min(len(x), int(ini * SR)), min(len(x), int(fin * SR))
    if a:
        x[:a] *= np.linspace(0, 1, a)
    if b:
        x[-b:] *= np.linspace(1, 0, b)
    return x


def recortar_silencio(x, umbral_db=-55):
    idx = np.where(np.abs(x) > np.max(np.abs(x) + 1e-9) * 10 ** (umbral_db / 20))[0]
    if len(idx) == 0:
        return x
    return x[max(0, idx[0] - 32): idx[-1] + int(0.02 * SR)]


def normalizar(x, pico_db=-1.0):
    m = np.max(np.abs(x)) + 1e-9
    return x / m * 10 ** (pico_db / 20)


def limitador(x, umbral=0.8):
    """Limitador suave: por encima del umbral comprime con tanh."""
    s = np.sign(x)
    a = np.abs(x)
    sobre = a > umbral
    a[sobre] = umbral + (1 - umbral) * np.tanh((a[sobre] - umbral) / (1 - umbral))
    return s * a


def panear(x, pan=0.0):
    """pan -1 (izq) .. 1 (der), ley de potencia constante. Devuelve (n, 2)."""
    ang = (pan + 1) * np.pi / 4
    return np.stack([x * np.cos(ang), x * np.sin(ang)], 1)


def poner(pista, sonido, inicio_seg):
    i = int(inicio_seg * SR)
    if i >= len(pista) or i < 0:
        return
    f = min(len(pista), i + len(sonido))
    pista[i:f] += sonido[: f - i]


def guardar_wav(path: Path, audio, sr: int = SR, normal=True) -> Path:
    a = np.asarray(audio, float)
    if normal:
        a = normalizar(a, -1.0)
    a = np.clip(a, -1, 1)
    canales = 1 if a.ndim == 1 else a.shape[1]
    datos = (a * 32767).astype("<i2")
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(canales)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(datos.tobytes())
    return path
