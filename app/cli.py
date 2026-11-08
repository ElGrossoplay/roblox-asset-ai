"""Uso por consola:  python -m app.cli "isla tropical de terror" [--subir]"""
import sys

from .paths import force_portable_env

force_portable_env()

from . import pipeline  # noqa: E402


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if not args:
        print('Uso: python -m app.cli "tema del juego" [--subir]')
        return
    carpeta = pipeline.generar_pack(" ".join(args))
    if "--subir" in sys.argv:
        pipeline.subir_pack(carpeta)
    print(f"\nPack en: {carpeta}")


if __name__ == "__main__":
    main()
