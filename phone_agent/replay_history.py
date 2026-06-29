"""Replay history aggregation for BetterGLM dashboards."""

from __future__ import annotations

import json
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any


def build_replay_history(root_dir: str | Path, limit: int = 50) -> dict[str, Any]:
    """Scan replay runs and return summary metrics plus recent run rows."""

    root = Path(root_dir)
    if not root.exists():
        return _empty_history()

    runs = [_build_run_row(run_dir, root) for run_dir in _iter_run_dirs(root)]
    runs = [run for run in runs if run]
    runs.sort(key=lambda run: run.get("started_at") or "", reverse=True)
    runs = runs[:limit]

    return {
        "summary": _build_summary(runs),
        "runs": runs,
    }


def classify_failure(
    metadata: dict[str, Any],
    steps: list[dict[str, Any]],
    evaluation: dict[str, Any] | None = None,
) -> str | None:
    """Classify a replay failure into a stable, dashboard-friendly type."""

    evaluation = evaluation or metadata.get("evaluation")
    if evaluation and evaluation.get("status") == "passed":
        return None

    status = str(metadata.get("status") or "")
    if status == "completed" and not evaluation:
        return None
    if status == "max_steps":
        return "max_steps"

    for step in steps:
        text = " ".join(
            str(step.get(key) or "")
            for key in ("error", "message", "raw_action", "current_app")
        ).lower()
        if not text.strip():
            continue
        if "parse" in text or "failed to parse" in text:
            return "model_parse_error"
        if "wda" in text or "webdriveragent" in text or "connection" in text:
            return "wda_error"
        if "app not found" in text or "not installed" in text:
            return "app_not_installed"
        if "coordinate" in text or ("tap" in text and "failed" in text):
            return "coordinate_error"
        if "sensitive" in text or "cancelled" in text:
            return "sensitive_action_blocked"

    if evaluation:
        failed = [
            check.get("name")
            for check in evaluation.get("checks", [])
            if check.get("status") != "passed"
        ]
        if "max_steps" in failed:
            return "max_steps"
        if "target_app" in failed:
            return "target_app_mismatch"
        if "must_contain_text" in failed or "any_contain_text" in failed:
            return "target_text_missing"
        if "run_completed" in failed:
            return "not_completed"
        if "no_step_errors" in failed:
            return "step_error"

    if status and status != "completed":
        return status
    if evaluation and evaluation.get("status") == "failed":
        return "evaluation_failed"
    return None


def _iter_run_dirs(root: Path) -> list[Path]:
    return [
        path
        for path in root.iterdir()
        if path.is_dir() and (path / "metadata.json").exists()
    ]


def _build_run_row(run_dir: Path, root: Path) -> dict[str, Any] | None:
    metadata = _load_json(run_dir / "metadata.json", {})
    if not isinstance(metadata, dict):
        return None

    steps = _load_json(run_dir / "steps.json", [])
    if not isinstance(steps, list):
        steps = []

    evaluation = _load_json(run_dir / "evaluation.json", None)
    if not evaluation and isinstance(metadata.get("evaluation"), dict):
        evaluation = metadata["evaluation"]

    started_at = metadata.get("started_at")
    finished_at = metadata.get("finished_at")
    duration = _duration_seconds(started_at, finished_at)
    evaluation_status = evaluation.get("status") if isinstance(evaluation, dict) else None
    status = evaluation_status or metadata.get("status") or "unknown"
    score = evaluation.get("score") if isinstance(evaluation, dict) else None
    failure_type = classify_failure(metadata, steps, evaluation)
    relative = run_dir.relative_to(root)

    return {
        "run_id": metadata.get("run_id") or run_dir.name,
        "task": metadata.get("task") or "",
        "status": status,
        "metadata_status": metadata.get("status"),
        "score": score,
        "steps": len(steps),
        "duration_seconds": duration,
        "started_at": started_at,
        "finished_at": finished_at,
        "failure_type": failure_type,
        "current_app": steps[-1].get("current_app") if steps else None,
        "path": str(run_dir),
        "index_url": f"/replays/{relative.as_posix()}/index.html",
    }


def _build_summary(runs: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(runs)
    evaluated = sum(1 for run in runs if run.get("score") is not None)
    passed = sum(1 for run in runs if run.get("status") == "passed")
    failed = sum(
        1
        for run in runs
        if run.get("status") in ("failed", "max_steps") or run.get("failure_type")
    )
    completed_unscored = sum(
        1
        for run in runs
        if run.get("status") == "completed" and run.get("score") is None
    )
    scores = [
        run["score"]
        for run in runs
        if isinstance(run.get("score"), (int, float))
    ]
    steps = [run["steps"] for run in runs if isinstance(run.get("steps"), int)]
    durations = [
        run["duration_seconds"]
        for run in runs
        if isinstance(run.get("duration_seconds"), (int, float))
    ]
    failures = Counter(run.get("failure_type") for run in runs if run.get("failure_type"))

    return {
        "total": total,
        "evaluated": evaluated,
        "passed": passed,
        "failed": failed,
        "completed_unscored": completed_unscored,
        "success_rate": round(passed * 100 / evaluated) if evaluated else 0,
        "avg_score": round(sum(scores) / len(scores), 1) if scores else None,
        "avg_steps": round(sum(steps) / len(steps), 1) if steps else None,
        "avg_duration_seconds": round(sum(durations) / len(durations), 1)
        if durations
        else None,
        "failure_counts": dict(failures),
    }


def _duration_seconds(started_at: str | None, finished_at: str | None) -> int | None:
    if not started_at or not finished_at:
        return None
    try:
        started = datetime.fromisoformat(started_at)
        finished = datetime.fromisoformat(finished_at)
    except ValueError:
        return None
    return max(0, round((finished - started).total_seconds()))


def _load_json(path: Path, default: Any) -> Any:
    try:
        if not path.exists():
            return default
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return default


def _empty_history() -> dict[str, Any]:
    return {
        "summary": {
            "total": 0,
            "evaluated": 0,
            "passed": 0,
            "failed": 0,
            "completed_unscored": 0,
            "success_rate": 0,
            "avg_score": None,
            "avg_steps": None,
            "avg_duration_seconds": None,
            "failure_counts": {},
        },
        "runs": [],
    }
