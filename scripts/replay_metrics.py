#!/usr/bin/env python3
"""Generate portfolio metrics from BetterGLM replay artifacts."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime
from pathlib import Path
from statistics import mean
from typing import Any

from phone_agent.replay_history import classify_failure
from phone_agent.task_templates import filter_task_templates, load_task_templates


TOUCH_ACTIONS = {"Tap", "Double Tap", "Long Press", "Swipe"}
LOW_RISK_TERMS = ("不要", "不许", "禁止", "不要下单", "不要支付", "不要付款")


def main() -> None:
    args = parse_args()
    metrics = build_metrics(
        run_roots=[Path(path) for path in args.runs],
        templates_file=args.templates_file,
        limit=args.limit,
        include_running=args.include_running,
    )

    if args.json_output:
        json_path = Path(args.json_output)
        json_path.parent.mkdir(parents=True, exist_ok=True)
        json_path.write_text(
            json.dumps(metrics, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    markdown = render_markdown(metrics)
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(markdown, encoding="utf-8")
    else:
        print(markdown)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Summarize replay quality, artifact, and coordinate metrics."
    )
    parser.add_argument(
        "--runs",
        action="append",
        default=None,
        help="Replay root to scan. Can be repeated. Default: runs",
    )
    parser.add_argument(
        "--templates-file",
        default=None,
        help="Optional custom task templates JSON file.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=200,
        help="Maximum recent runs to include.",
    )
    parser.add_argument(
        "--include-running",
        action="store_true",
        help="Include replay runs whose metadata status is still running.",
    )
    parser.add_argument(
        "--output",
        help="Write a Markdown report to this path instead of stdout.",
    )
    parser.add_argument(
        "--json-output",
        help="Write raw metrics JSON to this path.",
    )
    args = parser.parse_args()
    if args.runs is None:
        args.runs = ["runs"]
    return args


def build_metrics(
    run_roots: list[Path],
    templates_file: str | None = None,
    limit: int = 200,
    include_running: bool = False,
) -> dict[str, Any]:
    discovered_runs = discover_runs(run_roots)
    running_runs = [run for run in discovered_runs if run.get("status") == "running"]
    runs = (
        discovered_runs
        if include_running
        else [
            run
            for run in discovered_runs
            if run.get("status") != "running"
        ]
    )
    runs.sort(key=lambda run: run.get("started_at") or "", reverse=True)
    runs = runs[:limit]

    templates = load_task_templates(templates_file)
    ios_templates = filter_task_templates(templates, "ios")
    public_runs = [strip_run_details(run) for run in runs]

    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "run_roots": [str(path) for path in run_roots],
        "excluded_running_runs": 0 if include_running else len(running_runs),
        "template_metrics": build_template_metrics(ios_templates),
        "quality_metrics": build_quality_metrics(runs),
        "artifact_metrics": build_artifact_metrics(runs),
        "coordinate_metrics": build_coordinate_metrics(runs),
        "runs": public_runs,
    }


def discover_runs(run_roots: list[Path]) -> list[dict[str, Any]]:
    seen: set[Path] = set()
    runs: list[dict[str, Any]] = []

    for root in run_roots:
        if not root.exists():
            continue
        for metadata_path in root.rglob("metadata.json"):
            run_dir = metadata_path.parent.resolve()
            if run_dir in seen:
                continue
            seen.add(run_dir)
            run = load_run(run_dir)
            if run:
                runs.append(run)
    return runs


def load_run(run_dir: Path) -> dict[str, Any] | None:
    metadata = load_json(run_dir / "metadata.json", {})
    if not isinstance(metadata, dict):
        return None

    steps = load_json(run_dir / "steps.json", [])
    if not isinstance(steps, list):
        steps = []

    evaluation = load_json(run_dir / "evaluation.json", None)
    if not evaluation and isinstance(metadata.get("evaluation"), dict):
        evaluation = metadata["evaluation"]
    if not isinstance(evaluation, dict):
        evaluation = None

    status = (evaluation or {}).get("status") or metadata.get("status") or "unknown"
    score = (evaluation or {}).get("score")
    failure_type = classify_failure(metadata, steps, evaluation)
    duration = duration_seconds(metadata.get("started_at"), metadata.get("finished_at"))

    screenshots = [
        step.get("screenshot")
        for step in steps
        if isinstance(step, dict) and step.get("screenshot")
    ]
    screenshot_files = [
        path
        for path in screenshots
        if isinstance(path, str) and (run_dir / path).exists()
    ]

    return {
        "run_id": metadata.get("run_id") or run_dir.name,
        "task": metadata.get("task") or "",
        "device_type": metadata.get("device_type"),
        "model": metadata.get("model"),
        "status": status,
        "metadata_status": metadata.get("status"),
        "score": score,
        "failure_type": failure_type,
        "started_at": metadata.get("started_at"),
        "finished_at": metadata.get("finished_at"),
        "duration_seconds": duration,
        "step_count": len(steps),
        "current_app": steps[-1].get("current_app") if steps else None,
        "has_steps": bool(steps),
        "has_index": (run_dir / "index.html").exists(),
        "has_evaluation": evaluation is not None,
        "screenshot_steps": len(screenshots),
        "screenshot_files": len(screenshot_files),
        "path": str(run_dir),
        "relative_path": safe_relative(run_dir),
        "steps": steps,
    }


def build_template_metrics(templates: list[Any]) -> dict[str, Any]:
    tags = Counter(tag for template in templates for tag in template.tags)
    app_segments = {
        tag
        for tag in tags
        if tag
        not in {
            "portfolio",
            "safe",
            "ios",
            "smoke",
            "demo",
            "browser",
            "settings",
        }
    }
    guarded = [
        template
        for template in templates
        if "safe" in template.tags or any(term in template.prompt for term in LOW_RISK_TERMS)
    ]
    scored = [template for template in templates if template.success_criteria]

    return {
        "ios_templates": len(templates),
        "scored_templates": len(scored),
        "guarded_templates": len(guarded),
        "app_or_scene_segments": len(app_segments),
        "top_tags": dict(tags.most_common(12)),
    }


def build_quality_metrics(runs: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(runs)
    evaluated = [run for run in runs if run.get("has_evaluation")]
    passed = [run for run in evaluated if run.get("status") == "passed"]
    failed = [
        run
        for run in runs
        if run.get("status") in ("failed", "max_steps") or run.get("failure_type")
    ]
    scores = [
        run["score"]
        for run in evaluated
        if isinstance(run.get("score"), (int, float))
    ]
    steps = [
        run["step_count"]
        for run in runs
        if isinstance(run.get("step_count"), int) and run.get("step_count", 0) > 0
    ]
    durations = [
        run["duration_seconds"]
        for run in runs
        if isinstance(run.get("duration_seconds"), (int, float))
    ]
    failure_counts = Counter(run.get("failure_type") for run in runs if run.get("failure_type"))
    statuses = Counter(str(run.get("status") or "unknown") for run in runs)

    return {
        "total_runs": total,
        "evaluated_runs": len(evaluated),
        "passed_runs": len(passed),
        "failed_or_classified_runs": len(failed),
        "scored_pass_rate": pct(len(passed), len(evaluated)),
        "avg_score": round(mean(scores), 1) if scores else None,
        "avg_steps": round(mean(steps), 1) if steps else None,
        "avg_duration_seconds": round(mean(durations), 1) if durations else None,
        "status_counts": dict(statuses),
        "failure_counts": dict(failure_counts),
    }


def build_artifact_metrics(runs: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(runs)
    complete_replays = [
        run for run in runs if run.get("has_steps") and run.get("has_index")
    ]
    total_steps = sum(run.get("step_count", 0) for run in runs)
    screenshot_steps = sum(run.get("screenshot_steps", 0) for run in runs)
    screenshot_files = sum(run.get("screenshot_files", 0) for run in runs)

    return {
        "complete_replay_runs": len(complete_replays),
        "complete_replay_rate": pct(len(complete_replays), total),
        "runs_with_evaluation": sum(1 for run in runs if run.get("has_evaluation")),
        "evaluation_coverage": pct(
            sum(1 for run in runs if run.get("has_evaluation")),
            total,
        ),
        "total_steps": total_steps,
        "screenshot_steps": screenshot_steps,
        "screenshot_file_coverage": pct(screenshot_files, screenshot_steps),
        "step_screenshot_coverage": pct(screenshot_steps, total_steps),
    }


def build_coordinate_metrics(runs: list[dict[str, Any]]) -> dict[str, Any]:
    touch_actions = 0
    audited_touch_actions = 0
    coordinate_points = 0
    clamped_points = 0
    strategies: Counter[str] = Counter()
    action_counts: Counter[str] = Counter()

    for run in runs:
        for step in run.get("steps", []):
            action = step.get("parsed_action") if isinstance(step, dict) else None
            action_name = action.get("action") if isinstance(action, dict) else None
            if action_name:
                action_counts[str(action_name)] += 1
            if action_name not in TOUCH_ACTIONS:
                continue

            touch_actions += 1
            coordinates = extract_coordinates(step)
            if coordinates:
                audited_touch_actions += 1
            coordinate_points += len(coordinates)
            for coordinate in coordinates:
                if coordinate.get("clamped"):
                    clamped_points += 1
                strategy = coordinate.get("strategy")
                if strategy:
                    strategies[str(strategy)] += 1

    return {
        "touch_actions": touch_actions,
        "audited_touch_actions": audited_touch_actions,
        "coordinate_audit_coverage": pct(audited_touch_actions, touch_actions),
        "coordinate_points": coordinate_points,
        "clamped_points": clamped_points,
        "strategy_counts": dict(strategies),
        "action_counts": dict(action_counts.most_common()),
    }


def extract_coordinates(step: dict[str, Any]) -> list[dict[str, Any]]:
    result = step.get("action_result")
    if not isinstance(result, dict):
        return []
    metadata = result.get("metadata")
    if not isinstance(metadata, dict):
        return []

    coordinates = []
    for key in ("coordinate", "start_coordinate", "end_coordinate"):
        coordinate = metadata.get(key)
        if isinstance(coordinate, dict):
            coordinates.append(coordinate)
    return coordinates


def strip_run_details(run: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in run.items() if key != "steps"}


def render_markdown(metrics: dict[str, Any]) -> str:
    quality = metrics["quality_metrics"]
    artifacts = metrics["artifact_metrics"]
    coordinates = metrics["coordinate_metrics"]
    templates = metrics["template_metrics"]
    runs = metrics["runs"]

    lines = [
        "# BetterGLM 指标报告",
        "",
        f"生成时间：`{metrics['generated_at']}`",
        f"回放目录：`{', '.join(metrics['run_roots'])}`",
        f"已排除运行中任务：`{metrics.get('excluded_running_runs', 0)}`",
        "",
        "## 核心指标",
        "",
        "| 指标 | 数值 | 证明什么 |",
        "| --- | ---: | --- |",
        row("iOS 模板数", templates["ios_templates"], "可复现 demo 和回归场景覆盖。"),
        row("带评分标准模板数", templates["scored_templates"], "任务有确定性成功条件，不靠模型自述。"),
        row("低风险模板数", templates["guarded_templates"], "Prompt 内显式约束不支付、不下单、不互动。"),
        row("回放任务数", quality["total_runs"], "可用于调试、复盘和演示的证据样本。"),
        row("已评分任务数", quality["evaluated_runs"], "有 passed/failed 和分数的任务样本。"),
        row("评分通过率", f"{quality['scored_pass_rate']}%", "基于回放证据的质量指标。"),
        row("平均分", value_or_dash(quality["avg_score"]), "任务完成质量的聚合分。"),
        row("平均步数", value_or_dash(quality["avg_steps"]), "任务效率和收敛速度信号。"),
        row("完整回放率", f"{artifacts['complete_replay_rate']}%", "metadata、steps、HTML replay 的可观测性覆盖。"),
        row("步骤截图覆盖率", f"{artifacts['step_screenshot_coverage']}%", "每一步是否有视觉证据可复盘。"),
        row("坐标审计覆盖率", f"{coordinates['coordinate_audit_coverage']}%", "触控动作是否记录了坐标映射证据。"),
        "",
        "## 质量指标",
        "",
        json_block(quality),
        "",
        "## 回放证据指标",
        "",
        json_block(artifacts),
        "",
        "## 坐标执行指标",
        "",
        json_block(coordinates),
        "",
        "## 模板库指标",
        "",
        json_block(templates),
        "",
        "## 最近任务样本",
        "",
        "| 状态 | 分数 | 步数 | 耗时秒 | 失败类型 | 任务 | 回放目录 |",
        "| --- | ---: | ---: | ---: | --- | --- | --- |",
    ]

    for run in runs[:20]:
        lines.append(
            "| {status} | {score} | {steps} | {duration} | {failure} | {task} | `{path}` |".format(
                status=escape_cell(run.get("status") or "-"),
                score=escape_cell(value_or_dash(run.get("score"))),
                steps=escape_cell(value_or_dash(run.get("step_count"))),
                duration=escape_cell(value_or_dash(run.get("duration_seconds"))),
                failure=escape_cell(run.get("failure_type") or "-"),
                task=escape_cell(shorten(run.get("task") or "", 48)),
                path=escape_cell(run.get("relative_path") or run.get("path") or ""),
            )
        )

    lines.extend(
        [
            "",
            "## 这些数据怎么证明优化",
            "",
            "- 不是只录一次成功 demo，而是把每次任务沉淀为 metadata、steps、screenshots、HTML replay 和 evaluation report。",
            "- 评分通过率、平均分、平均步数能证明 Agent 质量和效率，而不是只相信模型说“完成了”。",
            "- 失败类型能区分 max_steps、目标 App 不匹配、目标文本缺失、WDA/坐标/解析异常，方便继续优化。",
            "- 坐标审计覆盖率能证明点击链路被观测：模型坐标、截图像素、WDA/设备坐标都有记录。",
            "- 模板数量和低风险模板数量能证明你做了场景库和安全边界，而不是零散手写 prompt。",
            "",
            "## 简历可写",
            "",
            "- 构建手机 Agent 回放评测体系，累计生成多条真实 iOS 任务回放，统计评分通过率、平均步数、失败类型和坐标审计覆盖率。",
            "- 将单次手机自动化 demo 产品化为可复现模板库和质量 Dashboard，支持任务级 replay、deterministic evaluation 和失败归因。",
            "- 优化多模态点击执行链路，记录模型归一化坐标、截图像素和 WDA 触控坐标，用数据定位点击偏移问题。",
        ]
    )
    return "\n".join(lines) + "\n"


def row(metric: str, value: Any, why: str) -> str:
    return f"| {metric} | {value} | {why} |"


def json_block(value: Any) -> str:
    return "```json\n" + json.dumps(value, ensure_ascii=False, indent=2) + "\n```"


def load_json(path: Path, default: Any) -> Any:
    try:
        if not path.exists():
            return default
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return default


def duration_seconds(started_at: str | None, finished_at: str | None) -> int | None:
    if not started_at or not finished_at:
        return None
    try:
        started = datetime.fromisoformat(started_at)
        finished = datetime.fromisoformat(finished_at)
    except ValueError:
        return None
    return max(0, round((finished - started).total_seconds()))


def pct(numerator: int, denominator: int) -> int:
    return round(numerator * 100 / denominator) if denominator else 0


def value_or_dash(value: Any) -> Any:
    return "-" if value is None else value


def shorten(value: str, limit: int) -> str:
    return value if len(value) <= limit else value[: limit - 1] + "…"


def escape_cell(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


def safe_relative(path: Path) -> str:
    try:
        return str(path.relative_to(Path.cwd()))
    except ValueError:
        return str(path)


if __name__ == "__main__":
    main()
