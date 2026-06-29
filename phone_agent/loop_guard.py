"""Guardrails for agent execution loops."""

from __future__ import annotations

import json
from typing import Any


class AgentLoopGuard:
    """Detect terminal action failures and repeated-action loops."""

    def __init__(self, repeat_threshold: int = 3):
        self.repeat_threshold = repeat_threshold
        self._recent_action_signatures: list[str] = []

    def reset(self) -> None:
        self._recent_action_signatures = []

    def repeated_action_message(self, action: dict[str, Any]) -> str | None:
        """Return a terminal message when the same action repeats too often."""

        if action.get("_metadata") == "finish":
            self.reset()
            return None

        signature = json.dumps(action, ensure_ascii=False, sort_keys=True)
        self._recent_action_signatures.append(signature)
        self._recent_action_signatures = self._recent_action_signatures[
            -self.repeat_threshold :
        ]

        if (
            len(self._recent_action_signatures) == self.repeat_threshold
            and len(set(self._recent_action_signatures)) == 1
        ):
            action_name = action.get("action") or action.get("_metadata") or "unknown"
            return (
                "Repeated action loop detected: "
                f"{action_name}. Stopping before wasting more steps."
            )
        return None

    @staticmethod
    def terminal_failure_status(success: bool, message: str | None) -> str | None:
        """Return a replay status for failures that should stop the agent."""

        if success:
            return None

        text = (message or "").lower()
        if "app not found" in text or "not installed" in text:
            return "failed"
        return None
