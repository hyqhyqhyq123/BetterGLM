"""iOS PhoneAgent class for orchestrating iOS phone automation."""

import json
import threading
import traceback
from dataclasses import dataclass
from typing import Any, Callable

from phone_agent.actions.handler import parse_action
from phone_agent.actions.handler_ios import ActionResult, IOSActionHandler
from phone_agent.config import get_messages, get_system_prompt
from phone_agent.model import ModelClient, ModelConfig
from phone_agent.model.client import MessageBuilder
from phone_agent.loop_guard import AgentLoopGuard
from phone_agent.replay import ReplayRecorder
from phone_agent.xctest import XCTestConnection, get_current_app, get_screenshot


@dataclass
class IOSAgentConfig:
    """Configuration for the iOS PhoneAgent."""

    max_steps: int = 100
    wda_url: str = "http://localhost:8100"
    session_id: str | None = None
    device_id: str | None = None  # iOS device UDID
    lang: str = "cn"
    system_prompt: str | None = None
    verbose: bool = True
    replay_dir: str | None = None

    def __post_init__(self):
        if self.system_prompt is None:
            self.system_prompt = get_system_prompt(self.lang)


@dataclass
class StepResult:
    """Result of a single agent step."""

    success: bool
    finished: bool
    action: dict[str, Any] | None
    thinking: str
    message: str | None = None
    status: str | None = None


class IOSPhoneAgent:
    """
    AI-powered agent for automating iOS phone interactions.

    The agent uses a vision-language model to understand screen content
    and decide on actions to complete user tasks via WebDriverAgent.

    Args:
        model_config: Configuration for the AI model.
        agent_config: Configuration for the iOS agent behavior.
        confirmation_callback: Optional callback for sensitive action confirmation.
        takeover_callback: Optional callback for takeover requests.

    Example:
        >>> from phone_agent.agent_ios import IOSPhoneAgent, IOSAgentConfig
        >>> from phone_agent.model import ModelConfig
        >>>
        >>> model_config = ModelConfig(base_url="http://localhost:8000/v1")
        >>> agent_config = IOSAgentConfig(wda_url="http://localhost:8100")
        >>> agent = IOSPhoneAgent(model_config, agent_config)
        >>> agent.run("Open Safari and search for Apple")
    """

    def __init__(
        self,
        model_config: ModelConfig | None = None,
        agent_config: IOSAgentConfig | None = None,
        confirmation_callback: Callable[[str], bool] | None = None,
        takeover_callback: Callable[[str], None] | None = None,
    ):
        self.model_config = model_config or ModelConfig()
        self.agent_config = agent_config or IOSAgentConfig()

        self.model_client = ModelClient(self.model_config)

        # Initialize WDA connection and create session if needed
        self.wda_connection = XCTestConnection(wda_url=self.agent_config.wda_url)
        self._wda_ready_at_startup = self.wda_connection.is_wda_ready(timeout=2)

        # Auto-create session if not provided
        if self.agent_config.session_id is None and self._wda_ready_at_startup:
            success, session_id = self.wda_connection.start_wda_session()
            if success and session_id != "session_started":
                self.agent_config.session_id = session_id
                if self.agent_config.verbose:
                    print(f"✅ Created WDA session: {session_id}")
            elif self.agent_config.verbose:
                print(f"⚠️  Using default WDA session (no explicit session ID)")
        elif self.agent_config.session_id is None and self.agent_config.verbose:
            print(f"⚠️  WebDriverAgent is not reachable: {self.agent_config.wda_url}")

        self.action_handler = IOSActionHandler(
            wda_url=self.agent_config.wda_url,
            session_id=self.agent_config.session_id,
            confirmation_callback=confirmation_callback,
            takeover_callback=takeover_callback,
        )

        self._context: list[dict[str, Any]] = []
        self._step_count = 0
        self._replay_recorder: ReplayRecorder | None = None
        self._loop_guard = AgentLoopGuard()
        self._cancel_requested = threading.Event()

    def run(self, task: str, *, preserve_cancel: bool = False) -> str:
        """
        Run the agent to complete a task.

        Args:
            task: Natural language description of the task.
            preserve_cancel: Keep an already requested cancellation when a
                controller asks to stop before the agent loop has started.

        Returns:
            Final message from the agent.
        """
        self._context = []
        self._step_count = 0
        self._loop_guard.reset()
        if not preserve_cancel:
            self._cancel_requested.clear()
        self._start_replay(task)

        if self.is_cancel_requested():
            return self._finish_cancelled_run()
        if not self._is_wda_ready():
            return self._finish_wda_error()

        # First step with user prompt
        result = self._execute_step(task, is_first=True)

        if result.finished:
            final_message = result.message or "Task completed"
            self._finish_replay(
                final_message,
                status=result.status or ("completed" if result.success else "failed"),
            )
            return final_message

        # Continue until finished or max steps reached
        while self._step_count < self.agent_config.max_steps:
            if self.is_cancel_requested():
                return self._finish_cancelled_run()

            result = self._execute_step(is_first=False)

            if result.finished:
                final_message = result.message or "Task completed"
                self._finish_replay(
                    final_message,
                    status=result.status or ("completed" if result.success else "failed"),
                )
                return final_message

        self._finish_replay("Max steps reached", status="max_steps")
        return "Max steps reached"

    def step(self, task: str | None = None) -> StepResult:
        """
        Execute a single step of the agent.

        Useful for manual control or debugging.

        Args:
            task: Task description (only needed for first step).

        Returns:
            StepResult with step details.
        """
        is_first = len(self._context) == 0

        if is_first and not task:
            raise ValueError("Task is required for the first step")

        return self._execute_step(task, is_first)

    def reset(self) -> None:
        """Reset the agent state for a new task."""
        self._context = []
        self._step_count = 0
        self._loop_guard.reset()
        self._cancel_requested.clear()

    def request_cancel(self) -> None:
        """Ask the agent loop to stop at the next safe checkpoint."""
        self._cancel_requested.set()

    def is_cancel_requested(self) -> bool:
        """Return whether a controller requested the current run to stop."""
        return self._cancel_requested.is_set()

    def _execute_step(
        self, user_prompt: str | None = None, is_first: bool = False
    ) -> StepResult:
        """Execute a single step of the agent loop."""
        if self.is_cancel_requested():
            return self._cancelled_step_result()
        if not self._is_wda_ready():
            return self._wda_error_step_result()

        self._step_count += 1

        # Capture current screen state
        screenshot = get_screenshot(
            wda_url=self.agent_config.wda_url,
            session_id=self.agent_config.session_id,
            device_id=self.agent_config.device_id,
        )
        current_app = get_current_app(
            wda_url=self.agent_config.wda_url, session_id=self.agent_config.session_id
        )
        screen_info = MessageBuilder.build_screen_info(current_app)

        if self.is_cancel_requested():
            self._record_cancelled_step(
                current_app=current_app,
                screen_info=screen_info,
                screenshot=screenshot,
            )
            return self._cancelled_step_result()

        # Build messages
        if is_first:
            self._context.append(
                MessageBuilder.create_system_message(self.agent_config.system_prompt)
            )

            text_content = f"{user_prompt}\n\n{screen_info}"

            self._context.append(
                MessageBuilder.create_user_message(
                    text=text_content, image_base64=screenshot.base64_data
                )
            )
        else:
            text_content = f"** Screen Info **\n\n{screen_info}"

            self._context.append(
                MessageBuilder.create_user_message(
                    text=text_content, image_base64=screenshot.base64_data
                )
            )

        if self.is_cancel_requested():
            self._record_cancelled_step(
                current_app=current_app,
                screen_info=screen_info,
                screenshot=screenshot,
            )
            return self._cancelled_step_result()

        # Get model response
        try:
            response = self.model_client.request(self._context)
        except Exception as e:
            if self.agent_config.verbose:
                traceback.print_exc()
            self._record_replay_step(
                current_app=current_app,
                screen_info=screen_info,
                screenshot=screenshot,
                error=f"Model error: {e}",
                message=f"Model error: {e}",
                finished=True,
            )
            return StepResult(
                success=False,
                finished=True,
                action=None,
                thinking="",
                message=f"Model error: {e}",
                status="failed",
            )

        if self.is_cancel_requested():
            self._record_cancelled_step(
                current_app=current_app,
                screen_info=screen_info,
                screenshot=screenshot,
                thinking=response.thinking,
                raw_action=response.action,
                model_metrics=self._model_metrics(response),
            )
            return self._cancelled_step_result()

        # Parse action from response
        try:
            action = parse_action(response.action)
        except ValueError as e:
            if self.agent_config.verbose:
                print(f"⚠️  Failed to parse model action, retrying: {e}")
            self._record_replay_step(
                current_app=current_app,
                screen_info=screen_info,
                screenshot=screenshot,
                thinking=response.thinking,
                raw_action=response.action,
                error=str(e),
                message="Model action parse failed; retrying",
                model_metrics=self._model_metrics(response),
            )

            self._context[-1] = MessageBuilder.remove_images_from_message(
                self._context[-1]
            )
            self._context.append(
                MessageBuilder.create_assistant_message(
                    f"<think>{response.thinking}</think><answer>{response.action}</answer>"
                )
            )
            self._context.append(
                MessageBuilder.create_user_message(
                    text=(
                        "上一次输出的 <answer> 不是可执行动作，系统无法解析。"
                        "请继续完成原任务，并且这次 <answer> 只能输出一个动作调用，"
                        '例如 do(action="Launch", app="微信")、'
                        'do(action="Tap", element=[x,y])、'
                        'do(action="Type", text="xxx") 或 finish(message="xxx")。'
                        "不要在 <answer> 中输出解释性文字。"
                    )
                )
            )
            return StepResult(
                success=False,
                finished=False,
                action=None,
                thinking=response.thinking,
                message=str(e),
            )

        if self.agent_config.verbose:
            # Print thinking process
            msgs = get_messages(self.agent_config.lang)
            print("\n" + "=" * 50)
            print(f"💭 {msgs['thinking']}:")
            print("-" * 50)
            print(response.thinking)
            print("-" * 50)
            print(f"🎯 {msgs['action']}:")
            print(json.dumps(action, ensure_ascii=False, indent=2))
            print("=" * 50 + "\n")

        # Remove image from context to save space
        self._context[-1] = MessageBuilder.remove_images_from_message(self._context[-1])

        if self.is_cancel_requested():
            self._record_cancelled_step(
                current_app=current_app,
                screen_info=screen_info,
                screenshot=screenshot,
                thinking=response.thinking,
                raw_action=response.action,
                parsed_action=action,
                action_result=ActionResult(False, True, _cancel_message()),
                model_metrics=self._model_metrics(response),
            )
            return self._cancelled_step_result()

        # Execute action
        execution_error = None
        repeated_action_message = self._loop_guard.repeated_action_message(action)
        if repeated_action_message:
            execution_error = repeated_action_message
            result = ActionResult(False, True, repeated_action_message)
        else:
            try:
                result = self.action_handler.execute(
                    action, screenshot.width, screenshot.height
                )
            except Exception as e:
                if self.agent_config.verbose:
                    traceback.print_exc()
                execution_error = str(e)
                result = ActionResult(False, True, f"Action failed: {e}")

        # Add assistant response to context
        self._context.append(
            MessageBuilder.create_assistant_message(
                f"<think>{response.thinking}</think><answer>{response.action}</answer>"
            )
        )

        # Check if finished
        terminal_status = self._loop_guard.terminal_failure_status(
            result.success, result.message
        )
        finished = (
            action.get("_metadata") == "finish"
            or result.should_finish
            or terminal_status is not None
        )
        step_error = execution_error or (
            result.message if not result.success and finished else None
        )
        self._record_replay_step(
            current_app=current_app,
            screen_info=screen_info,
            screenshot=screenshot,
            thinking=response.thinking,
            raw_action=response.action,
            parsed_action=action,
            action_result=result,
            finished=finished,
            message=result.message or action.get("message"),
            error=step_error,
            model_metrics=self._model_metrics(response),
        )

        if finished and self.agent_config.verbose:
            msgs = get_messages(self.agent_config.lang)
            print("\n" + "🎉 " + "=" * 48)
            print(
                f"✅ {msgs['task_completed']}: {result.message or action.get('message', msgs['done'])}"
            )
            print("=" * 50 + "\n")

        return StepResult(
            success=result.success,
            finished=finished,
            action=action,
            thinking=response.thinking,
            message=result.message or action.get("message"),
            status=terminal_status or ("failed" if finished and not result.success else None),
        )

    @property
    def context(self) -> list[dict[str, Any]]:
        """Get the current conversation context."""
        return self._context.copy()

    @property
    def step_count(self) -> int:
        """Get the current step count."""
        return self._step_count

    @property
    def replay_path(self) -> str | None:
        """Get the current replay directory path."""
        if self._replay_recorder is None:
            return None
        return str(self._replay_recorder.run_dir)

    def _start_replay(self, task: str) -> None:
        if not self.agent_config.replay_dir:
            self._replay_recorder = None
            return

        self._replay_recorder = ReplayRecorder(
            root_dir=self.agent_config.replay_dir,
            task=task,
            device_type="ios",
            model_name=self.model_config.model_name,
            config={
                "wda_url": self.agent_config.wda_url,
                "device_id": self.agent_config.device_id,
                "max_steps": self.agent_config.max_steps,
            },
        )

    def _finish_replay(self, result: str, status: str = "completed") -> None:
        if self._replay_recorder is not None:
            self._replay_recorder.finish(result, status=status)

    def _finish_cancelled_run(self) -> str:
        message = _cancel_message()
        self._finish_replay(message, status="cancelled")
        return message

    def _finish_wda_error(self) -> str:
        message = self._wda_error_message()
        self._finish_replay(message, status="wda_error")
        return message

    def _cancelled_step_result(self) -> StepResult:
        return StepResult(
            success=False,
            finished=True,
            action=None,
            thinking="",
            message=_cancel_message(),
            status="cancelled",
        )

    def _wda_error_step_result(self) -> StepResult:
        return StepResult(
            success=False,
            finished=True,
            action=None,
            thinking="",
            message=self._wda_error_message(),
            status="wda_error",
        )

    def _record_cancelled_step(self, **kwargs) -> None:
        self._record_replay_step(
            finished=True,
            message=_cancel_message(),
            error=_cancel_message(),
            **kwargs,
        )

    def _is_wda_ready(self) -> bool:
        return self.wda_connection.is_wda_ready(timeout=2)

    def _wda_error_message(self) -> str:
        return (
            "WebDriverAgent is not reachable. "
            f"Check WDA_URL={self.agent_config.wda_url}, Xcode test status, "
            "USB iproxy, or WiFi connectivity."
        )

    def _record_replay_step(self, **kwargs) -> None:
        if self._replay_recorder is not None:
            self._replay_recorder.record_step(
                step_index=self._step_count,
                **kwargs,
            )

    def _model_metrics(self, response) -> dict[str, float | None]:
        return {
            "time_to_first_token": response.time_to_first_token,
            "time_to_thinking_end": response.time_to_thinking_end,
            "total_time": response.total_time,
        }


def _cancel_message() -> str:
    return "Task cancelled by user"
