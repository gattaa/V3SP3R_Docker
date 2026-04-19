from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from time import time
from typing import Optional
from uuid import uuid4


class RiskLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    BLOCKED = "BLOCKED"


class CommandAction(str, Enum):
    LIST_DIRECTORY = "list_directory"
    READ_FILE = "read_file"
    WRITE_FILE = "write_file"
    CREATE_DIRECTORY = "create_directory"
    DELETE = "delete"
    MOVE = "move"
    RENAME = "rename"
    COPY = "copy"
    GET_DEVICE_INFO = "get_device_info"
    GET_STORAGE_INFO = "get_storage_info"
    SEARCH_FAPHUB = "search_faphub"
    INSTALL_FAPHUB_APP = "install_faphub_app"
    PUSH_ARTIFACT = "push_artifact"
    EXECUTE_CLI = "execute_cli"
    FORGE_PAYLOAD = "forge_payload"
    SEARCH_RESOURCES = "search_resources"
    LIST_VAULT = "list_vault"
    RUN_RUNBOOK = "run_runbook"
    LAUNCH_APP = "launch_app"
    SUBGHZ_TRANSMIT = "subghz_transmit"
    IR_TRANSMIT = "ir_transmit"
    NFC_EMULATE = "nfc_emulate"
    RFID_EMULATE = "rfid_emulate"
    IBUTTON_EMULATE = "ibutton_emulate"
    BADUSB_EXECUTE = "badusb_execute"
    BLE_SPAM = "ble_spam"
    LED_CONTROL = "led_control"
    VIBRO_CONTROL = "vibro_control"
    BROWSE_REPO = "browse_repo"
    DOWNLOAD_RESOURCE = "download_resource"
    GITHUB_SEARCH = "github_search"
    REQUEST_PHOTO = "request_photo"


@dataclass
class CommandArgs:
    command: Optional[str] = None
    path: Optional[str] = None
    destination_path: Optional[str] = None
    content: Optional[str] = None
    new_name: Optional[str] = None
    recursive: bool = False
    artifact_type: Optional[str] = None
    artifact_data: Optional[str] = None
    prompt: Optional[str] = None
    resource_type: Optional[str] = None
    runbook_id: Optional[str] = None
    payload_type: Optional[str] = None
    filter: Optional[str] = None
    app_name: Optional[str] = None
    app_args: Optional[str] = None
    frequency: Optional[int] = None
    protocol: Optional[str] = None
    address: Optional[str] = None
    signal_name: Optional[str] = None
    enabled: Optional[bool] = None
    red: Optional[int] = None
    green: Optional[int] = None
    blue: Optional[int] = None
    repo_id: Optional[str] = None
    sub_path: Optional[str] = None
    download_url: Optional[str] = None
    search_scope: Optional[str] = None
    photo_prompt: Optional[str] = None


@dataclass
class ExecuteCommand:
    action: CommandAction
    args: CommandArgs
    justification: str
    expected_effect: str


@dataclass
class FileDiff:
    original_content: Optional[str]
    new_content: str
    lines_added: int
    lines_removed: int
    unified_diff: str


@dataclass
class CommandResultData:
    entries: Optional[list[dict]] = None
    content: Optional[str] = None
    bytes_written: Optional[int] = None
    device_info: Optional[dict] = None
    storage_info: Optional[dict] = None
    diff: Optional[FileDiff] = None
    message: Optional[str] = None


@dataclass
class CommandResult:
    success: bool
    action: Optional[CommandAction]
    data: Optional[CommandResultData] = None
    error: Optional[str] = None
    execution_time_ms: int = 0
    requires_confirmation: bool = False
    pending_approval_id: Optional[str] = None


@dataclass
class RiskAssessment:
    level: RiskLevel
    reason: str
    affected_paths: list[str]
    requires_diff: bool
    requires_confirmation: bool
    blocked_reason: Optional[str] = None


@dataclass
class PendingApproval:
    command: ExecuteCommand
    risk_assessment: RiskAssessment
    created_at: float = field(default_factory=lambda: time())
    id: str = field(default_factory=lambda: str(uuid4()))
    expires_at: float = field(default_factory=lambda: time() + 120)
    diff: Optional[FileDiff] = None


class AuditActionType(str, Enum):
    COMMAND_RECEIVED = "command_received"
    COMMAND_EXECUTED = "command_executed"
    COMMAND_FAILED = "command_failed"
    COMMAND_BLOCKED = "command_blocked"
    APPROVAL_REQUESTED = "approval_requested"
    APPROVAL_GRANTED = "approval_granted"
    APPROVAL_DENIED = "approval_denied"
    APPROVAL_TIMEOUT = "approval_timeout"
    SESSION_STARTED = "session_started"
    SESSION_ENDED = "session_ended"


@dataclass
class AuditEntry:
    action_type: AuditActionType
    session_id: str
    command: Optional[ExecuteCommand] = None
    result: Optional[CommandResult] = None
    risk_level: Optional[RiskLevel] = None
    user_approved: Optional[bool] = None
    metadata: dict[str, str] = field(default_factory=dict)
    id: str = field(default_factory=lambda: str(uuid4()))
    timestamp: int = field(default_factory=lambda: int(time() * 1000))
