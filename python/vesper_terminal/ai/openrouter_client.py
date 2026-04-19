from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Callable

from vesper_terminal.domain.models import CommandAction, CommandArgs, ExecuteCommand


@dataclass
class AgentResponse:
    assistant_text: str
    command: ExecuteCommand | None = None


class OpenRouterClient:
    """OpenRouter client with tool-calling, retries, JSON repair, and model fallback."""

    TOOL_SCHEMA: dict[str, Any] = {
        "type": "function",
        "function": {
            "name": "execute_command",
            "description": "Execute a structured Flipper operation command.",
            "parameters": {
                "type": "object",
                "required": ["action", "args", "justification", "expected_effect"],
                "properties": {
                    "action": {"type": "string"},
                    "args": {"type": "object"},
                    "justification": {"type": "string"},
                    "expected_effect": {"type": "string"},
                },
            },
        },
    }

    SYSTEM_PROMPT = (
        "You are Vesper terminal operator. Use execute_command whenever a Flipper action is needed. "
        "Prefer safe read-only commands first, and include concise operator-facing language."
    )

    def __init__(
        self,
        api_key: str | None = None,
        models: list[str] | None = None,
        retries: int = 2,
        timeout_seconds: int = 45,
        requester: Callable[[str, dict[str, Any], int], dict[str, Any]] | None = None,
    ) -> None:
        self.api_key = api_key
        self.models = models or ["anthropic/claude-sonnet-4", "openai/gpt-4o-mini"]
        self.retries = max(0, retries)
        self.timeout_seconds = timeout_seconds
        self._requester = requester or self._default_requester

    def chat(self, user_text: str) -> AgentResponse:
        text = user_text.strip()
        if text.startswith("tool "):
            raw = text[len("tool "):]
            return AgentResponse(
                assistant_text="Executing requested tool...",
                command=self._parse_command_json(raw),
            )

        if not self.api_key:
            return AgentResponse(
                assistant_text=(
                    "OpenRouter API key not configured. "
                    "Set OPENROUTER_API_KEY in config.env, or use tool JSON mode."
                )
            )

        return self._chat_openrouter(text)

    def _chat_openrouter(self, user_text: str) -> AgentResponse:
        last_error: str | None = None
        for model in self.models:
            for _attempt in range(self.retries + 1):
                try:
                    payload = {
                        "model": model,
                        "messages": [
                            {"role": "system", "content": self.SYSTEM_PROMPT},
                            {"role": "user", "content": user_text},
                        ],
                        "tools": [self.TOOL_SCHEMA],
                        "tool_choice": "auto",
                    }
                    response = self._requester(self.api_key or "", payload, self.timeout_seconds)
                    return self._parse_model_response(response)
                except Exception as exc:  # noqa: BLE001 - fallback loop handles transient failures
                    last_error = str(exc)
                    continue

        return AgentResponse(
            assistant_text=(
                "Model request failed after retries/fallbacks. "
                f"Last error: {last_error or 'unknown error'}"
            )
        )

    def _parse_model_response(self, response: dict[str, Any]) -> AgentResponse:
        choices = response.get("choices") or []
        if not choices:
            raise ValueError("OpenRouter response missing choices")
        message = (choices[0] or {}).get("message") or {}

        tool_calls = message.get("tool_calls") or []
        if tool_calls:
            first_call = tool_calls[0] or {}
            fn = first_call.get("function") or {}
            arguments = fn.get("arguments") or "{}"
            return AgentResponse(
                assistant_text="Executing model-planned tool command...",
                command=self._parse_command_json(arguments),
            )

        content = message.get("content")
        if isinstance(content, list):
            parts = []
            for item in content:
                if isinstance(item, dict) and item.get("type") == "text":
                    parts.append(str(item.get("text", "")))
            content_text = "\n".join(p for p in parts if p)
        else:
            content_text = str(content or "")

        # If model returned inline JSON command without tool-call envelope, salvage it.
        if "action" in content_text and "args" in content_text and "{" in content_text:
            try:
                return AgentResponse(
                    assistant_text="Executing extracted inline command...",
                    command=self._parse_command_json(content_text),
                )
            except Exception:
                pass

        return AgentResponse(assistant_text=content_text or "No response content.")

    def _parse_command_json(self, raw: str) -> ExecuteCommand:
        payload = self._load_json_with_repair(raw)
        action = CommandAction(payload["action"])
        args = CommandArgs(**payload.get("args", {}))
        return ExecuteCommand(
            action=action,
            args=args,
            justification=payload.get("justification", "Tool-requested action"),
            expected_effect=payload.get("expected_effect", "Execute action"),
        )

    def _load_json_with_repair(self, raw: str) -> dict[str, Any]:
        text = raw.strip()
        text = text.replace("```json", "").replace("```", "").strip()

        for candidate in (text, self._extract_first_json_object(text), self._remove_trailing_commas(text)):
            if not candidate:
                continue
            try:
                loaded = json.loads(candidate)
                if isinstance(loaded, dict):
                    return loaded
            except json.JSONDecodeError:
                continue

        extracted = self._extract_first_json_object(text)
        if extracted:
            extracted = self._remove_trailing_commas(extracted)
            loaded = json.loads(extracted)
            if isinstance(loaded, dict):
                return loaded
        raise ValueError("Unable to parse command JSON")

    def _extract_first_json_object(self, text: str) -> str | None:
        start = text.find("{")
        if start < 0:
            return None
        depth = 0
        for idx in range(start, len(text)):
            char = text[idx]
            if char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    return text[start : idx + 1]
        return None

    def _remove_trailing_commas(self, text: str) -> str:
        return re.sub(r",(\s*[}\]])", r"\1", text)

    def _default_requester(
        self,
        api_key: str,
        payload: dict[str, Any],
        timeout_seconds: int,
    ) -> dict[str, Any]:
        request = urllib.request.Request(
            url="https://openrouter.ai/api/v1/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://github.com/gattaa/V3SP3R_Docker",
                "X-Title": "V3SP3R Terminal",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"HTTP {exc.code}: {body}") from exc
