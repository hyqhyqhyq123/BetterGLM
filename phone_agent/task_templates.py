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
    success_criteria: dict[str, Any] = field(default_factory=dict)

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
            success_criteria=dict(data.get("success_criteria", {})),
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
        success_criteria={
            "must_contain_text": ["{city}", "天气"],
            "target_app": "Safari",
            "max_steps": 12,
            "min_score": 80,
        },
    ),
    TaskTemplate(
        id="ios_settings_wifi",
        title="iOS settings Wi-Fi check",
        device_type="ios",
        prompt="打开设置，查看当前 Wi-Fi 页面，不要修改任何设置",
        purpose="验证只读型系统设置导航能力，适合安全演示和环境排查。",
        tags=["smoke", "settings", "ios", "safe"],
        success_criteria={
            "must_contain_text": ["Wi-Fi"],
            "target_app": "Settings",
            "max_steps": 8,
            "min_score": 80,
        },
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
        success_criteria={
            "must_contain_text": ["BetterGLM", "Doctor", "Replay", "Web Console"],
            "target_app": "Notes",
            "max_steps": 20,
            "min_score": 80,
        },
    ),
    TaskTemplate(
        id="ios_wechat_search_contact",
        title="WeChat safe contact search",
        device_type="ios",
        prompt="打开微信，搜索{keyword}，停留在搜索结果页，不要发送消息、不要点击支付或小程序",
        purpose="验证腾讯系 App 的启动、搜索入口定位和安全边界控制。",
        variables={"keyword": "文件传输助手"},
        tags=["portfolio", "tencent", "wechat", "safe"],
        success_criteria={
            "must_contain_text": ["{keyword}"],
            "target_app": "微信",
            "max_steps": 15,
            "min_score": 80,
        },
    ),
    TaskTemplate(
        id="ios_alipay_search_service",
        title="Alipay safe service search",
        device_type="ios",
        prompt="打开支付宝，搜索{keyword}，停留在搜索结果页，不要转账、不要付款、不要打开收付款码",
        purpose="验证支付类 App 的安全操作约束和搜索流程。",
        variables={"keyword": "汇率"},
        tags=["portfolio", "alibaba", "alipay", "safe"],
        success_criteria={
            "must_contain_text": ["{keyword}"],
            "target_app": "支付宝",
            "max_steps": 15,
            "min_score": 80,
        },
    ),
    TaskTemplate(
        id="ios_taobao_search_product",
        title="Taobao product search",
        device_type="ios",
        prompt="打开淘宝，搜索{keyword}，停留在商品搜索结果页，不要下单、不要加入购物车",
        purpose="验证电商 App 搜索链路和交易边界控制。",
        variables={"keyword": "机械键盘"},
        tags=["portfolio", "alibaba", "ecommerce", "safe"],
        success_criteria={
            "must_contain_text": ["{keyword}"],
            "target_app": "淘宝",
            "max_steps": 16,
            "min_score": 80,
        },
    ),
    TaskTemplate(
        id="ios_jd_search_product",
        title="JD product search",
        device_type="ios",
        prompt="打开京东，搜索{keyword}，停留在商品搜索结果页，不要下单、不要加入购物车",
        purpose="验证京东类电商搜索场景和安全边界。",
        variables={"keyword": "显示器"},
        tags=["portfolio", "jd", "ecommerce", "safe"],
        success_criteria={
            "must_contain_text": ["{keyword}"],
            "target_app": "京东",
            "max_steps": 16,
            "min_score": 80,
        },
    ),
    TaskTemplate(
        id="ios_meituan_search_food",
        title="Meituan local service search",
        device_type="ios",
        prompt="打开美团，搜索{keyword}，停留在搜索结果页，不要下单、不要支付",
        purpose="验证本地生活 App 的搜索、列表页识别和交易边界控制。",
        variables={"keyword": "咖啡"},
        tags=["portfolio", "meituan", "local-service", "safe"],
        success_criteria={
            "must_contain_text": ["{keyword}"],
            "target_app": "美团",
            "max_steps": 16,
            "min_score": 80,
        },
    ),
    TaskTemplate(
        id="ios_dianping_search_restaurant",
        title="Dianping restaurant search",
        device_type="ios",
        prompt="打开大众点评，搜索{keyword}，停留在商户或笔记搜索结果页，不要下单、不要写评价",
        purpose="验证中厂本地生活内容检索和列表页导航能力。",
        variables={"keyword": "火锅"},
        tags=["portfolio", "meituan", "dianping", "safe"],
        success_criteria={
            "must_contain_text": ["{keyword}"],
            "target_app": "大众点评",
            "max_steps": 16,
            "min_score": 80,
        },
    ),
    TaskTemplate(
        id="ios_xiaohongshu_search_note",
        title="Xiaohongshu content search",
        device_type="ios",
        prompt="打开小红书，搜索{keyword}，停留在笔记搜索结果页，不要点赞、不要收藏、不要评论",
        purpose="验证社区内容 App 的搜索结果定位和互动边界控制。",
        variables={"keyword": "面试经验"},
        tags=["portfolio", "content", "xiaohongshu", "safe"],
        success_criteria={
            "must_contain_text": ["{keyword}"],
            "target_app": "小红书",
            "max_steps": 16,
            "min_score": 80,
        },
    ),
    TaskTemplate(
        id="ios_douyin_search_topic",
        title="Douyin topic search",
        device_type="ios",
        prompt="打开抖音，搜索{keyword}，停留在搜索结果页，不要点赞、不要关注、不要评论",
        purpose="验证短视频 App 的搜索入口定位和高动态页面处理能力。",
        variables={"keyword": "AI Agent"},
        tags=["portfolio", "bytedance", "video", "safe"],
        success_criteria={
            "must_contain_text": ["{keyword}"],
            "target_app": "抖音",
            "max_steps": 18,
            "min_score": 80,
        },
    ),
    TaskTemplate(
        id="ios_bilibili_search_video",
        title="Bilibili video search",
        device_type="ios",
        prompt="打开哔哩哔哩，搜索{keyword}，停留在视频搜索结果页，不要点赞、不要投币、不要评论",
        purpose="验证视频内容平台搜索和结果页识别能力。",
        variables={"keyword": "Python 教程"},
        tags=["portfolio", "bilibili", "video", "safe"],
        success_criteria={
            "must_contain_text": ["{keyword}"],
            "target_app": "哔哩哔哩",
            "max_steps": 16,
            "min_score": 80,
        },
    ),
    TaskTemplate(
        id="ios_zhihu_search_question",
        title="Zhihu question search",
        device_type="ios",
        prompt="打开知乎，搜索{keyword}，停留在问题或内容搜索结果页，不要点赞、不要收藏、不要评论",
        purpose="验证问答社区搜索和文本密集页面理解能力。",
        variables={"keyword": "大模型 Agent"},
        tags=["portfolio", "content", "zhihu", "safe"],
        success_criteria={
            "must_contain_text": ["{keyword}"],
            "target_app": "知乎",
            "max_steps": 16,
            "min_score": 80,
        },
    ),
    TaskTemplate(
        id="ios_weibo_search_topic",
        title="Weibo topic search",
        device_type="ios",
        prompt="打开微博，搜索{keyword}，停留在搜索结果页，不要点赞、不要转发、不要评论",
        purpose="验证信息流社区 App 的搜索入口和互动边界控制。",
        variables={"keyword": "人工智能"},
        tags=["portfolio", "content", "weibo", "safe"],
        success_criteria={
            "must_contain_text": ["{keyword}"],
            "target_app": "微博",
            "max_steps": 16,
            "min_score": 80,
        },
    ),
    TaskTemplate(
        id="ios_gaode_search_place",
        title="Amap place search",
        device_type="ios",
        prompt="打开高德地图，搜索{keyword}，停留在地点搜索结果页，不要发起打车、不要导航",
        purpose="验证地图类 App 的地点检索和出行敏感动作边界。",
        variables={"keyword": "北京南站"},
        tags=["portfolio", "alibaba", "map", "safe"],
        success_criteria={
            "must_contain_text": ["{keyword}"],
            "target_app": "高德地图",
            "max_steps": 15,
            "min_score": 80,
        },
    ),
    TaskTemplate(
        id="ios_ctrip_search_hotel",
        title="Ctrip hotel search",
        device_type="ios",
        prompt="打开携程，搜索{keyword}，停留在搜索结果页，不要预订、不要支付",
        purpose="验证旅行类中厂 App 搜索链路和订单边界控制。",
        variables={"keyword": "上海酒店"},
        tags=["portfolio", "travel", "ctrip", "safe"],
        success_criteria={
            "must_contain_text": ["{keyword}"],
            "target_app": "携程",
            "max_steps": 18,
            "min_score": 80,
        },
    ),
    TaskTemplate(
        id="ios_dewu_search_product",
        title="Dewu product search",
        device_type="ios",
        prompt="打开得物，搜索{keyword}，停留在商品搜索结果页，不要下单、不要支付",
        purpose="验证潮流电商中厂 App 的搜索和交易安全边界。",
        variables={"keyword": "运动鞋"},
        tags=["portfolio", "ecommerce", "dewu", "safe"],
        success_criteria={
            "must_contain_text": ["{keyword}"],
            "target_app": "得物",
            "max_steps": 16,
            "min_score": 80,
        },
    ),
    TaskTemplate(
        id="ios_smzdm_search_deal",
        title="SMZDM deal search",
        device_type="ios",
        prompt="打开什么值得买，搜索{keyword}，停留在搜索结果页，不要点击购买链接",
        purpose="验证导购内容 App 的搜索和外链购买边界控制。",
        variables={"keyword": "咖啡机"},
        tags=["portfolio", "content-commerce", "safe"],
        success_criteria={
            "must_contain_text": ["{keyword}"],
            "target_app": "什么值得买",
            "max_steps": 16,
            "min_score": 80,
        },
    ),
    TaskTemplate(
        id="ios_luckin_search_store",
        title="Luckin store/product search",
        device_type="ios",
        prompt="打开 Luckin Coffee，搜索或查看{keyword}相关页面，停留在结果页，不要下单、不要支付",
        purpose="验证咖啡零售 App 的搜索/菜单页面导航和支付边界。",
        variables={"keyword": "拿铁"},
        tags=["portfolio", "retail", "coffee", "safe"],
        success_criteria={
            "must_contain_text": ["{keyword}"],
            "target_app": "Luckin Coffee",
            "max_steps": 16,
            "min_score": 80,
        },
    ),
    TaskTemplate(
        id="android_browser_weather",
        title="Android browser weather search",
        device_type="adb",
        prompt="打开浏览器搜索{city}天气",
        purpose="验证 Android ADB、应用启动和文本输入链路。",
        variables={"city": "北京"},
        tags=["smoke", "browser", "android"],
        success_criteria={
            "must_contain_text": ["{city}", "天气"],
            "max_steps": 15,
            "min_score": 80,
        },
    ),
    TaskTemplate(
        id="harmony_browser_weather",
        title="HarmonyOS browser weather search",
        device_type="hdc",
        prompt="打开浏览器搜索{city}天气",
        purpose="验证 HarmonyOS HDC、应用启动和文本输入链路。",
        variables={"city": "北京"},
        tags=["smoke", "browser", "harmonyos"],
        success_criteria={
            "must_contain_text": ["{city}", "天气"],
            "max_steps": 15,
            "min_score": 80,
        },
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


def render_success_criteria(
    template: TaskTemplate, variables: dict[str, str] | None = None
) -> dict[str, Any]:
    """Render success criteria placeholders with template variables."""

    values = dict(template.variables)
    values.update(variables or {})
    return _render_value(template.success_criteria, _TemplateVars(values))


def task_template_payload(template: TaskTemplate) -> dict[str, Any]:
    """Return a JSON-friendly template with its default rendered prompt."""

    data = template.to_dict()
    data["rendered_prompt"] = render_task_template(template)
    data["rendered_success_criteria"] = render_success_criteria(template)
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


def _render_value(value: Any, variables: _TemplateVars) -> Any:
    if isinstance(value, str):
        return value.format_map(variables)
    if isinstance(value, list):
        return [_render_value(item, variables) for item in value]
    if isinstance(value, dict):
        return {key: _render_value(item, variables) for key, item in value.items()}
    return value
