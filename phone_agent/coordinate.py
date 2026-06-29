"""Coordinate mapping and audit utilities for touch actions."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class CoordinateAudit:
    """Trace how a model coordinate becomes a physical touch coordinate."""

    model_coordinate: list[float]
    screenshot_size: dict[str, int]
    screenshot_pixel: list[int]
    target_size: dict[str, int] | None
    target_point: list[int] | None
    transport_coordinate: list[int]
    strategy: str
    clamped: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class CoordinateMapper:
    """Map model 0-1000 coordinates to device touch coordinates."""

    def __init__(
        self,
        *,
        screenshot_width: int,
        screenshot_height: int,
        target_width: int | None = None,
        target_height: int | None = None,
        transport_scale: float = 1.0,
        strategy: str = "screenshot_pixels",
    ):
        self.screenshot_width = int(screenshot_width)
        self.screenshot_height = int(screenshot_height)
        self.target_width = int(target_width) if target_width else None
        self.target_height = int(target_height) if target_height else None
        self.transport_scale = float(transport_scale)
        self.strategy = strategy

        if self.screenshot_width <= 0 or self.screenshot_height <= 0:
            raise ValueError("Screenshot dimensions must be positive")

    def map(self, element: list[int | float]) -> CoordinateAudit:
        """Map one model coordinate pair and return a full audit trail."""

        x_raw, y_raw = _validate_element(element)
        x_norm, x_clamped = _clamp(x_raw, 0.0, 1000.0)
        y_norm, y_clamped = _clamp(y_raw, 0.0, 1000.0)

        screenshot_x = _scale(x_norm, self.screenshot_width)
        screenshot_y = _scale(y_norm, self.screenshot_height)

        if self.target_width and self.target_height:
            target_x = _scale(x_norm, self.target_width)
            target_y = _scale(y_norm, self.target_height)
            transport_x = _clamp_int(
                round(target_x * self.transport_scale), 0, self.screenshot_width - 1
            )
            transport_y = _clamp_int(
                round(target_y * self.transport_scale), 0, self.screenshot_height - 1
            )
            target_point: list[int] | None = [target_x, target_y]
            target_size: dict[str, int] | None = {
                "width": self.target_width,
                "height": self.target_height,
            }
        else:
            transport_x = screenshot_x
            transport_y = screenshot_y
            target_point = None
            target_size = None

        return CoordinateAudit(
            model_coordinate=[x_raw, y_raw],
            screenshot_size={
                "width": self.screenshot_width,
                "height": self.screenshot_height,
            },
            screenshot_pixel=[screenshot_x, screenshot_y],
            target_size=target_size,
            target_point=target_point,
            transport_coordinate=[transport_x, transport_y],
            strategy=self.strategy,
            clamped=x_clamped or y_clamped,
        )


def _validate_element(element: list[int | float]) -> tuple[float, float]:
    if not isinstance(element, list) or len(element) != 2:
        raise ValueError(f"Coordinate must be a two-item list, got: {element}")
    try:
        return float(element[0]), float(element[1])
    except (TypeError, ValueError) as e:
        raise ValueError(f"Coordinate values must be numeric, got: {element}") from e


def _scale(value: float, size: int) -> int:
    return _clamp_int(round(value / 1000.0 * (size - 1)), 0, size - 1)


def _clamp(value: float, minimum: float, maximum: float) -> tuple[float, bool]:
    clamped = min(max(value, minimum), maximum)
    return clamped, clamped != value


def _clamp_int(value: int, minimum: int, maximum: int) -> int:
    return min(max(value, minimum), maximum)
