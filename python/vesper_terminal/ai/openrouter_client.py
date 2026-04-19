from __future__ import annotations

import json
from dataclasses import dataclass

from vesper_terminal.domain.models import CommandAction, CommandArgs, ExecuteCommand


@dataclass
class AgentResponse:
    assistant_text: str
    command: ExecuteCommand | None = None


class OpenRouterClient:
    """Minimal migration client shim."""

    def chat(self, user_text: str) -> AgentResponse:
        text = user_text.strip()
        if text.startswith("tool "):
            raw = text[len("tool "):]
            payload = json.loads(raw)
            action = CommandAction(payload["action"])
            args = CommandArgs(**payload.get("args", {}))
            cmd = ExecuteCommand(
                action=action,
                args=args,
                justification=payload.get("justification", "User requested tool execution"),
                expected_effect=payload.get("expected_effect", "Execute action"),
            )
            return AgentResponse(assistant_text="Executing requested tool...", command=cmd)

        return AgentResponse(
            assistant_text=(
                "I can execute Flipper actions when you send a tool JSON command. "
                "Example: tool {\"action\":\"list_directory\",\"args\":{\"path\":\"/ext\"}}"
            )
        )
