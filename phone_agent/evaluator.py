"""Deterministic evaluation for BetterGLM replay runs."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class EvaluationCheck:
    """One scored assertion in an evaluation report."""

    name: str
    status: str
    points: int
    max_points: int
    detail: str
    evidence: str | None = None
    required: bool = True


@dataclass
class EvaluationReport:
    """Result of evaluating one replay directory."""

    status: str
    score: int
    max_score: int
    summary: str
    checks: list[EvaluationCheck] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def evaluate_replay(
    replay_path: str | Path,
    criteria: dict[str, Any] | None,
) -> EvaluationReport:
    """Evaluate a replay directory using deterministic success criteria."""

    run_dir = Path(replay_path)
    metadata = _load_json(run_dir / "metadata.json", default={})
    steps = _load_json(run_dir / "steps.json", default=[])
    criteria = criteria or {}

    checks: list[EvaluationCheck] = []
    min_score = int(criteria.get("min_score", 80))

    if criteria.get("require_finished", True):
        completed = metadata.get("status") == "completed"
        finished_step = bool(steps and steps[-1].get("finished"))
        checks.append(
            _check(
                "run_completed",
                completed and finished_step,
                20,
                "Replay finished with a completed status.",
                f"metadata.status={metadata.get('status')}, final.finished={finished_step}",
            )
        )

    if not criteria.get("allow_errors", False):
        errors = [str(step.get("error")) for step in steps if step.get("error")]
        checks.append(
            _check(
                "no_step_errors",
                not errors,
                15,
                "No recorded step errors.",
                "; ".join(errors[:3]) if errors else "No step errors found.",
            )
        )

    max_steps = criteria.get("max_steps")
    if max_steps is not None:
        max_steps = int(max_steps)
        checks.append(
            _check(
                "max_steps",
                len(steps) <= max_steps,
                15,
                f"Run finished within {max_steps} steps.",
                f"actual_steps={len(steps)}",
            )
        )

    target_app = criteria.get("target_app")
    if target_app:
        final_app = str(steps[-1].get("current_app", "")) if steps else ""
        checks.append(
            _check(
                "target_app",
                _target_app_matches(str(target_app), final_app),
                15,
                f"Final app should be {target_app}.",
                f"final_app={final_app or 'unknown'}",
            )
        )

    corpus = _build_text_corpus(metadata, steps)

    must_contain = [str(value) for value in criteria.get("must_contain_text", [])]
    if must_contain:
        passed_terms = [term for term in must_contain if term.lower() in corpus.lower()]
        missing_terms = [term for term in must_contain if term not in passed_terms]
        checks.append(
            _check(
                "must_contain_text",
                not missing_terms,
                25,
                "Replay evidence contains all required text.",
                (
                    f"matched={', '.join(passed_terms) or 'none'}; "
                    f"missing={', '.join(missing_terms) or 'none'}"
                ),
            )
        )

    any_contain = [str(value) for value in criteria.get("any_contain_text", [])]
    if any_contain:
        matched = [term for term in any_contain if term.lower() in corpus.lower()]
        checks.append(
            _check(
                "any_contain_text",
                bool(matched),
                10,
                "Replay evidence contains at least one optional text signal.",
                f"matched={', '.join(matched) or 'none'}",
                required=False,
            )
        )

    if not checks:
        return EvaluationReport(
            status="skipped",
            score=0,
            max_score=0,
            summary="No success criteria were configured.",
            checks=[],
        )

    score = sum(check.points for check in checks)
    max_score = sum(check.max_points for check in checks)
    normalized = round(score * 100 / max_score) if max_score else 0
    required_failed = [
        check.name
        for check in checks
        if check.required and check.status != "passed"
    ]
    status = "passed" if normalized >= min_score and not required_failed else "failed"
    summary = (
        f"{status.upper()} with score {normalized}/100"
        if status != "skipped"
        else "No evaluation was run."
    )

    return EvaluationReport(
        status=status,
        score=normalized,
        max_score=100,
        summary=summary,
        checks=checks,
    )


def save_evaluation_report(
    replay_path: str | Path, report: EvaluationReport
) -> dict[str, Any]:
    """Persist evaluation.json and attach the report to metadata.json."""

    run_dir = Path(replay_path)
    payload = report.to_dict()
    (run_dir / "evaluation.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    metadata_path = run_dir / "metadata.json"
    metadata = _load_json(metadata_path, default={})
    if isinstance(metadata, dict):
        metadata["evaluation"] = payload
        metadata_path.write_text(
            json.dumps(metadata, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    return payload


def load_evaluation_report(replay_path: str | Path) -> dict[str, Any] | None:
    """Load a previously saved evaluation report if it exists."""

    evaluation_path = Path(replay_path) / "evaluation.json"
    if not evaluation_path.exists():
        return None
    return _load_json(evaluation_path, default=None)


def format_evaluation_report(report: EvaluationReport) -> str:
    """Format an evaluation report for CLI output."""

    lines = [
        "=" * 50,
        "BetterGLM Evaluation",
        "=" * 50,
        f"Status: {report.status}",
        f"Score: {report.score}/{report.max_score}",
        f"Summary: {report.summary}",
        "-" * 50,
    ]
    for check in report.checks:
        marker = "OK" if check.status == "passed" else "FAIL"
        lines.append(
            f"[{marker}] {check.name}: {check.points}/{check.max_points} - {check.detail}"
        )
        if check.evidence:
            lines.append(f"      Evidence: {check.evidence}")
    lines.append("=" * 50)
    return "\n".join(lines)


def _check(
    name: str,
    passed: bool,
    points: int,
    detail: str,
    evidence: str | None = None,
    required: bool = True,
) -> EvaluationCheck:
    return EvaluationCheck(
        name=name,
        status="passed" if passed else "failed",
        points=points if passed else 0,
        max_points=points,
        detail=detail,
        evidence=evidence,
        required=required,
    )


def _load_json(path: Path, default: Any) -> Any:
    try:
        if not path.exists():
            return default
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return default


def _build_text_corpus(metadata: dict[str, Any], steps: list[dict[str, Any]]) -> str:
    chunks: list[str] = []
    for key in ("result",):
        if metadata.get(key):
            chunks.append(str(metadata[key]))

    for step in steps:
        for key in (
            "current_app",
            "screen_info",
            "message",
            "error",
        ):
            value = step.get(key)
            if value:
                chunks.append(str(value))
        for key in ("parsed_action", "action_result"):
            value = step.get(key)
            if value:
                chunks.append(json.dumps(value, ensure_ascii=False))

    return "\n".join(chunks)


_TARGET_APP_ALIASES = (
    {"settings", "设置", "系统设置", "preferences"},
    {"safari", "mobile safari", "浏览器"},
    {"notes", "备忘录"},
    {"bilibili", "哔哩哔哩", "哔哩", "b站"},
    {"amap", "高德", "高德地图"},
    {"luckin coffee", "luckincoffee", "luckin", "瑞幸", "瑞幸咖啡"},
)


def _target_app_matches(expected: str, actual: str) -> bool:
    expected_norm = _normalize_text(expected)
    actual_norm = _normalize_text(actual)
    if not expected_norm or not actual_norm:
        return False
    if expected_norm in actual_norm or actual_norm in expected_norm:
        return True

    for alias_group in _TARGET_APP_ALIASES:
        normalized_group = {_normalize_text(value) for value in alias_group}
        if expected_norm in normalized_group and actual_norm in normalized_group:
            return True
    return False


def _normalize_text(value: str) -> str:
    return " ".join(str(value).strip().lower().split())
