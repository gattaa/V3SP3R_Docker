import tempfile
import unittest
import base64
from pathlib import Path

from vesper_terminal.data.persistence import SqlitePersistence
from vesper_terminal.domain.executor import CommandExecutor
from vesper_terminal.domain.models import CommandAction, CommandArgs, ExecuteCommand
from vesper_terminal.domain.permission import PermissionService
from vesper_terminal.domain.risk import RiskAssessor
from vesper_terminal.transport.mock_momentum import MockMomentumTransport


class ExecutorTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.persistence = SqlitePersistence(str(root / "test.sqlite3"))
        self.permissions = PermissionService()
        self.permissions.grant_path_permission("/ext", CommandAction.CREATE_DIRECTORY)
        self.permissions.grant_path_permission("/ext", CommandAction.WRITE_FILE)
        self.transport = MockMomentumTransport(str(root / "fs"))
        self.assessor = RiskAssessor(self.permissions)
        self.executor = CommandExecutor(self.transport, self.assessor, self.permissions, self.persistence)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_medium_requires_confirmation_when_not_autoapproved(self) -> None:
        cmd = ExecuteCommand(CommandAction.FORGE_PAYLOAD, CommandArgs(prompt="make badusb"), "", "")
        result = self.executor.execute(cmd, "s1")
        self.assertTrue(result.requires_confirmation)
        self.assertIsNotNone(result.pending_approval_id)

    def test_approval_timeout_for_missing_id(self) -> None:
        result = self.executor.approve("missing", "s2")
        self.assertFalse(result.success)
        self.assertIn("not found or expired", result.error)

    def test_launch_app_maps_to_loader_open_cli(self) -> None:
        cmd = ExecuteCommand(
            CommandAction.LAUNCH_APP,
            CommandArgs(app_name="Infrared"),
            "",
            "",
        )
        result = self.executor.execute(cmd, "s3")
        self.assertTrue(result.requires_confirmation)
        approved = self.executor.approve(result.pending_approval_id, "s3")
        self.assertTrue(approved.success)
        self.assertIn("app launched", approved.data.content.lower())

    def test_push_artifact_rejects_non_ext_path(self) -> None:
        encoded = base64.b64encode(b"payload").decode("ascii")
        cmd = ExecuteCommand(
            CommandAction.PUSH_ARTIFACT,
            CommandArgs(path="/int/evil.bin", artifact_data=encoded),
            "",
            "",
        )
        result = self.executor.execute(cmd, "s4")
        self.assertFalse(result.success)
        self.assertIn("Blocked", result.error)

    def test_download_resource_rejects_unapproved_domain(self) -> None:
        cmd = ExecuteCommand(
            CommandAction.DOWNLOAD_RESOURCE,
            CommandArgs(download_url="https://example.com/file.ir", path="/ext/infrared/file.ir"),
            "",
            "",
        )
        result = self.executor.execute(cmd, "s5")
        self.assertTrue(result.requires_confirmation)
        approved = self.executor.approve(result.pending_approval_id, "s5")
        self.assertFalse(approved.success)
        self.assertIn("approved domain", approved.error)

    def test_push_artifact_rejects_invalid_base64(self) -> None:
        cmd = ExecuteCommand(
            CommandAction.PUSH_ARTIFACT,
            CommandArgs(path="/ext/invalid.bin", artifact_data="%%%bad%%%"),
            "",
            "",
        )
        result = self.executor.execute(cmd, "s6")
        self.assertTrue(result.requires_confirmation)
        approved = self.executor.approve(result.pending_approval_id, "s6")
        self.assertFalse(approved.success)
        self.assertIn("Invalid base64", approved.error)

    def test_push_artifact_rejects_oversized_payload(self) -> None:
        raw = b"a" * (self.executor.MAX_ARTIFACT_BYTES + 1)
        encoded = base64.b64encode(raw).decode("ascii")
        cmd = ExecuteCommand(
            CommandAction.PUSH_ARTIFACT,
            CommandArgs(path="/ext/oversized.bin", artifact_data=encoded),
            "",
            "",
        )
        result = self.executor.execute(cmd, "s7")
        self.assertTrue(result.requires_confirmation)
        approved = self.executor.approve(result.pending_approval_id, "s7")
        self.assertFalse(approved.success)
        self.assertIn("size limit", approved.error)

    def test_audit_entries_are_persisted(self) -> None:
        cmd = ExecuteCommand(
            CommandAction.LIST_DIRECTORY,
            CommandArgs(path="/ext"),
            "",
            "",
        )
        result = self.executor.execute(cmd, "audit-session")
        self.assertTrue(result.success)

        with self.persistence._conn() as conn:
            count = conn.execute(
                "SELECT COUNT(*) FROM audit_entries WHERE session_id = ?",
                ("audit-session",),
            ).fetchone()[0]
        self.assertGreaterEqual(count, 2)  # command_received + command_executed


if __name__ == "__main__":
    unittest.main()
