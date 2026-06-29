"""Replay logging for agent runs."""

from __future__ import annotations

import base64
import html
import json
import re
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any


class ReplayRecorder:
    """Persist screenshots, step metadata, and an HTML replay for one task."""

    def __init__(
        self,
        root_dir: str | Path,
        task: str,
        device_type: str,
        model_name: str,
        config: dict[str, Any] | None = None,
    ):
        self.root_dir = Path(root_dir)
        self.started_at = datetime.now()
        self.run_id = f"{self.started_at.strftime('%Y%m%d-%H%M%S')}-{_slug(task)}"
        self.run_dir = self.root_dir / self.run_id
        self.screenshot_dir = self.run_dir / "screenshots"
        self.screenshot_dir.mkdir(parents=True, exist_ok=True)

        self.metadata: dict[str, Any] = {
            "run_id": self.run_id,
            "task": task,
            "device_type": device_type,
            "model": model_name,
            "started_at": self.started_at.isoformat(timespec="seconds"),
            "finished_at": None,
            "status": "running",
            "result": None,
            "config": config or {},
        }
        self.steps: list[dict[str, Any]] = []
        self._write_all()

    def record_step(
        self,
        *,
        step_index: int,
        current_app: str,
        screen_info: str,
        screenshot: Any,
        thinking: str = "",
        raw_action: str = "",
        parsed_action: dict[str, Any] | None = None,
        action_result: Any | None = None,
        finished: bool = False,
        message: str | None = None,
        error: str | None = None,
        model_metrics: dict[str, Any] | None = None,
    ) -> None:
        screenshot_path = self._save_screenshot(step_index, screenshot)
        step = {
            "step": step_index,
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "current_app": current_app,
            "screen_info": screen_info,
            "screenshot": screenshot_path,
            "screenshot_size": {
                "width": getattr(screenshot, "width", None),
                "height": getattr(screenshot, "height", None),
                "is_sensitive": getattr(screenshot, "is_sensitive", False),
            },
            "thinking": thinking,
            "raw_action": raw_action,
            "parsed_action": parsed_action,
            "action_result": _to_plain_dict(action_result),
            "finished": finished,
            "message": message,
            "error": error,
            "model_metrics": model_metrics or {},
        }
        self.steps.append(step)
        self._write_all()

    def finish(self, result: str, status: str = "completed") -> None:
        self.metadata["finished_at"] = datetime.now().isoformat(timespec="seconds")
        self.metadata["status"] = status
        self.metadata["result"] = result
        self._write_all()

    def _save_screenshot(self, step_index: int, screenshot: Any) -> str | None:
        base64_data = getattr(screenshot, "base64_data", None)
        if not base64_data:
            return None

        filename = f"step_{step_index:03d}.png"
        path = self.screenshot_dir / filename
        try:
            path.write_bytes(base64.b64decode(base64_data))
        except Exception:
            return None
        return f"screenshots/{filename}"

    def _write_all(self) -> None:
        self.run_dir.mkdir(parents=True, exist_ok=True)
        (self.run_dir / "metadata.json").write_text(
            json.dumps(self.metadata, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        (self.run_dir / "steps.json").write_text(
            json.dumps(self.steps, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        (self.run_dir / "index.html").write_text(self._render_html(), encoding="utf-8")

    def _render_html(self) -> str:
        step_cards = "\n".join(self._render_step(step) for step in self.steps)
        metadata = self.metadata
        return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>BetterGLM Replay - {html.escape(metadata['run_id'])}</title>
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; margin: 0; background: #f7f8fa; color: #1f2328; }}
    header {{ padding: 24px 32px; background: #101418; color: white; }}
    main {{ max-width: 1180px; margin: 0 auto; padding: 24px; }}
    .summary {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 12px; margin-bottom: 20px; }}
    .box, .step {{ background: white; border: 1px solid #d8dee4; border-radius: 8px; padding: 16px; }}
    .step {{ display: grid; grid-template-columns: minmax(220px, 320px) 1fr; gap: 18px; margin-bottom: 18px; }}
    img {{ width: 100%; border: 1px solid #d8dee4; border-radius: 6px; background: #111; }}
    pre {{ white-space: pre-wrap; word-break: break-word; background: #f6f8fa; padding: 12px; border-radius: 6px; overflow: auto; }}
    .muted {{ color: #667085; }}
    .ok {{ color: #137333; }}
    .fail {{ color: #b42318; }}
    .coord {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 8px; }}
    @media (max-width: 760px) {{ .step {{ grid-template-columns: 1fr; }} main {{ padding: 14px; }} }}
  </style>
</head>
<body>
  <header>
    <h1>BetterGLM Replay</h1>
    <p>{html.escape(metadata["task"])}</p>
  </header>
  <main>
    <section class="summary">
      <div class="box"><strong>Status</strong><br>{html.escape(str(metadata["status"]))}</div>
      <div class="box"><strong>Model</strong><br>{html.escape(str(metadata["model"]))}</div>
      <div class="box"><strong>Device</strong><br>{html.escape(str(metadata["device_type"]))}</div>
      <div class="box"><strong>Steps</strong><br>{len(self.steps)}</div>
    </section>
    {step_cards or '<div class="box muted">No steps recorded yet.</div>'}
  </main>
</body>
</html>
"""

    def _render_step(self, step: dict[str, Any]) -> str:
        screenshot = step.get("screenshot")
        image_html = (
            f'<img src="{html.escape(screenshot)}" alt="Step {step["step"]} screenshot">'
            if screenshot
            else '<div class="box muted">No screenshot</div>'
        )
        status_class = "ok" if not step.get("error") else "fail"
        action = json.dumps(step.get("parsed_action"), ensure_ascii=False, indent=2)
        result = json.dumps(step.get("action_result"), ensure_ascii=False, indent=2)
        metrics = json.dumps(step.get("model_metrics"), ensure_ascii=False, indent=2)
        coordinate_html = self._render_coordinate_audit(step)
        return f"""<section class="step">
  <div>
    <h2>Step {step["step"]}</h2>
    {image_html}
  </div>
  <div>
    <p class="muted">{html.escape(str(step.get("timestamp", "")))} | {html.escape(str(step.get("current_app", "")))}</p>
    <p class="{status_class}">{html.escape(str(step.get("message") or step.get("error") or "running"))}</p>
    <h3>Thinking</h3>
    <pre>{html.escape(step.get("thinking") or "")}</pre>
    <h3>Raw Action</h3>
    <pre>{html.escape(step.get("raw_action") or "")}</pre>
    <h3>Parsed Action</h3>
    <pre>{html.escape(action)}</pre>
    <h3>Execution Result</h3>
    <pre>{html.escape(result)}</pre>
    {coordinate_html}
    <h3>Model Metrics</h3>
    <pre>{html.escape(metrics)}</pre>
  </div>
</section>"""

    def _render_coordinate_audit(self, step: dict[str, Any]) -> str:
        result = step.get("action_result") or {}
        metadata = result.get("metadata") if isinstance(result, dict) else None
        if not isinstance(metadata, dict):
            return ""

        coordinate = metadata.get("coordinate") or metadata.get("start_coordinate")
        if not isinstance(coordinate, dict):
            return ""

        target = coordinate.get("target_point") or coordinate.get("transport_coordinate")
        return f"""<h3>Coordinate Audit</h3>
    <div class="coord">
      <div class="box"><strong>Model</strong><br>{html.escape(str(coordinate.get("model_coordinate")))}</div>
      <div class="box"><strong>Screenshot</strong><br>{html.escape(str(coordinate.get("screenshot_pixel")))}</div>
      <div class="box"><strong>Target</strong><br>{html.escape(str(target))}</div>
      <div class="box"><strong>Strategy</strong><br>{html.escape(str(coordinate.get("strategy")))}</div>
    </div>"""


def _to_plain_dict(value: Any) -> Any:
    if value is None:
        return None
    if hasattr(value, "__dataclass_fields__"):
        return asdict(value)
    if isinstance(value, dict):
        return value
    return str(value)


def _slug(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9\u4e00-\u9fff]+", "-", value.strip()).strip("-")
    if not slug:
        return "task"
    return slug[:48]
