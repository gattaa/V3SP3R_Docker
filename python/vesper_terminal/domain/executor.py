from __future__ import annotations

import difflib
import time
from pathlib import PurePosixPath
from typing import Optional

from .models import (
    AuditActionType,
    AuditEntry,
    CommandAction,
    CommandResult,
    CommandResultData,
    ExecuteCommand,
    FileDiff,
    PendingApproval,
    RiskAssessment,
    RiskLevel,
)
from .permission import PermissionService
from .risk import RiskAssessor
from vesper_terminal.transport.base import FlipperTransport
from vesper_terminal.data.persistence import SqlitePersistence


class CommandExecutor:
    def __init__(
        self,
        transport: FlipperTransport,
        risk_assessor: RiskAssessor,
        permission_service: PermissionService,
        persistence: SqlitePersistence,
        auto_approve_medium: bool = False,
        auto_approve_high: bool = False,
    ) -> None:
        self.transport = transport
        self.risk_assessor = risk_assessor
        self.permission_service = permission_service
        self.persistence = persistence
        self.auto_approve_medium = auto_approve_medium
        self.auto_approve_high = auto_approve_high
        self.pending: dict[str, PendingApproval] = {}

    def execute(self, command: ExecuteCommand, session_id: str) -> CommandResult:
        self._clear_expired_approvals()
        self._audit(AuditEntry(action_type=AuditActionType.COMMAND_RECEIVED, command=command, session_id=session_id))
        start_time = time.time()
        risk = self.risk_assessor.assess(command)

        if risk.level == RiskLevel.BLOCKED:
            result = CommandResult(False, command.action, error=f"Blocked: {risk.blocked_reason or 'Protected path'}")
            self._audit(AuditEntry(action_type=AuditActionType.COMMAND_BLOCKED, command=command, result=result, risk_level=risk.level, session_id=session_id))
            return result

        if risk.level == RiskLevel.MEDIUM and not self.auto_approve_medium and (risk.requires_confirmation or risk.requires_diff):
            return self._request_approval(command, risk, session_id)

        if risk.level == RiskLevel.HIGH and not self.auto_approve_high:
            return self._request_approval(command, risk, session_id)

        return self._execute_direct(command, session_id, risk.level, start_time)

    def _request_approval(
        self,
        command: ExecuteCommand,
        risk: RiskAssessment,
        session_id: str,
    ) -> CommandResult:
        diff: Optional[FileDiff] = None
        if command.action == CommandAction.WRITE_FILE and command.args.path and command.args.content is not None:
            old_content = None
            try:
                old_content = self.transport.read_file(command.args.path)
            except Exception:
                old_content = None
            diff = self._compute_diff(old_content, command.args.content)

        pending = PendingApproval(command=command, risk_assessment=risk, diff=diff)
        self.pending[pending.id] = pending
        self._audit(AuditEntry(action_type=AuditActionType.APPROVAL_REQUESTED, command=command, risk_level=risk.level, session_id=session_id, metadata={"approval_id": pending.id}))
        return CommandResult(
            success=True,
            action=command.action,
            data=CommandResultData(diff=diff, message=f"Awaiting user approval for {risk.reason}"),
            requires_confirmation=True,
            pending_approval_id=pending.id,
        )

    def approve(self, approval_id: str, session_id: str) -> CommandResult:
        self._clear_expired_approvals()
        pending = self.pending.pop(approval_id, None)
        if not pending:
            result = CommandResult(False, None, error="Approval not found or expired")
            self._audit(AuditEntry(action_type=AuditActionType.APPROVAL_TIMEOUT, session_id=session_id, result=result, metadata={"approval_id": approval_id}))
            return result

        self._audit(AuditEntry(action_type=AuditActionType.APPROVAL_GRANTED, command=pending.command, risk_level=pending.risk_assessment.level, user_approved=True, session_id=session_id, metadata={"approval_id": approval_id}))
        return self._execute_direct(pending.command, session_id, pending.risk_assessment.level, time.time())

    def reject(self, approval_id: str, session_id: str) -> CommandResult:
        self._clear_expired_approvals()
        pending = self.pending.pop(approval_id, None)
        if not pending:
            result = CommandResult(False, None, error="Approval not found or expired")
            self._audit(AuditEntry(action_type=AuditActionType.APPROVAL_TIMEOUT, session_id=session_id, result=result, metadata={"approval_id": approval_id}))
            return result

        result = CommandResult(False, pending.command.action, error="Action rejected by user")
        self._audit(AuditEntry(action_type=AuditActionType.APPROVAL_DENIED, command=pending.command, result=result, risk_level=pending.risk_assessment.level, user_approved=False, session_id=session_id, metadata={"approval_id": approval_id}))
        return result

    def get_pending_approval(self, approval_id: str) -> Optional[PendingApproval]:
        self._clear_expired_approvals()
        return self.pending.get(approval_id)

    def _execute_direct(self, command: ExecuteCommand, session_id: str, risk_level: RiskLevel, start_time: float) -> CommandResult:
        try:
            data = self._execute_action(command)
            result = CommandResult(True, command.action, data=data, execution_time_ms=int((time.time() - start_time) * 1000))
            self._audit(AuditEntry(action_type=AuditActionType.COMMAND_EXECUTED, command=command, result=result, risk_level=risk_level, user_approved=True, session_id=session_id))
            return result
        except Exception as exc:
            result = CommandResult(False, command.action, error=f"{command.action.value}: {exc}", execution_time_ms=int((time.time() - start_time) * 1000))
            self._audit(AuditEntry(action_type=AuditActionType.COMMAND_FAILED, command=command, result=result, risk_level=risk_level, user_approved=True, session_id=session_id))
            return result

    def _execute_action(self, command: ExecuteCommand) -> CommandResultData:
        a = command.action
        args = command.args

        if a == CommandAction.LIST_DIRECTORY:
            return CommandResultData(entries=self.transport.list_directory(args.path or "/ext"))
        if a == CommandAction.READ_FILE:
            if not args.path:
                raise ValueError("Path required")
            return CommandResultData(content=self.transport.read_file(args.path))
        if a == CommandAction.WRITE_FILE:
            if not args.path or args.content is None:
                raise ValueError("Path and content required")
            return CommandResultData(bytes_written=self.transport.write_file(args.path, args.content), message=f"Wrote: {args.path}")
        if a == CommandAction.CREATE_DIRECTORY:
            if not args.path:
                raise ValueError("Path required")
            self.transport.create_directory(args.path)
            return CommandResultData(message=f"Directory created: {args.path}")
        if a == CommandAction.DELETE:
            if not args.path:
                raise ValueError("Path required")
            self.transport.delete(args.path, args.recursive)
            return CommandResultData(message=f"Deleted: {args.path}")
        if a == CommandAction.MOVE:
            if not args.path or not args.destination_path:
                raise ValueError("Source and destination required")
            self.transport.move(args.path, args.destination_path)
            return CommandResultData(message=f"Moved: {args.path} -> {args.destination_path}")
        if a == CommandAction.COPY:
            if not args.path or not args.destination_path:
                raise ValueError("Source and destination required")
            self.transport.copy(args.path, args.destination_path)
            return CommandResultData(message=f"Copied: {args.path} -> {args.destination_path}")
        if a == CommandAction.RENAME:
            if not args.path or not args.new_name:
                raise ValueError("Path and new_name required")
            source_path = PurePosixPath(args.path)
            destination = str(source_path.parent / args.new_name)
            self.transport.move(args.path, destination)
            return CommandResultData(message=f"Renamed to: {args.new_name}")
        if a == CommandAction.GET_DEVICE_INFO:
            return CommandResultData(device_info=self.transport.get_device_info())
        if a == CommandAction.GET_STORAGE_INFO:
            return CommandResultData(storage_info=self.transport.get_storage_info())
        if a == CommandAction.EXECUTE_CLI:
            cli_command_text = args.command or args.content
            if not cli_command_text:
                raise ValueError("CLI command required")
            return CommandResultData(
                content=self.transport.execute_cli(cli_command_text),
                message=f"Executed CLI command: {cli_command_text}",
            )
        if a == CommandAction.SEARCH_FAPHUB:
            q = (args.command or "").strip()
            return CommandResultData(content=f"FapHub matches for '{q}':\n1. wifi_marauder\n2. evil_portal")
        if a == CommandAction.SEARCH_RESOURCES:
            q = (args.command or "").strip()
            return CommandResultData(content=f"Resources for '{q}':\n- Flipper-IRDB\n- awesome-flipper")
        if a == CommandAction.FORGE_PAYLOAD:
            prompt = args.prompt or args.command or ""
            return CommandResultData(content=f"[mock forge payload]\nPrompt: {prompt}")
        if a == CommandAction.REQUEST_PHOTO:
            return CommandResultData(content="[mock glasses photo capture]")
        if a in {
            CommandAction.LAUNCH_APP,
            CommandAction.SUBGHZ_TRANSMIT,
            CommandAction.IR_TRANSMIT,
            CommandAction.NFC_EMULATE,
            CommandAction.RFID_EMULATE,
            CommandAction.IBUTTON_EMULATE,
            CommandAction.BADUSB_EXECUTE,
            CommandAction.BLE_SPAM,
            CommandAction.LED_CONTROL,
            CommandAction.VIBRO_CONTROL,
            CommandAction.DOWNLOAD_RESOURCE,
            CommandAction.BROWSE_REPO,
            CommandAction.GITHUB_SEARCH,
            CommandAction.PUSH_ARTIFACT,
            CommandAction.INSTALL_FAPHUB_APP,
            CommandAction.LIST_VAULT,
            CommandAction.RUN_RUNBOOK,
        }:
            return CommandResultData(content=f"[mocked action] {a.value}", message="Mock mode")

        raise ValueError(f"Unsupported action: {a.value}")

    def _compute_diff(self, old: Optional[str], new: str) -> FileDiff:
        old_lines = [] if old is None else old.splitlines()
        new_lines = new.splitlines()
        diff_lines = list(difflib.unified_diff(old_lines, new_lines, fromfile="original", tofile="modified", lineterm=""))
        added = sum(1 for line in diff_lines if line.startswith("+") and not line.startswith("+++"))
        removed = sum(1 for line in diff_lines if line.startswith("-") and not line.startswith("---"))
        return FileDiff(old, new, added, removed, "\n".join(diff_lines))

    def _clear_expired_approvals(self) -> None:
        now = time.time()
        self.pending = {k: v for k, v in self.pending.items() if v.expires_at > now}

    def _audit(self, entry: AuditEntry) -> None:
        self.persistence.save_audit(entry)
