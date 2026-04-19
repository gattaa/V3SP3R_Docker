from __future__ import annotations

from pathlib import Path


class PlaintextConfigStore:
    """Simple local plaintext config for migration phase."""

    def __init__(self, path: str) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self.path.write_text("", encoding="utf-8")

    def load(self) -> dict[str, str]:
        out: dict[str, str] = {}
        for line in self.path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            out[k.strip()] = v.strip()
        return out

    def get(self, key: str, default: str | None = None) -> str | None:
        return self.load().get(key, default)

    def set(self, key: str, value: str) -> None:
        cfg = self.load()
        cfg[key] = value
        content = "\n".join(f"{k}={v}" for k, v in sorted(cfg.items())) + "\n"
        self.path.write_text(content, encoding="utf-8")
