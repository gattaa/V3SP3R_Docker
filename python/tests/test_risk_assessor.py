import unittest

from vesper_terminal.domain.models import CommandAction, CommandArgs, ExecuteCommand, RiskLevel
from vesper_terminal.domain.permission import PermissionService
from vesper_terminal.domain.risk import RiskAssessor


class RiskAssessorTest(unittest.TestCase):
    def setUp(self) -> None:
        self.permissions = PermissionService()
        self.assessor = RiskAssessor(self.permissions)

    def test_list_directory_is_low(self) -> None:
        cmd = ExecuteCommand(CommandAction.LIST_DIRECTORY, CommandArgs(path="/ext/subghz"), "", "")
        self.assertEqual(RiskLevel.LOW, self.assessor.assess(cmd).level)

    def test_write_in_scope_is_medium(self) -> None:
        self.permissions.grant_path_permission("/ext", CommandAction.WRITE_FILE)
        cmd = ExecuteCommand(CommandAction.WRITE_FILE, CommandArgs(path="/ext/a.txt", content="x"), "", "")
        assessment = self.assessor.assess(cmd)
        self.assertEqual(RiskLevel.MEDIUM, assessment.level)
        self.assertTrue(assessment.requires_diff)

    def test_protected_path_blocked(self) -> None:
        cmd = ExecuteCommand(CommandAction.READ_FILE, CommandArgs(path="/int/secret.txt"), "", "")
        self.assertEqual(RiskLevel.BLOCKED, self.assessor.assess(cmd).level)


if __name__ == "__main__":
    unittest.main()
