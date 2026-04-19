from __future__ import annotations

from pathlib import Path

from vesper_terminal.ai.agent import VesperAgent
from vesper_terminal.ai.openrouter_client import OpenRouterClient
from vesper_terminal.data.config_store import PlaintextConfigStore
from vesper_terminal.data.persistence import SqlitePersistence
from vesper_terminal.domain.executor import CommandExecutor
from vesper_terminal.domain.models import CommandAction
from vesper_terminal.domain.permission import PermissionService
from vesper_terminal.domain.risk import RiskAssessor
from vesper_terminal.transport.factory import create_transport

APPROVAL_PROMPT = "Type YES to approve, or no/reject to deny."


def build_agent(data_dir: str) -> tuple[VesperAgent, dict]:
    base = Path(data_dir)
    base.mkdir(parents=True, exist_ok=True)

    config = PlaintextConfigStore(str(base / "config.env"))
    persistence = SqlitePersistence(str(base / "vesper.sqlite3"))

    permission = PermissionService()
    permission.grant_path_permission("/ext", action=CommandAction.WRITE_FILE)
    permission.grant_path_permission("/ext", action=CommandAction.CREATE_DIRECTORY)

    transport, profile = create_transport(config, base)
    risk = RiskAssessor(permission)
    executor = CommandExecutor(
        transport=transport,
        risk_assessor=risk,
        permission_service=permission,
        persistence=persistence,
        auto_approve_medium=config.get("AUTO_APPROVE_MEDIUM", "false").lower() == "true",
        auto_approve_high=config.get("AUTO_APPROVE_HIGH", "false").lower() == "true",
    )
    model_list_raw = config.get(
        "OPENROUTER_MODELS",
        "anthropic/claude-sonnet-4,openai/gpt-4o-mini",
    )
    models = [
        model.strip()
        for model in (model_list_raw or "").split(",")
        if model.strip()
    ]
    client = OpenRouterClient(
        api_key=config.get("OPENROUTER_API_KEY"),
        models=models,
        retries=int(config.get("OPENROUTER_RETRIES", "2") or "2"),
    )
    agent = VesperAgent(client=client, executor=executor, persistence=persistence)
    return agent, profile


def run_cli() -> None:
    agent, profile = build_agent(str(Path.home() / ".vesper_terminal"))
    print("V3SP3R Terminal (Python migration)")
    print("Commands: new | retry | history | quit")
    print("Tool mode: tool {\"action\":\"list_directory\",\"args\":{\"path\":\"/ext\"}}")
    print(
        "Transport:",
        profile.get("transport_mode", "unknown"),
        f"(firmware={profile.get('firmware_family', 'unknown')})",
    )
    if profile.get("mock_mode"):
        print("⚠ mock mode enabled for transport-dependent actions.")
    if not profile.get("supports_cli", False):
        reason = profile.get("unsupported_reason", "CLI unavailable")
        print(f"⚠ transport limitations: {reason}")

    pending_approval: str | None = None

    while True:
        raw = input("vesper> ").strip()
        if raw == "":
            continue

        if pending_approval:
            if raw.lower() == "yes":
                result = agent.executor.approve(pending_approval, agent.session_id)
                print("✅ approved" if result.success else f"❌ {result.error}")
                pending_approval = None
                continue
            if raw.lower() in {"no", "reject"}:
                result = agent.executor.reject(pending_approval, agent.session_id)
                print("🚫 rejected")
                pending_approval = None
                continue
            print(APPROVAL_PROMPT)
            continue

        if raw == "quit":
            break
        if raw == "new":
            sid = agent.new_session()
            print(f"Started new session: {sid}")
            continue
        if raw == "retry":
            text, pending = agent.retry_last()
            print(text)
            if pending:
                pending_approval = pending
                print(APPROVAL_PROMPT)
            continue
        if raw == "history":
            for role, content in agent.persistence.history(agent.session_id, limit=20):
                print(f"[{role}] {content}")
            continue

        text, pending = agent.send_message(raw)
        print(text)
        if pending:
            pending_approval = pending
            print(APPROVAL_PROMPT)


if __name__ == "__main__":
    run_cli()
