from __future__ import annotations

import shutil
from pathlib import Path

from .base import FlipperTransport


class MockMomentumTransport(FlipperTransport):
    """Momentum-first mock transport for Linux/macOS development."""

    def __init__(self, mock_root: str) -> None:
        self.root = Path(mock_root)
        self.root.mkdir(parents=True, exist_ok=True)
        (self.root / "ext").mkdir(exist_ok=True)

    def _resolve(self, path: str) -> Path:
        cleaned = path.lstrip("/")
        target = self.root / cleaned
        target.parent.mkdir(parents=True, exist_ok=True)
        return target

    def list_directory(self, path: str) -> list[dict]:
        p = self._resolve(path)
        if not p.exists():
            return []
        if not p.is_dir():
            raise NotADirectoryError(path)
        result = []
        for child in sorted(p.iterdir()):
            result.append({
                "name": child.name,
                "path": "/" + str(child.relative_to(self.root)),
                "is_directory": child.is_dir(),
                "size": child.stat().st_size,
            })
        return result

    def read_file(self, path: str) -> str:
        return self._resolve(path).read_text(encoding="utf-8")

    def write_file(self, path: str, content: str) -> int:
        target = self._resolve(path)
        target.write_text(content, encoding="utf-8")
        return len(content.encode("utf-8"))

    def create_directory(self, path: str) -> None:
        self._resolve(path).mkdir(parents=True, exist_ok=True)

    def delete(self, path: str, recursive: bool = False) -> None:
        target = self._resolve(path)
        if target.is_dir() and recursive:
            shutil.rmtree(target)
        elif target.is_dir():
            target.rmdir()
        else:
            target.unlink(missing_ok=False)

    def move(self, src: str, dest: str) -> None:
        shutil.move(str(self._resolve(src)), str(self._resolve(dest)))

    def copy(self, src: str, dest: str) -> None:
        s = self._resolve(src)
        d = self._resolve(dest)
        if s.is_dir():
            if d.exists():
                shutil.rmtree(d)
            shutil.copytree(s, d)
        else:
            shutil.copy2(s, d)

    def execute_cli(self, command: str) -> str:
        normalized = command.strip().lower()
        if normalized == "version":
            return "Momentum firmware mock 1.0.0"
        if normalized.startswith("loader open"):
            return f"app launched: {command}"
        if normalized.startswith(("subghz tx", "ir tx", "nfc emulate", "rfid emulate", "ibutton emulate", "badusb run")):
            return f"executed on mock momentum transport: {command}"
        if normalized.startswith("storage ls"):
            parts = command.split(maxsplit=2)
            path = parts[2] if len(parts) > 2 else "/ext"
            items = self.list_directory(path)
            return "\n".join(i["name"] for i in items)
        return f"mock_cli_ok: {command}"

    def get_device_info(self) -> dict:
        return {
            "name": "Flipper Zero (Mock)",
            "firmware_version": "Momentum",
            "hardware_version": "FZ.1",
            "battery_level": 87,
            "is_charging": False,
        }

    def get_storage_info(self) -> dict:
        total, used, free = shutil.disk_usage(self.root)
        return {
            "internal_total": total,
            "internal_free": free,
            "external_total": total,
            "external_free": free,
            "has_sd_card": True,
            "used": used,
        }

    def capability_profile(self) -> dict:
        return {
            "firmware_family": "MOMENTUM",
            "transport_mode": "MOCK_USB",
            "supports_cli": True,
            "supports_rpc": True,
            "supports_rpc_app_bridge": True,
            "platform_hint": "linux_macos",
        }
