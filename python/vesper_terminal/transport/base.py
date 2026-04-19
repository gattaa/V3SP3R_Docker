from __future__ import annotations

from abc import ABC, abstractmethod


class FlipperTransport(ABC):
    @abstractmethod
    def list_directory(self, path: str) -> list[dict]: ...

    @abstractmethod
    def read_file(self, path: str) -> str: ...

    @abstractmethod
    def write_file(self, path: str, content: str) -> int: ...

    @abstractmethod
    def create_directory(self, path: str) -> None: ...

    @abstractmethod
    def delete(self, path: str, recursive: bool = False) -> None: ...

    @abstractmethod
    def move(self, src: str, dest: str) -> None: ...

    @abstractmethod
    def copy(self, src: str, dest: str) -> None: ...

    @abstractmethod
    def execute_cli(self, command: str) -> str: ...

    @abstractmethod
    def get_device_info(self) -> dict: ...

    @abstractmethod
    def get_storage_info(self) -> dict: ...

    @abstractmethod
    def capability_profile(self) -> dict: ...
