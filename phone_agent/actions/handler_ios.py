"""Action handler for iOS automation using WebDriverAgent."""

import time
from dataclasses import dataclass, field
from typing import Any, Callable

from phone_agent.coordinate import CoordinateAudit, CoordinateMapper
from phone_agent.xctest import (
    back,
    double_tap,
    home,
    launch_app,
    long_press,
    swipe,
    tap,
)
from phone_agent.xctest.device import SCALE_FACTOR, get_screen_size
from phone_agent.xctest.input import clear_text, hide_keyboard, type_text


@dataclass
class ActionResult:
    """Result of an action execution."""

    success: bool
    should_finish: bool
    message: str | None = None
    requires_confirmation: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


class IOSActionHandler:
    """
    Handles execution of actions from AI model output for iOS devices.

    Args:
        wda_url: WebDriverAgent URL.
        session_id: Optional WDA session ID.
        confirmation_callback: Optional callback for sensitive action confirmation.
            Should return True to proceed, False to cancel.
        takeover_callback: Optional callback for takeover requests (login, captcha).
    """

    def __init__(
        self,
        wda_url: str = "http://localhost:8100",
        session_id: str | None = None,
        confirmation_callback: Callable[[str], bool] | None = None,
        takeover_callback: Callable[[str], None] | None = None,
    ):
        self.wda_url = wda_url
        self.session_id = session_id
        self.confirmation_callback = confirmation_callback or self._default_confirmation
        self.takeover_callback = takeover_callback or self._default_takeover
        self._target_size: tuple[int, int] | None = None

    def execute(
        self, action: dict[str, Any], screen_width: int, screen_height: int
    ) -> ActionResult:
        """
        Execute an action from the AI model.

        Args:
            action: The action dictionary from the model.
            screen_width: Current screen width in pixels.
            screen_height: Current screen height in pixels.

        Returns:
            ActionResult indicating success and whether to finish.
        """
        action_type = action.get("_metadata")

        if action_type == "finish":
            return ActionResult(
                success=True, should_finish=True, message=action.get("message")
            )

        if action_type != "do":
            return ActionResult(
                success=False,
                should_finish=True,
                message=f"Unknown action type: {action_type}",
            )

        action_name = action.get("action")
        handler_method = self._get_handler(action_name)

        if handler_method is None:
            return ActionResult(
                success=False,
                should_finish=False,
                message=f"Unknown action: {action_name}",
            )

        try:
            return handler_method(action, screen_width, screen_height)
        except Exception as e:
            return ActionResult(
                success=False, should_finish=False, message=f"Action failed: {e}"
            )

    def _get_handler(self, action_name: str) -> Callable | None:
        """Get the handler method for an action."""
        handlers = {
            "Launch": self._handle_launch,
            "Tap": self._handle_tap,
            "Type": self._handle_type,
            "Type_Name": self._handle_type,
            "Swipe": self._handle_swipe,
            "Back": self._handle_back,
            "Home": self._handle_home,
            "Double Tap": self._handle_double_tap,
            "Long Press": self._handle_long_press,
            "Wait": self._handle_wait,
            "Take_over": self._handle_takeover,
            "Note": self._handle_note,
            "Call_API": self._handle_call_api,
            "Interact": self._handle_interact,
        }
        return handlers.get(action_name)

    def _map_coordinate(
        self, element: list[int], screen_width: int, screen_height: int
    ) -> CoordinateAudit:
        """Map model coordinates to WDA-calibrated transport coordinates."""
        target_width, target_height = self._get_target_size()
        return CoordinateMapper(
            screenshot_width=screen_width,
            screenshot_height=screen_height,
            target_width=target_width,
            target_height=target_height,
            transport_scale=SCALE_FACTOR,
            strategy="wda_window_calibrated",
        ).map(element)

    def _get_target_size(self) -> tuple[int, int]:
        if self._target_size is None:
            self._target_size = get_screen_size(
                wda_url=self.wda_url, session_id=self.session_id
            )
        return self._target_size

    def _handle_launch(self, action: dict, width: int, height: int) -> ActionResult:
        """Handle app launch action."""
        app_name = action.get("app")
        if not app_name:
            return ActionResult(False, False, "No app name specified")

        success = launch_app(
            app_name, wda_url=self.wda_url, session_id=self.session_id
        )
        if success:
            return ActionResult(True, False)
        return ActionResult(False, False, f"App not found: {app_name}")

    def _handle_tap(self, action: dict, width: int, height: int) -> ActionResult:
        """Handle tap action."""
        element = action.get("element")
        if not element:
            return ActionResult(False, False, "No element coordinates")

        coordinate = self._map_coordinate(element, width, height)
        x, y = coordinate.transport_coordinate

        print(
            "Physically tap on "
            f"{coordinate.target_point or coordinate.transport_coordinate} "
            f"via {coordinate.transport_coordinate}"
        )

        # Check for sensitive operation
        if "message" in action:
            if not self.confirmation_callback(action["message"]):
                return ActionResult(
                    success=False,
                    should_finish=True,
                    message="User cancelled sensitive operation",
                )

        tap(x, y, wda_url=self.wda_url, session_id=self.session_id)
        return ActionResult(True, False, metadata={"coordinate": coordinate.to_dict()})

    def _handle_type(self, action: dict, width: int, height: int) -> ActionResult:
        """Handle text input action."""
        text = action.get("text", "")

        # Clear existing text and type new text
        clear_text(wda_url=self.wda_url, session_id=self.session_id)
        time.sleep(0.5)

        type_text(text, wda_url=self.wda_url, session_id=self.session_id)
        time.sleep(0.5)

        # Hide keyboard after typing
        hide_keyboard(wda_url=self.wda_url, session_id=self.session_id)
        time.sleep(0.5)

        return ActionResult(True, False)

    def _handle_swipe(self, action: dict, width: int, height: int) -> ActionResult:
        """Handle swipe action."""
        start = action.get("start")
        end = action.get("end")

        if not start or not end:
            return ActionResult(False, False, "Missing swipe coordinates")

        start_coordinate = self._map_coordinate(start, width, height)
        end_coordinate = self._map_coordinate(end, width, height)
        start_x, start_y = start_coordinate.transport_coordinate
        end_x, end_y = end_coordinate.transport_coordinate

        print(
            "Physically scroll from "
            f"{start_coordinate.target_point or start_coordinate.transport_coordinate} "
            f"to {end_coordinate.target_point or end_coordinate.transport_coordinate}"
        )

        swipe(
            start_x,
            start_y,
            end_x,
            end_y,
            wda_url=self.wda_url,
            session_id=self.session_id,
        )
        return ActionResult(
            True,
            False,
            metadata={
                "start_coordinate": start_coordinate.to_dict(),
                "end_coordinate": end_coordinate.to_dict(),
            },
        )

    def _handle_back(self, action: dict, width: int, height: int) -> ActionResult:
        """Handle back gesture (swipe from left edge)."""
        back(wda_url=self.wda_url, session_id=self.session_id)
        return ActionResult(True, False)

    def _handle_home(self, action: dict, width: int, height: int) -> ActionResult:
        """Handle home button action."""
        home(wda_url=self.wda_url, session_id=self.session_id)
        return ActionResult(True, False)

    def _handle_double_tap(self, action: dict, width: int, height: int) -> ActionResult:
        """Handle double tap action."""
        element = action.get("element")
        if not element:
            return ActionResult(False, False, "No element coordinates")

        coordinate = self._map_coordinate(element, width, height)
        x, y = coordinate.transport_coordinate
        double_tap(x, y, wda_url=self.wda_url, session_id=self.session_id)
        return ActionResult(True, False, metadata={"coordinate": coordinate.to_dict()})

    def _handle_long_press(self, action: dict, width: int, height: int) -> ActionResult:
        """Handle long press action."""
        element = action.get("element")
        if not element:
            return ActionResult(False, False, "No element coordinates")

        coordinate = self._map_coordinate(element, width, height)
        x, y = coordinate.transport_coordinate
        long_press(
            x,
            y,
            duration=3.0,
            wda_url=self.wda_url,
            session_id=self.session_id,
        )
        return ActionResult(True, False, metadata={"coordinate": coordinate.to_dict()})

    def _handle_wait(self, action: dict, width: int, height: int) -> ActionResult:
        """Handle wait action."""
        duration_str = action.get("duration", "1 seconds")
        try:
            duration = float(duration_str.replace("seconds", "").strip())
        except ValueError:
            duration = 1.0

        time.sleep(duration)
        return ActionResult(True, False)

    def _handle_takeover(self, action: dict, width: int, height: int) -> ActionResult:
        """Handle takeover request (login, captcha, etc.)."""
        message = action.get("message", "User intervention required")
        self.takeover_callback(message)
        return ActionResult(True, False)

    def _handle_note(self, action: dict, width: int, height: int) -> ActionResult:
        """Handle note action (placeholder for content recording)."""
        # This action is typically used for recording page content
        # Implementation depends on specific requirements
        return ActionResult(True, False)

    def _handle_call_api(self, action: dict, width: int, height: int) -> ActionResult:
        """Handle API call action (placeholder for summarization)."""
        # This action is typically used for content summarization
        # Implementation depends on specific requirements
        return ActionResult(True, False)

    def _handle_interact(self, action: dict, width: int, height: int) -> ActionResult:
        """Handle interaction request (user choice needed)."""
        # This action signals that user input is needed
        return ActionResult(True, False, message="User interaction required")

    @staticmethod
    def _default_confirmation(message: str) -> bool:
        """Default confirmation callback using console input."""
        response = input(f"Sensitive operation: {message}\nConfirm? (Y/N): ")
        return response.upper() == "Y"

    @staticmethod
    def _default_takeover(message: str) -> None:
        """Default takeover callback using console input."""
        input(f"{message}\nPress Enter after completing manual operation...")
