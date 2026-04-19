import tempfile
import unittest
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

    def test_audit_entries_are_persisted(self) -> None:
        cmd = ExecuteCommand(
            CommandAction.LIST_DIRECTORY,
            CommandArgs(path="/ext"),
            "",
            "",
        )
        result = self.executor.execute(cmd, "audit-session")
        self.assertTrue(result.success)

        with self.persistence._conn() as conn:  # noqa: SLF001 - acceptable for test inspection
            count = conn.execute(
                "SELECT COUNT(*) FROM audit_entries WHERE session_id = ?",
                ("audit-session",),
            ).fetchone()[0]
        self.assertGreaterEqual(count, 2)  # command_received + command_executed


if __name__ == "__main__":
    unittest.main()
