import sys
from pathlib import Path


def resource_path(relative: str) -> Path:
    """Путь к ресурсу: работает из исходников и из PyInstaller .exe."""
    base = getattr(sys, "_MEIPASS", None)
    if base:
        return Path(base) / relative
    return Path(__file__).resolve().parent.parent / relative
