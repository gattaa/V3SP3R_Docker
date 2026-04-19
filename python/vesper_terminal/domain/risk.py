from __future__ import annotations

from .models import CommandAction, ExecuteCommand, RiskAssessment, RiskLevel
from .permission import PermissionService


SYSTEM_PATHS = ["/int/", "/int/.region", "/int/manifest.txt", "/ext/.region"]
FIRMWARE_PATHS = ["/int/update/", "/ext/update/"]
SENSITIVE_EXTENSIONS = [".key", ".priv", ".secret"]


class RiskAssessor:
    def __init__(self, permission_service: PermissionService) -> None:
        self.permission_service = permission_service

    def assess(self, command: ExecuteCommand) -> RiskAssessment:
        paths = self._extract_paths(command)
        blocked = next(
            (
                p
                for p in paths
                if self._is_protected(p)
                and not self.permission_service.is_protected_path_unlocked(p)
            ),
            None,
        )
        if blocked:
            return RiskAssessment(
                level=RiskLevel.BLOCKED,
                reason="Protected path",
                affected_paths=paths,
                requires_diff=False,
                requires_confirmation=False,
                blocked_reason=self._blocked_reason(blocked),
            )

        action = command.action
        if action in {
            CommandAction.LIST_DIRECTORY,
            CommandAction.READ_FILE,
            CommandAction.GET_DEVICE_INFO,
            CommandAction.GET_STORAGE_INFO,
            CommandAction.SEARCH_FAPHUB,
            CommandAction.SEARCH_RESOURCES,
            CommandAction.LIST_VAULT,
            CommandAction.BROWSE_REPO,
            CommandAction.GITHUB_SEARCH,
            CommandAction.REQUEST_PHOTO,
            CommandAction.LED_CONTROL,
            CommandAction.VIBRO_CONTROL,
        }:
            return RiskAssessment(RiskLevel.LOW, "Read-only operation", paths, False, False)

        if action == CommandAction.WRITE_FILE:
            path = command.args.path or ""
            in_scope = self.permission_service.has_permission(path, CommandAction.WRITE_FILE)
            return RiskAssessment(
                level=RiskLevel.MEDIUM if in_scope else RiskLevel.HIGH,
                reason="File modification" if in_scope else "Write outside permitted scope",
                affected_paths=paths,
                requires_diff=True,
                requires_confirmation=not in_scope,
            )

        if action == CommandAction.CREATE_DIRECTORY:
            path = command.args.path or ""
            in_scope = self.permission_service.has_permission(path, CommandAction.CREATE_DIRECTORY)
            return RiskAssessment(
                level=RiskLevel.LOW if in_scope else RiskLevel.MEDIUM,
                reason="Directory creation in scope" if in_scope else "Directory creation outside scope",
                affected_paths=paths,
                requires_diff=False,
                requires_confirmation=not in_scope,
            )

        if action in {
            CommandAction.DELETE,
            CommandAction.MOVE,
            CommandAction.RENAME,
            CommandAction.BADUSB_EXECUTE,
            CommandAction.INSTALL_FAPHUB_APP,
        }:
            reason = (
                "Recursive deletion"
                if action == CommandAction.DELETE and command.args.recursive
                else f"{action.value} operation"
            )
            return RiskAssessment(RiskLevel.HIGH, reason, paths, False, True)

        if action == CommandAction.COPY:
            dest = command.args.destination_path or ""
            in_scope = self.permission_service.has_permission(dest, CommandAction.WRITE_FILE)
            return RiskAssessment(
                level=RiskLevel.MEDIUM if in_scope else RiskLevel.HIGH,
                reason="Copy operation" if in_scope else "Copy to unscoped destination",
                affected_paths=paths,
                requires_diff=False,
                requires_confirmation=not in_scope,
            )

        if action in {
            CommandAction.PUSH_ARTIFACT,
            CommandAction.FORGE_PAYLOAD,
            CommandAction.RUN_RUNBOOK,
            CommandAction.DOWNLOAD_RESOURCE,
            CommandAction.LAUNCH_APP,
            CommandAction.SUBGHZ_TRANSMIT,
            CommandAction.IR_TRANSMIT,
            CommandAction.NFC_EMULATE,
            CommandAction.RFID_EMULATE,
            CommandAction.IBUTTON_EMULATE,
            CommandAction.BLE_SPAM,
            CommandAction.EXECUTE_CLI,
        }:
            return RiskAssessment(
                RiskLevel.MEDIUM,
                "Potentially state-changing operation",
                paths,
                False,
                True,
            )

        return RiskAssessment(RiskLevel.HIGH, "Unclassified operation", paths, False, True)

    def _extract_paths(self, command: ExecuteCommand) -> list[str]:
        paths: list[str] = []
        if command.args.path:
            paths.append(command.args.path)
        if command.args.destination_path:
            paths.append(command.args.destination_path)
        if command.action == CommandAction.EXECUTE_CLI:
            cli = command.args.command or command.args.content or ""
            paths.extend(token for token in cli.split() if token.startswith("/"))
        return paths

    def _is_protected(self, path: str) -> bool:
        return (
            any(path.startswith(p) for p in SYSTEM_PATHS)
            or any(path.startswith(p) for p in FIRMWARE_PATHS)
            or any(path.endswith(ext) for ext in SENSITIVE_EXTENSIONS)
        )

    def _blocked_reason(self, path: str) -> str:
        if any(path.startswith(p) for p in SYSTEM_PATHS):
            return "System path requires settings unlock"
        if any(path.startswith(p) for p in FIRMWARE_PATHS):
            return "Firmware path requires settings unlock"
        if any(path.endswith(ext) for ext in SENSITIVE_EXTENSIONS):
            return "Sensitive file type requires settings unlock"
        return "Protected path requires settings unlock"
