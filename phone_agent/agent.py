"""Main PhoneAgent class for orchestrating phone automation."""

import json
import traceback
from dataclasses import dataclass
from typing import Any, Callable

from phone_agent.actions import ActionHandler
from phone_agent.actions.handler import do, finish, parse_action
from phone_agent.config import get_messages, get_system_prompt
from phone_agent.device_factory import get_device_factory
from phone_agent.model import ModelClient, ModelConfig
from phone_agent.model.client import MessageBuilder
from phone_agent.replay import ReplayRecorder


@dataclass
class AgentConfig:
    """Configuration for the PhoneAgent."""

    max_steps: int = 100
    device_id: str | None = None
    device_type: str = "phone"
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


class PhoneAgent:
    """
    AI-powered agent for automating Android phone interactions.

    The agent uses a vision-language model to understand screen content
    and decide on actions to complete user tasks.

    Args:
        model_config: Configuration for the AI model.
        agent_config: Configuration for the agent behavior.
        confirmation_callback: Optional callback for sensitive action confirmation.
        takeover_callback: Optional callback for takeover requests.

    Example:
        >>> from phone_agent import PhoneAgent
        >>> from phone_agent.model import ModelConfig
        >>>
        >>> model_config = ModelConfig(base_url="http://localhost:8000/v1")
        >>> agent = PhoneAgent(model_config)
        >>> agent.run("Open WeChat and send a message to John")
    """

    def __init__(
        self,
        model_config: ModelConfig | None = None,
        agent_config: AgentConfig | None = None,
        confirmation_callback: Callable[[str], bool] | None = None,
        takeover_callback: Callable[[str], None] | None = None,
    ):
        self.model_config = model_config or ModelConfig()
        self.agent_config = agent_config or AgentConfig()

        self.model_client = ModelClient(self.model_config)
        self.action_handler = ActionHandler(
            device_id=self.agent_config.device_id,
            confirmation_callback=confirmation_callback,
            takeover_callback=takeover_callback,
        )

        self._context: list[dict[str, Any]] = []
        self._step_count = 0
        self._replay_recorder: ReplayRecorder | None = None

    def run(self, task: str) -> str:
        """
        Run the agent to complete a task.

        Args:
            task: Natural language description of the task.

        Returns:
            Final message from the agent.
        """
        self._context = []
        self._step_count = 0
        self._start_replay(task)

        # First step with user prompt
        result = self._execute_step(task, is_first=True)

        if result.finished:
            final_message = result.message or "Task completed"
            self._finish_replay(final_message)
            return final_message

        # Continue until finished or max steps reached
        while self._step_count < self.agent_config.max_steps:
            result = self._execute_step(is_first=False)

            if result.finished:
                final_message = result.message or "Task completed"
                self._finish_replay(final_message)
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

    def _execute_step(
        self, user_prompt: str | None = None, is_first: bool = False
    ) -> StepResult:
        """Execute a single step of the agent loop."""
        self._step_count += 1

        # Capture current screen state
        device_factory = get_device_factory()
        screenshot = device_factory.get_screenshot(self.agent_config.device_id)
        current_app = device_factory.get_current_app(self.agent_config.device_id)

        # Build messages
        if is_first:
            self._context.append(
                MessageBuilder.create_system_message(self.agent_config.system_prompt)
            )

            screen_info = MessageBuilder.build_screen_info(current_app)
            text_content = f"{user_prompt}\n\n{screen_info}"

            self._context.append(
                MessageBuilder.create_user_message(
                    text=text_content, image_base64=screenshot.base64_data
                )
            )
        else:
            screen_info = MessageBuilder.build_screen_info(current_app)
            text_content = f"** Screen Info **\n\n{screen_info}"

            self._context.append(
                MessageBuilder.create_user_message(
                    text=text_content, image_base64=screenshot.base64_data
                )
            )

        # Get model response
        try:
            msgs = get_messages(self.agent_config.lang)
            print("\n" + "=" * 50)
            print(f"💭 {msgs['thinking']}:")
            print("-" * 50)
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
            )

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
            print("-" * 50)
            print(f"🎯 {msgs['action']}:")
            print(json.dumps(action, ensure_ascii=False, indent=2))
            print("=" * 50 + "\n")

        # Remove image from context to save space
        self._context[-1] = MessageBuilder.remove_images_from_message(self._context[-1])

        # Execute action
        execution_error = None
        try:
            result = self.action_handler.execute(
                action, screenshot.width, screenshot.height
            )
        except Exception as e:
            if self.agent_config.verbose:
                traceback.print_exc()
            execution_error = str(e)
            result = self.action_handler.execute(
                finish(message=str(e)), screenshot.width, screenshot.height
            )

        # Add assistant response to context
        self._context.append(
            MessageBuilder.create_assistant_message(
                f"<think>{response.thinking}</think><answer>{response.action}</answer>"
            )
        )

        # Check if finished
        finished = action.get("_metadata") == "finish" or result.should_finish
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
            error=execution_error,
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
            device_type=self.agent_config.device_type,
            model_name=self.model_config.model_name,
            config={
                "device_id": self.agent_config.device_id,
                "max_steps": self.agent_config.max_steps,
            },
        )

    def _finish_replay(self, result: str, status: str = "completed") -> None:
        if self._replay_recorder is not None:
            self._replay_recorder.finish(result, status=status)

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
