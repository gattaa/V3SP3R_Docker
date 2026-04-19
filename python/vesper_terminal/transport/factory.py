from __future__ import annotations

from pathlib import Path

from vesper_terminal.data.config_store import PlaintextConfigStore

from .base import FlipperTransport
from .mock_momentum import MockMomentumTransport
from .pyflipper_usb import PyFlipperUsbTransport, UsbTransportConfig


def create_transport(config: PlaintextConfigStore, data_dir: Path) -> tuple[FlipperTransport, dict]:
    mode = (config.get("TRANSPORT_MODE", "mock") or "mock").strip().lower()
    allow_fallback = (config.get("ALLOW_MOCK_FALLBACK", "true") or "true").strip().lower() == "true"

    if mode in {"usb", "pyflipper_usb"}:
        device_path = config.get("USB_DEVICE_PATH", "/dev/ttyACM0") or "/dev/ttyACM0"
        baud_rate = int(config.get("USB_BAUD_RATE", "230400") or "230400")
        usb = PyFlipperUsbTransport(
            UsbTransportConfig(device_path=device_path, baud_rate=baud_rate)
        )
        profile = usb.capability_profile()
        if profile.get("supports_cli"):
            return usb, profile
        if not allow_fallback:
            return usb, profile

    mock = MockMomentumTransport(str(data_dir / "flipper_mock_fs"))
    profile = mock.capability_profile()
    profile["mock_mode"] = True
    return mock, profile
