"""Reusable task templates for demos, smoke tests, and interviews."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class TaskTemplate:
    """A reproducible phone-agent task with context for demos."""

    id: str
    title: str
    device_type: str
    prompt: str
    purpose: str
    variables: dict[str, str] = field(default_factory=dict)
    tags: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TaskTemplate":
        required = ["id", "title", "device_type", "prompt", "purpose"]
        missing = [key for key in required if not data.get(key)]
        if missing:
            raise ValueError(f"Template is missing required fields: {', '.join(missing)}")

        return cls(
            id=str(data["id"]),
            title=str(data["title"]),
            device_type=str(data["device_type"]).lower(),
            prompt=str(data["prompt"]),
            purpose=str(data["purpose"]),
            variables={str(k): str(v) for k, v in data.get("variables", {}).items()},
            tags=[str(tag) for tag in data.get("tags", [])],
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


DEFAULT_TASK_TEMPLATES: tuple[TaskTemplate, ...] = (
    TaskTemplate(
        id="ios_safari_weather",
        title="iOS Safari weather search",
        device_type="ios",
        prompt="打开 Safari 搜索{city}天气",
        purpose="验证 iOS WDA、视觉理解、应用启动和文本输入是否完整可用。",
        variables={"city": "北京"},
        tags=["smoke", "browser", "ios"],
    ),
    TaskTemplate(
        id="ios_settings_wifi",
        title="iOS settings Wi-Fi check",
        device_type="ios",
        prompt="打开设置，查看当前 Wi-Fi 页面，不要修改任何设置",
        purpose="验证只读型系统设置导航能力，适合安全演示和环境排查。",
        tags=["smoke", "settings", "ios", "safe"],
    ),
    TaskTemplate(
        id="ios_notes_demo",
        title="iOS Notes demo checklist",
        device_type="ios",
        prompt=(
            "打开备忘录，新建一条名为 BetterGLM 演示的备忘录，"
            "内容包含 Doctor、Replay、Web Console 三项"
        ),
        purpose="展示跨步骤输入和结果留痕能力，适合作品集录屏。",
        tags=["demo", "notes", "ios"],
    ),
    TaskTemplate(
        id="android_browser_weather",
        title="Android browser weather search",
        device_type="adb",
        prompt="打开浏览器搜索{city}天气",
        purpose="验证 Android ADB、应用启动和文本输入链路。",
        variables={"city": "北京"},
        tags=["smoke", "browser", "android"],
    ),
    TaskTemplate(
        id="harmony_browser_weather",
        title="HarmonyOS browser weather search",
        device_type="hdc",
        prompt="打开浏览器搜索{city}天气",
        purpose="验证 HarmonyOS HDC、应用启动和文本输入链路。",
        variables={"city": "北京"},
        tags=["smoke", "browser", "harmonyos"],
    ),
)


def load_task_templates(path: str | None = None) -> list[TaskTemplate]:
    """Load built-in templates plus optional user templates from JSON."""

    templates = list(DEFAULT_TASK_TEMPLATES)
    if not path:
        return templates

    template_path = Path(path).expanduser()
    if not template_path.exists():
        raise ValueError(f"Templates file not found: {template_path}")

    payload = json.loads(template_path.read_text(encoding="utf-8"))
    if isinstance(payload, dict):
        items = payload.get("templates", [])
    elif isinstance(payload, list):
        items = payload
    else:
        raise ValueError("Templates file must be a list or an object with templates")

    if not isinstance(items, list):
        raise ValueError("templates must be a list")

    templates.extend(TaskTemplate.from_dict(item) for item in items)
    return templates


def filter_task_templates(
    templates: list[TaskTemplate], device_type: str | None = None
) -> list[TaskTemplate]:
    """Return templates matching a device type, keeping cross-device templates."""

    if not device_type:
        return templates

    normalized = device_type.lower()
    return [
        template
        for template in templates
        if template.device_type in (normalized, "any", "all")
    ]


def get_task_template(
    templates: list[TaskTemplate], template_id: str, device_type: str | None = None
) -> TaskTemplate:
    """Find a template by id and optional device type."""

    candidates = filter_task_templates(templates, device_type)
    for template in candidates:
        if template.id == template_id:
            return template

    available = ", ".join(template.id for template in candidates) or "none"
    raise ValueError(f"Unknown template '{template_id}'. Available: {available}")


def parse_template_vars(values: list[str] | None) -> dict[str, str]:
    """Parse KEY=VALUE pairs from the CLI."""

    variables: dict[str, str] = {}
    for value in values or []:
        if "=" not in value:
            raise ValueError(f"Template variable must be KEY=VALUE, got: {value}")
        key, raw = value.split("=", 1)
        key = key.strip()
        if not key:
            raise ValueError(f"Template variable key is empty: {value}")
        variables[key] = raw
    return variables


def render_task_template(
    template: TaskTemplate, variables: dict[str, str] | None = None
) -> str:
    """Render a task prompt using defaults plus caller-provided variables."""

    values = dict(template.variables)
    values.update(variables or {})
    return template.prompt.format_map(_TemplateVars(values))


def task_template_payload(template: TaskTemplate) -> dict[str, Any]:
    """Return a JSON-friendly template with its default rendered prompt."""

    data = template.to_dict()
    data["rendered_prompt"] = render_task_template(template)
    return data


def format_task_templates(
    templates: list[TaskTemplate], device_type: str | None = None
) -> str:
    """Format templates as a compact CLI table."""

    rows = filter_task_templates(templates, device_type)
    if not rows:
        return "No task templates found."

    id_width = max(len("ID"), *(len(template.id) for template in rows))
    device_width = max(len("Device"), *(len(template.device_type) for template in rows))
    lines = [
        f"{'ID':<{id_width}}  {'Device':<{device_width}}  Title",
        f"{'-' * id_width}  {'-' * device_width}  {'-' * 40}",
    ]
    for template in rows:
        lines.append(
            f"{template.id:<{id_width}}  {template.device_type:<{device_width}}  {template.title}"
        )
        lines.append(f"{'':<{id_width}}  {'':<{device_width}}  {template.purpose}")
        lines.append(
            f"{'':<{id_width}}  {'':<{device_width}}  Task: {render_task_template(template)}"
        )
    return "\n".join(lines)


class _TemplateVars(dict[str, str]):
    def __missing__(self, key: str) -> str:
        return "{" + key + "}"
