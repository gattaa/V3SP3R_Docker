from __future__ import annotations

import time
from dataclasses import dataclass

from .base import FlipperTransport


class UnsupportedTransportError(RuntimeError):
    """Raised when USB transport is unavailable on the current host/runtime."""


@dataclass
class UsbTransportConfig:
    device_path: str
    baud_rate: int = 230400
    read_timeout_s: float = 0.8


class PyFlipperUsbTransport(FlipperTransport):
    """Momentum-first USB transport scaffold.

    This implementation is intentionally conservative and provides graceful
    unsupported behavior when USB serial dependencies or a target device are
    unavailable. It is designed to be swapped in incrementally as command-level
    compatibility is validated against real Momentum firmware.
    """

    MAX_IDLE_ROUNDS = 2

    def __init__(self, config: UsbTransportConfig) -> None:
        self.config = config
        self._serial = None
        self._serial_module = None
        self._profile = self._probe_capabilities()

    def _probe_capabilities(self) -> dict:
        profile = {
            "firmware_family": "MOMENTUM",
            "transport_mode": "USB_SERIAL",
            "supports_cli": False,
            "supports_rpc": False,
            "supports_rpc_app_bridge": False,
            "connected": False,
            "unsupported_reason": "",
        }
        try:
            import serial  # type: ignore

            self._serial_module = serial
        except ImportError:
            profile["unsupported_reason"] = (
                "pyserial is not installed; install it to enable USB transport"
            )
            return profile

        try:
            with self._serial_module.Serial(
                self.config.device_path,
                self.config.baud_rate,
                timeout=self.config.read_timeout_s,
            ):
                pass
            profile["supports_cli"] = True
            profile["connected"] = True
            return profile
        except (
            getattr(self._serial_module, "SerialException", OSError),
            OSError,
            ValueError,
        ) as exc:
            profile["unsupported_reason"] = str(exc)
            return profile

    def capability_profile(self) -> dict:
        return dict(self._profile)

    def _ensure_connected(self) -> None:
        if not self._profile.get("supports_cli"):
            raise UnsupportedTransportError(
                self._profile.get("unsupported_reason") or "USB CLI transport unavailable"
            )
        if self._serial is None:
            self._serial = self._serial_module.Serial(
                self.config.device_path,
                self.config.baud_rate,
                timeout=self.config.read_timeout_s,
            )
            time.sleep(0.05)

    def execute_cli(self, command: str) -> str:
        self._ensure_connected()
        if self._serial is None:
            raise UnsupportedTransportError("USB CLI transport is not connected")
        cmd = command.strip() + "\r\n"
        self._serial.write(cmd.encode("utf-8"))
        self._serial.flush()

        lines: list[str] = []
        idle_rounds = 0
        while idle_rounds < self.MAX_IDLE_ROUNDS:
            raw = self._serial.readline()
            if not raw:
                idle_rounds += 1
                continue
            idle_rounds = 0
            line = raw.decode("utf-8", errors="replace").rstrip("\r\n")
            if line:
                lines.append(line)
        return "\n".join(lines)

    def list_directory(self, path: str) -> list[dict]:
        output = self.execute_cli(f"storage ls {path}")
        entries: list[dict] = []
        for line in output.splitlines():
            name = line.strip()
            if not name:
                continue
            entries.append(
                {
                    "name": name,
                    "path": f"{path.rstrip('/')}/{name}",
                    "is_directory": False,
                    "size": 0,
                }
            )
        return entries

    def read_file(self, path: str) -> str:
        return self.execute_cli(f"storage read {path}")

    def write_file(self, path: str, content: str) -> int:
        raise UnsupportedTransportError(
            "Direct USB write_file is not implemented yet; use mock transport for write workflows"
        )

    def create_directory(self, path: str) -> None:
        self.execute_cli(f"storage mkdir {path}")

    def delete(self, path: str, recursive: bool = False) -> None:
        if recursive:
            self.execute_cli(f"storage remove_recursive {path}")
        else:
            self.execute_cli(f"storage remove {path}")

    def move(self, src: str, dest: str) -> None:
        self.execute_cli(f"storage rename {src} {dest}")

    def copy(self, src: str, dest: str) -> None:
        self.execute_cli(f"storage copy {src} {dest}")

    def get_device_info(self) -> dict:
        info = self.execute_cli("device_info")
        return {
            "name": "Flipper Zero",
            "firmware_version": "Momentum",
            "hardware_version": "unknown",
            "battery_level": 0,
            "is_charging": False,
            "raw": info,
        }

    def get_storage_info(self) -> dict:
        info = self.execute_cli("storage info")
        return {
            "internal_total": 0,
            "internal_free": 0,
            "external_total": 0,
            "external_free": 0,
            "has_sd_card": True,
            "raw": info,
        }
