"""CLI input helpers."""

from __future__ import annotations

from typing import Any


_PROMPT_HISTORY: Any | None = None


def read_task_input(prompt_text: str = "Enter your task: ") -> str:
    """Read a task with better editing support when prompt_toolkit is installed."""

    global _PROMPT_HISTORY

    try:
        from prompt_toolkit import prompt
        from prompt_toolkit.history import InMemoryHistory

        if _PROMPT_HISTORY is None:
            _PROMPT_HISTORY = InMemoryHistory()

        return prompt(prompt_text, history=_PROMPT_HISTORY)
    except ImportError:
        try:
            import readline  # noqa: F401
        except ImportError:
            pass

        return input(prompt_text)
