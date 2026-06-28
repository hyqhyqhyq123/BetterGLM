"""Local Web console for BetterGLM demos and debugging."""

from __future__ import annotations

import json
import threading
import traceback
from dataclasses import asdict, dataclass
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

from phone_agent import PhoneAgent
from phone_agent.agent import AgentConfig
from phone_agent.agent_ios import IOSAgentConfig, IOSPhoneAgent
from phone_agent.device_factory import DeviceType, set_device_type
from phone_agent.doctor import DoctorOptions, run_doctor
from phone_agent.model import ModelConfig


@dataclass
class WebConsoleOptions:
    """Runtime configuration for the local Web console."""

    host: str = "127.0.0.1"
    port: int = 8765
    device_type: str = "ios"
    base_url: str = "http://localhost:8000/v1"
    api_key: str = "EMPTY"
    model_name: str = "autoglm-phone-9b"
    max_steps: int = 100
    device_id: str | None = None
    wda_url: str = "http://localhost:8100"
    lang: str = "cn"
    replay_dir: str = "runs/web"
    quiet: bool = False


class WebConsoleState:
    """Thread-safe state shared by HTTP handlers and agent jobs."""

    def __init__(self, options: WebConsoleOptions):
        self.options = options
        self.lock = threading.Lock()
        self.running = False
        self.task: str | None = None
        self.result: str | None = None
        self.error: str | None = None
        self.replay_path: str | None = None
        self.started_at: str | None = None
        self.finished_at: str | None = None
        self.job_thread: threading.Thread | None = None

    def snapshot(self) -> dict[str, Any]:
        with self.lock:
            data = {
                "running": self.running,
                "task": self.task,
                "result": self.result,
                "error": self.error,
                "replay_path": self.replay_path,
                "started_at": self.started_at,
                "finished_at": self.finished_at,
                "options": _public_options(self.options),
            }

        data.update(_read_replay_state(self.replay_path))
        return data

    def start_job(self, task: str) -> tuple[bool, str]:
        task = task.strip()
        if not task:
            return False, "Task is empty"

        with self.lock:
            if self.running:
                return False, "Another task is already running"

            self.running = True
            self.task = task
            self.result = None
            self.error = None
            self.replay_path = None
            self.started_at = _now()
            self.finished_at = None

            self.job_thread = threading.Thread(
                target=self._run_task, args=(task,), daemon=True
            )
            self.job_thread.start()

        return True, "Task started"

    def _run_task(self, task: str) -> None:
        agent: Any | None = None
        monitor_stop = threading.Event()
        monitor_thread: threading.Thread | None = None
        try:
            agent = _build_agent(self.options)
            monitor_thread = threading.Thread(
                target=self._monitor_replay_path,
                args=(agent, monitor_stop),
                daemon=True,
            )
            monitor_thread.start()
            result = agent.run(task)
            with self.lock:
                self.result = result
                self.replay_path = agent.replay_path
        except Exception as e:
            with self.lock:
                self.error = str(e)
                self.result = None
                if agent and getattr(agent, "replay_path", None):
                    self.replay_path = agent.replay_path
            traceback.print_exc()
        finally:
            monitor_stop.set()
            if monitor_thread:
                monitor_thread.join(timeout=1)
            with self.lock:
                self.running = False
                self.finished_at = _now()

    def _monitor_replay_path(self, agent: Any, stop_event: threading.Event) -> None:
        while not stop_event.wait(0.5):
            replay_path = getattr(agent, "replay_path", None)
            if replay_path:
                with self.lock:
                    self.replay_path = replay_path


def run_web_console(options: WebConsoleOptions) -> None:
    """Start the local Web console and block until interrupted."""

    state = WebConsoleState(options)

    class Handler(WebConsoleHandler):
        console_state = state

    server = ThreadingHTTPServer((options.host, options.port), Handler)
    url = f"http://{options.host}:{options.port}"
    print("=" * 60)
    print("BetterGLM Web Console")
    print("=" * 60)
    print(f"Open: {url}")
    print("Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping BetterGLM Web Console...")
    finally:
        server.server_close()


class WebConsoleHandler(BaseHTTPRequestHandler):
    """HTTP endpoints for the Web console."""

    console_state: WebConsoleState

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/":
            self._send_html(INDEX_HTML)
        elif parsed.path == "/api/state":
            self._send_json(self.console_state.snapshot())
        elif parsed.path.startswith("/replays/"):
            self._send_replay_file(parsed.path)
        else:
            self._send_json({"error": "Not found"}, status=HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/api/run":
            payload = self._read_json()
            ok, message = self.console_state.start_job(str(payload.get("task", "")))
            status = HTTPStatus.ACCEPTED if ok else HTTPStatus.CONFLICT
            self._send_json({"ok": ok, "message": message}, status=status)
        elif parsed.path == "/api/doctor":
            payload = self._read_json()
            skip_model = bool(payload.get("skip_model", True))
            report = run_doctor(
                DoctorOptions(
                    device_type=self.console_state.options.device_type,
                    base_url=self.console_state.options.base_url,
                    api_key=self.console_state.options.api_key,
                    model_name=self.console_state.options.model_name,
                    wda_url=self.console_state.options.wda_url,
                    device_id=self.console_state.options.device_id,
                    check_model=not skip_model,
                )
            )
            self._send_json(
                {
                    "ok": report.ok,
                    "checks": [asdict(check) for check in report.checks],
                }
            )
        else:
            self._send_json({"error": "Not found"}, status=HTTPStatus.NOT_FOUND)

    def log_message(self, format: str, *args: Any) -> None:
        return

    def _read_json(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0"))
        if length <= 0:
            return {}
        raw = self.rfile.read(length).decode("utf-8")
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return {}

    def _send_json(self, payload: dict[str, Any], status: int = HTTPStatus.OK) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_html(self, html: str) -> None:
        body = html.encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_replay_file(self, request_path: str) -> None:
        replay_root = Path(self.console_state.options.replay_dir).resolve()
        relative = unquote(request_path.removeprefix("/replays/"))
        file_path = (replay_root / relative).resolve()

        if replay_root not in file_path.parents and file_path != replay_root:
            self._send_json({"error": "Invalid path"}, status=HTTPStatus.FORBIDDEN)
            return
        if not file_path.is_file():
            self._send_json({"error": "Not found"}, status=HTTPStatus.NOT_FOUND)
            return

        content_type = "application/octet-stream"
        if file_path.suffix == ".png":
            content_type = "image/png"
        elif file_path.suffix == ".html":
            content_type = "text/html; charset=utf-8"
        elif file_path.suffix == ".json":
            content_type = "application/json; charset=utf-8"

        body = file_path.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def _build_agent(options: WebConsoleOptions):
    model_config = ModelConfig(
        base_url=options.base_url,
        model_name=options.model_name,
        api_key=options.api_key,
        lang=options.lang,
    )

    if options.device_type == "ios":
        agent_config = IOSAgentConfig(
            max_steps=options.max_steps,
            wda_url=options.wda_url,
            device_id=options.device_id,
            verbose=not options.quiet,
            lang=options.lang,
            replay_dir=options.replay_dir,
        )
        return IOSPhoneAgent(model_config=model_config, agent_config=agent_config)

    device_type = DeviceType.HDC if options.device_type == "hdc" else DeviceType.ADB
    set_device_type(device_type)
    agent_config = AgentConfig(
        max_steps=options.max_steps,
        device_id=options.device_id,
        device_type=options.device_type,
        verbose=not options.quiet,
        lang=options.lang,
        replay_dir=options.replay_dir,
    )
    return PhoneAgent(model_config=model_config, agent_config=agent_config)


def _read_replay_state(replay_path: str | None) -> dict[str, Any]:
    if not replay_path:
        return {"replay": None, "steps": []}

    run_dir = Path(replay_path)
    metadata_path = run_dir / "metadata.json"
    steps_path = run_dir / "steps.json"
    metadata: dict[str, Any] | None = None
    steps: list[dict[str, Any]] = []

    try:
        if metadata_path.exists():
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        if steps_path.exists():
            steps = json.loads(steps_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {
            "replay": {
                "metadata": metadata,
                "path": replay_path,
                "index_url": f"/replays/{run_dir.name}/index.html",
                "root": str(run_dir.parent),
            },
            "steps": [],
        }

    replay_root = run_dir.parent
    for step in steps:
        screenshot = step.get("screenshot")
        if screenshot:
            relative = f"{run_dir.name}/{screenshot}"
            step["screenshot_url"] = f"/replays/{relative}"

    return {
        "replay": {
            "metadata": metadata,
            "path": replay_path,
            "index_url": f"/replays/{run_dir.name}/index.html",
            "root": str(replay_root),
        },
        "steps": steps,
    }


def _public_options(options: WebConsoleOptions) -> dict[str, Any]:
    data = asdict(options)
    api_key = data.get("api_key")
    if api_key and api_key != "EMPTY":
        data["api_key"] = f"{api_key[:4]}...{api_key[-4:]}" if len(api_key) > 8 else "***"
    return data


def _now() -> str:
    from datetime import datetime

    return datetime.now().isoformat(timespec="seconds")


INDEX_HTML = """<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>BetterGLM Console</title>
  <style>
    :root { color-scheme: light; }
    body { margin: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; background: #f6f7f9; color: #1d232a; }
    header { display: flex; justify-content: space-between; align-items: center; gap: 18px; padding: 18px 24px; background: #101418; color: white; }
    header h1 { margin: 0; font-size: 20px; }
    header p { margin: 4px 0 0; color: #c9d1d9; font-size: 13px; }
    main { display: grid; grid-template-columns: 360px 1fr; gap: 18px; padding: 18px; max-width: 1400px; margin: 0 auto; }
    section { background: white; border: 1px solid #d8dee4; border-radius: 8px; padding: 16px; }
    label { display: block; font-size: 13px; color: #57606a; margin-bottom: 8px; }
    textarea { width: 100%; min-height: 128px; box-sizing: border-box; resize: vertical; border: 1px solid #d0d7de; border-radius: 6px; padding: 10px; font: inherit; }
    button { border: 0; border-radius: 6px; padding: 10px 12px; background: #0969da; color: white; font-weight: 600; cursor: pointer; }
    button.secondary { background: #57606a; }
    button:disabled { opacity: .55; cursor: not-allowed; }
    .row { display: flex; gap: 8px; margin-top: 10px; }
    .kv { display: grid; grid-template-columns: 110px 1fr; gap: 8px; font-size: 13px; margin-top: 12px; }
    .muted { color: #667085; }
    .status { font-weight: 700; }
    .ok { color: #137333; }
    .fail { color: #b42318; }
    .warn { color: #9a6700; }
    .steps { display: grid; gap: 14px; }
    .step { display: grid; grid-template-columns: minmax(180px, 280px) 1fr; gap: 14px; border-top: 1px solid #d8dee4; padding-top: 14px; }
    .step:first-child { border-top: 0; padding-top: 0; }
    .step img { width: 100%; border-radius: 6px; border: 1px solid #d8dee4; background: #111; }
    pre { white-space: pre-wrap; word-break: break-word; background: #f6f8fa; border-radius: 6px; padding: 10px; max-height: 220px; overflow: auto; }
    .doctor-check { border-top: 1px solid #d8dee4; padding: 8px 0; font-size: 13px; }
    .doctor-check:first-child { border-top: 0; }
    @media (max-width: 900px) { main { grid-template-columns: 1fr; } .step { grid-template-columns: 1fr; } }
  </style>
</head>
<body>
  <header>
    <div>
      <h1>BetterGLM Console</h1>
      <p>本地手机 Agent 控制台：任务输入、状态观察、日志回放</p>
    </div>
    <div id="topStatus" class="status">Idle</div>
  </header>
  <main>
    <div>
      <section>
        <label for="task">任务</label>
        <textarea id="task" placeholder="例如：打开 Safari 搜索天气"></textarea>
        <div class="row">
          <button id="runBtn" onclick="runTask()">运行任务</button>
          <button class="secondary" onclick="runDoctor()">Doctor</button>
        </div>
        <div class="kv" id="config"></div>
      </section>
      <section style="margin-top: 18px;">
        <h2>Doctor</h2>
        <div id="doctor" class="muted">点击 Doctor 查看本机环境诊断。</div>
      </section>
    </div>
    <section>
      <h2>运行状态</h2>
      <div id="summary" class="muted">等待任务。</div>
      <div id="replayLink" style="margin: 10px 0;"></div>
      <h2>步骤回放</h2>
      <div id="steps" class="steps muted">暂无步骤。</div>
    </section>
  </main>
  <script>
    async function fetchState() {
      const res = await fetch('/api/state');
      const state = await res.json();
      renderState(state);
    }

    async function runTask() {
      const task = document.getElementById('task').value;
      const res = await fetch('/api/run', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({task})
      });
      const payload = await res.json();
      if (!payload.ok) alert(payload.message || '任务启动失败');
      fetchState();
    }

    async function runDoctor() {
      const res = await fetch('/api/doctor', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({skip_model: true})
      });
      renderDoctor(await res.json());
    }

    function renderState(state) {
      document.getElementById('topStatus').textContent = state.running ? 'Running' : 'Idle';
      document.getElementById('topStatus').className = 'status ' + (state.error ? 'fail' : state.running ? 'warn' : 'ok');
      document.getElementById('runBtn').disabled = state.running;
      const options = state.options || {};
      document.getElementById('config').innerHTML = [
        ['Device', options.device_type],
        ['Model', options.model_name],
        ['WDA', options.wda_url],
        ['Replay', options.replay_dir]
      ].map(([k, v]) => `<div class="muted">${escapeHtml(k)}</div><div>${escapeHtml(v || '')}</div>`).join('');

      document.getElementById('summary').innerHTML = `
        <div><strong>Task:</strong> ${escapeHtml(state.task || 'None')}</div>
        <div><strong>Result:</strong> ${escapeHtml(state.result || state.error || (state.running ? 'Running...' : 'None'))}</div>
      `;
      document.getElementById('replayLink').innerHTML = state.replay ? `<a href="${state.replay.index_url}" target="_blank">打开完整回放 HTML</a><br><span class="muted">${escapeHtml(state.replay.path)}</span>` : '';
      renderSteps(state.steps || []);
    }

    function renderSteps(steps) {
      const el = document.getElementById('steps');
      if (!steps.length) {
        el.textContent = '暂无步骤。';
        el.className = 'steps muted';
        return;
      }
      el.className = 'steps';
      el.innerHTML = steps.map(step => `
        <div class="step">
          <div>${step.screenshot_url ? `<img src="${step.screenshot_url}" alt="step screenshot">` : '<div class="muted">No screenshot</div>'}</div>
          <div>
            <h3>Step ${step.step}</h3>
            <div class="muted">${escapeHtml(step.current_app || '')} | ${escapeHtml(step.timestamp || '')}</div>
            <pre>${escapeHtml(step.raw_action || '')}</pre>
            <pre>${escapeHtml(JSON.stringify(step.action_result || {}, null, 2))}</pre>
          </div>
        </div>
      `).join('');
    }

    function renderDoctor(report) {
      const el = document.getElementById('doctor');
      el.className = '';
      el.innerHTML = (report.checks || []).map(check => `
        <div class="doctor-check">
          <strong class="${check.status}">[${check.status.toUpperCase()}]</strong>
          ${escapeHtml(check.name)}: ${escapeHtml(check.detail)}
          ${check.hint ? `<div class="muted">${escapeHtml(check.hint)}</div>` : ''}
        </div>
      `).join('');
    }

    function escapeHtml(value) {
      return String(value || '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
    }

    fetchState();
    setInterval(fetchState, 1500);
  </script>
</body>
</html>
"""
