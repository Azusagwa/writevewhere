from __future__ import annotations

from datetime import datetime
from pathlib import Path

from PySide6.QtGui import QPixmap


def save_screenshot(pixmap: QPixmap, root: Path | None = None, timestamp: str | None = None) -> Path:
    output_dir = (root or project_root()) / "screenshot"
    output_dir.mkdir(parents=True, exist_ok=True)
    stamp = timestamp or datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = output_dir / f"screenshot_{stamp}.png"
    pixmap.save(str(output_path), "PNG")
    return output_path


def project_root() -> Path:
    module_path = Path(__file__).resolve()
    for parent in module_path.parents:
        if (parent / "setup.py").exists() and (parent / "writevewhere").is_dir():
            return parent
    return Path.cwd()
