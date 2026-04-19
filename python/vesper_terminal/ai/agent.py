from __future__ import annotations

from uuid import uuid4

from vesper_terminal.ai.openrouter_client import OpenRouterClient
from vesper_terminal.data.persistence import SqlitePersistence
from vesper_terminal.domain.executor import CommandExecutor


class VesperAgent:
    def __init__(self, client: OpenRouterClient, executor: CommandExecutor, persistence: SqlitePersistence) -> None:
        self.client = client
        self.executor = executor
        self.persistence = persistence
        self.session_id = str(uuid4())
        self.last_user_message: str | None = None

    def new_session(self) -> str:
        self.session_id = str(uuid4())
        self.last_user_message = None
        return self.session_id

    def send_message(self, user_text: str) -> tuple[str, str | None]:
        self.last_user_message = user_text
        self.persistence.save_chat(self.session_id, "user", user_text)

        response = self.client.chat(user_text)
        assistant_text = response.assistant_text
        pending_id = None

        if response.command:
            result = self.executor.execute(response.command, self.session_id)
            if result.requires_confirmation:
                pending_id = result.pending_approval_id
                approval_message = (
                    result.data.message
                    if result.data and result.data.message
                    else "Approval required"
                )
                assistant_text = (
                    f"{approval_message}\nPending approval id: {pending_id}"
                )
                if result.data and result.data.diff:
                    assistant_text += "\n\nDiff preview:\n" + result.data.diff.unified_diff
            elif result.success:
                if result.data and result.data.content:
                    rendered = result.data.content
                elif result.data and result.data.message:
                    rendered = result.data.message
                else:
                    rendered = "Done"
                assistant_text = f"✅ {rendered}"
            else:
                assistant_text = f"❌ {result.error}"

        self.persistence.save_chat(self.session_id, "assistant", assistant_text)
        return assistant_text, pending_id

    def retry_last(self) -> tuple[str, str | None]:
        if not self.last_user_message:
            return "No previous message to retry.", None
        return self.send_message(self.last_user_message)
