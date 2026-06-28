"""Environment diagnostics for BetterGLM/Phone Agent."""

from __future__ import annotations

import importlib.util
import json
import os
import platform
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from urllib.parse import urlparse


Status = str


@dataclass
class DoctorOptions:
    """Configuration for a doctor run."""

    device_type: str = "ios"
    base_url: str = "http://localhost:8000/v1"
    api_key: str = "EMPTY"
    model_name: str = "autoglm-phone-9b"
    wda_url: str = "http://localhost:8100"
    device_id: str | None = None
    check_model: bool = True


@dataclass
class DoctorCheck:
    """Single diagnostic check result."""

    name: str
    status: Status
    detail: str
    hint: str | None = None


@dataclass
class DoctorReport:
    """Collection of diagnostic check results."""

    checks: list[DoctorCheck] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return all(check.status != "fail" for check in self.checks)

    def add(self, name: str, status: Status, detail: str, hint: str | None = None) -> None:
        self.checks.append(DoctorCheck(name, status, detail, hint))


def run_doctor(options: DoctorOptions) -> DoctorReport:
    """Run all diagnostics and return a report."""

    report = DoctorReport()

    _check_python(report)
    _check_packages(report)
    _check_configuration(report, options)
    _check_device_tools(report, options)

    if options.device_type == "ios":
        _check_ios_devices(report)
        _check_wda(report, options)
    elif options.device_type == "adb":
        _check_adb_devices(report)
    elif options.device_type == "hdc":
        _check_hdc_devices(report)
    else:
        report.add(
            "Device type",
            "fail",
            f"Unsupported device type: {options.device_type}",
            "Use one of: adb, hdc, ios.",
        )

    if options.check_model:
        _check_model_api(report, options)
    else:
        report.add("Model API", "warn", "Skipped by --doctor-skip-model.")

    return report


def print_doctor_report(report: DoctorReport) -> None:
    """Print a human-readable report."""

    print("=" * 60)
    print("BetterGLM Doctor")
    print("=" * 60)

    for check in report.checks:
        marker = {"ok": "[OK]", "warn": "[WARN]", "fail": "[FAIL]"}.get(
            check.status, "[INFO]"
        )
        print(f"{marker} {check.name}: {check.detail}")
        if check.hint:
            print(f"      Hint: {check.hint}")

    print("-" * 60)
    if report.ok:
        print("[OK] Doctor finished without blocking failures.")
    else:
        print("[FAIL] Doctor found blocking issues. Fix them before running tasks.")


def _check_python(report: DoctorReport) -> None:
    version = sys.version_info
    detail = f"Python {platform.python_version()} at {sys.executable}"
    if version >= (3, 10):
        report.add("Python", "ok", detail)
    else:
        report.add("Python", "fail", detail, "Use Python 3.10 or newer.")


def _check_packages(report: DoctorReport) -> None:
    required = {
        "PIL": "Pillow",
        "openai": "openai",
        "requests": "requests",
    }
    missing = [
        package_name
        for module_name, package_name in required.items()
        if importlib.util.find_spec(module_name) is None
    ]
    if missing:
        report.add(
            "Python packages",
            "fail",
            f"Missing required packages: {', '.join(missing)}",
            "Run: pip install -r requirements.txt",
        )
    else:
        report.add("Python packages", "ok", "Required packages are installed.")

    if importlib.util.find_spec("prompt_toolkit") is None:
        report.add(
            "Interactive input",
            "warn",
            "prompt_toolkit is not installed; CLI falls back to basic input.",
            "Run: pip install prompt_toolkit for better Chinese editing/history.",
        )
    else:
        report.add("Interactive input", "ok", "prompt_toolkit is installed.")


def _check_configuration(report: DoctorReport, options: DoctorOptions) -> None:
    env_path = os.path.abspath(".env")
    if os.path.exists(env_path):
        report.add(".env", "ok", f"Loaded from {env_path}")
    else:
        report.add(
            ".env",
            "warn",
            "No .env file found in the current directory.",
            "Environment variables or CLI flags can still provide configuration.",
        )

    report.add("Device type", "ok", options.device_type)
    if options.device_id:
        report.add("Device ID", "ok", options.device_id)

    report.add("Model config", "ok", f"{options.model_name} @ {options.base_url}")

    if not options.api_key or options.api_key == "EMPTY":
        status = "warn"
        hint = "This is fine for some local servers, but hosted APIs usually need a real key."
        report.add("API key", status, "EMPTY", hint)
    else:
        report.add("API key", "ok", _mask_secret(options.api_key))

    if options.device_type == "ios":
        report.add("WDA URL", "ok", options.wda_url)


def _check_device_tools(report: DoctorReport, options: DoctorOptions) -> None:
    if options.device_type == "ios":
        _check_tool(report, "xcodebuild", "Xcode command line tools")
        _check_tool(report, "idevice_id", "libimobiledevice", warn_only=True)
        _check_tool(report, "iproxy", "libimobiledevice iproxy", warn_only=True)
    elif options.device_type == "adb":
        _check_tool(report, "adb", "Android Debug Bridge")
    elif options.device_type == "hdc":
        _check_tool(report, "hdc", "HarmonyOS Device Connector")


def _check_ios_devices(report: DoctorReport) -> None:
    if shutil.which("idevice_id") is None:
        report.add(
            "iOS devices",
            "warn",
            "idevice_id is unavailable, so USB/pairing devices were not listed.",
            "Install libimobiledevice for USB diagnostics.",
        )
        return

    try:
        result = subprocess.run(
            ["idevice_id", "-ln"],
            capture_output=True,
            text=True,
            timeout=5,
        )
    except subprocess.TimeoutExpired:
        report.add("iOS devices", "warn", "idevice_id timed out.")
        return

    devices = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    if devices:
        short_ids = ", ".join(_short_id(device) for device in devices[:3])
        extra = "" if len(devices) <= 3 else f" (+{len(devices) - 3} more)"
        report.add("iOS devices", "ok", f"{len(devices)} device(s): {short_ids}{extra}")
    else:
        report.add(
            "iOS devices",
            "warn",
            "No USB/paired device found by idevice_id.",
            "WiFi WDA can still work if the WDA URL is reachable.",
        )


def _check_wda(report: DoctorReport, options: DoctorOptions) -> None:
    status = _fetch_wda_status(options.wda_url)
    if status[0]:
        payload = status[1]
        value = payload.get("value", {}) if isinstance(payload, dict) else {}
        state = value.get("state") or "ready"
        device_ip = value.get("ios", {}).get("ip")
        detail = f"Ready at {options.wda_url}"
        if device_ip:
            detail += f" (device IP: {device_ip})"
        report.add("WebDriverAgent", "ok", detail)
        if state != "success":
            report.add("WDA state", "warn", str(state))
        return

    hint = status[1]
    parsed = urlparse(options.wda_url)
    if parsed.hostname not in {"localhost", "127.0.0.1"}:
        localhost_status = _fetch_wda_status("http://localhost:8100")
        if localhost_status[0]:
            hint = (
                "USB forwarding works at localhost:8100, but WiFi WDA is not reachable. "
                "Check iOS Local Network permission, VPN, router isolation, or WDA reinstall."
            )

    report.add("WebDriverAgent", "fail", f"Not reachable at {options.wda_url}", hint)


def _check_adb_devices(report: DoctorReport) -> None:
    if shutil.which("adb") is None:
        return
    try:
        result = subprocess.run(["adb", "devices"], capture_output=True, text=True, timeout=5)
    except subprocess.TimeoutExpired:
        report.add("ADB devices", "fail", "adb devices timed out.")
        return

    devices = [
        line.split()[0]
        for line in result.stdout.splitlines()[1:]
        if line.strip() and "\tdevice" in line
    ]
    if devices:
        report.add("ADB devices", "ok", f"{len(devices)} device(s): {', '.join(devices[:3])}")
    else:
        report.add("ADB devices", "fail", "No authorized Android devices found.")


def _check_hdc_devices(report: DoctorReport) -> None:
    if shutil.which("hdc") is None:
        return
    try:
        result = subprocess.run(
            ["hdc", "list", "targets"], capture_output=True, text=True, timeout=5
        )
    except subprocess.TimeoutExpired:
        report.add("HDC devices", "fail", "hdc list targets timed out.")
        return

    devices = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    if devices:
        report.add("HDC devices", "ok", f"{len(devices)} target(s): {', '.join(devices[:3])}")
    else:
        report.add("HDC devices", "fail", "No HarmonyOS devices found.")


def _check_model_api(report: DoctorReport, options: DoctorOptions) -> None:
    try:
        from openai import OpenAI

        client = OpenAI(base_url=options.base_url, api_key=options.api_key, timeout=8.0)
        models_response = client.models.list()
        available_models = [model.id for model in models_response.data]
    except Exception as e:
        report.add(
            "Model API",
            "fail",
            f"Cannot reach {options.base_url}: {e}",
            "Check PHONE_AGENT_BASE_URL, PHONE_AGENT_API_KEY, network, and model service status.",
        )
        return

    if options.model_name in available_models:
        report.add("Model API", "ok", f"Model is available: {options.model_name}")
    else:
        sample = ", ".join(available_models[:5]) or "no models returned"
        report.add(
            "Model API",
            "warn",
            f"Connected, but model '{options.model_name}' was not listed.",
            f"Available sample: {sample}",
        )


def _check_tool(
    report: DoctorReport, tool_name: str, label: str, warn_only: bool = False
) -> None:
    path = shutil.which(tool_name)
    if path:
        report.add(label, "ok", f"{tool_name} found at {path}")
        return

    status = "warn" if warn_only else "fail"
    report.add(label, status, f"{tool_name} not found in PATH.")


def _fetch_wda_status(url: str) -> tuple[bool, dict | str]:
    try:
        import requests

        response = requests.get(f"{url.rstrip('/')}/status", timeout=5)
        if response.status_code != 200:
            return False, f"HTTP {response.status_code}: {response.text[:200]}"

        payload = response.json()
        value = payload.get("value", {})
        if value.get("ready") is False:
            return False, json.dumps(payload, ensure_ascii=False)[:300]
        return True, payload
    except Exception as e:
        return False, str(e)


def _mask_secret(value: str) -> str:
    if len(value) <= 8:
        return "*" * len(value)
    return f"{value[:4]}...{value[-4:]}"


def _short_id(value: str) -> str:
    if len(value) <= 16:
        return value
    return f"{value[:8]}...{value[-4:]}"
