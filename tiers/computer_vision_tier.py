"""Computer Vision tier — screen capture + template matching + mouse control."""
import asyncio
import gc
import math
import time
from typing import Optional

from core.tier_base import AutomationTier, TierRequest, TierResponse, TierResult
from core.human_override import HumanOverride


class ComputerVisionTier(AutomationTier):
    """Last-resort tier: screen capture, template matching, cursor movement."""

    def __init__(self):
        super().__init__("ComputerVisionTier")
        self._human_override = HumanOverride()
        self._cv2 = None
        self._pyautogui = None
        self._mss = None
        self._np = None
        self._loaded = False

    def _lazy_imports(self):
        if self._loaded:
            return
        import importlib
        self._cv2 = importlib.import_module("cv2")
        self._pyautogui = importlib.import_module("pyautogui")
        self._mss = importlib.import_module("mss")
        self._np = importlib.import_module("numpy")
        self._loaded = True

    def is_within_guardrails(self, request: TierRequest) -> bool:
        return True

    async def execute(self, request: TierRequest) -> TierResponse:
        tool = request.tool
        args = request.arguments

        try:
            self._lazy_imports()
        except ImportError as e:
            return TierResponse(
                result=TierResult.BLOCKED,
                message=f"Missing dependency: {e}. Install with: pip install opencv-python pyautogui mss numpy",
            )

        if tool == "computer_vision.click_target":
            return await self._click_target(args)
        elif tool == "computer_vision.track_target":
            return await self._track_target(args)
        else:
            return TierResponse(
                result=TierResult.BLOCKED,
                message=f"Unknown tool: {tool}",
            )

    def _bezier_path(self, start: tuple, end: tuple, steps: int = 30) -> list:
        """Generate a smooth Bezier-interpolated path from start to end."""
        cx = (start[0] + end[0]) / 2 + (end[1] - start[1]) * 0.1
        cy = (start[1] + end[1]) / 2 - (end[0] - start[0]) * 0.1
        path = []
        for i in range(steps + 1):
            t = i / steps
            mt = 1 - t
            x = mt * mt * start[0] + 2 * mt * t * cx + t * t * end[0]
            y = mt * mt * start[1] + 2 * mt * t * cy + t * t * end[1]
            path.append((int(x), int(y)))
        return path

    def _move_mouse_bezier(self, x: int, y: int, duration: float = 0.3):
        """Move mouse with Bezier interpolation."""
        start = self._pyautogui.position()
        path = self._bezier_path(start, (x, y))
        step_time = duration / len(path)
        for px, py in path:
            if self._human_override.is_overridden():
                return False
            self._pyautogui.moveTo(px, py, duration=step_time)
        return True

    async def _click_target(self, args: dict) -> TierResponse:
        self._lazy_imports()

        template_name = args.get("template_image", "")
        dpi_factor = args.get("dpi_scaling_factor", 1.0)
        confidence_threshold = args.get("confidence_threshold", 0.8)

        if not template_name:
            return TierResponse(
                result=TierResult.BLOCKED,
                message="No template_image provided.",
            )

        try:
            with self._mss.mss() as sct:
                screenshot = self._np.array(sct.grab(sct.monitors[0]))
                frame = self._cv2.cvtColor(screenshot, self._cv2.COLOR_BGRA2GRAY)

            template = self._cv2.imread(template_name, self._cv2.IMREAD_GRAYSCALE)
            if template is None:
                return TierResponse(
                    result=TierResult.BLOCKED,
                    message=f"Template image not found: {template_name}",
                )

            result = self._cv2.matchTemplate(frame, template, self._cv2.TM_CCOEFF_NORMED)
            _, max_val, _, max_loc = self._cv2.minMaxLoc(result)

            if max_val < confidence_threshold:
                return TierResponse(
                    result=TierResult.BLOCKED,
                    message=f"Target not found (confidence {max_val:.3f} < {confidence_threshold}).",
                    data={"confidence": float(max_val)},
                )

            h, w = template.shape[:2]
            center_x = int((max_loc[0] + w / 2) * dpi_factor)
            center_y = int((max_loc[1] + h / 2) * dpi_factor)

            if self._human_override.is_overridden():
                return TierResponse(
                    result=TierResult.BLOCKED,
                    message="Human override active — aborting mouse movement.",
                )

            moved = self._move_mouse_bezier(center_x, center_y)
            if not moved:
                return TierResponse(
                    result=TierResult.BLOCKED,
                    message="Human override activated during cursor movement.",
                )

            self._pyautogui.click()

            return TierResponse(
                result=TierResult.SUCCESS,
                data={"x": center_x, "y": center_y, "confidence": float(max_val)},
                message=f"Clicked target at ({center_x}, {center_y}) with confidence {max_val:.3f}.",
            )
        except ImportError as e:
            return TierResponse(
                result=TierResult.BLOCKED,
                message=f"Missing dependency: {e}. Install with: pip install opencv-python pyautogui mss numpy",
            )
        finally:
            if self._loaded:
                del frame, template, result, screenshot
                gc.collect()

    async def _track_target(self, args: dict) -> TierResponse:
        self._lazy_imports()

        template_name = args.get("template_image", "")
        confidence_threshold = args.get("confidence_threshold", 0.8)
        max_duration = args.get("max_duration_seconds", 30)

        if not template_name:
            return TierResponse(
                result=TierResult.BLOCKED,
                message="No template_image provided.",
            )

        template = self._cv2.imread(template_name, self._cv2.IMREAD_GRAYSCALE)
        if template is None:
            return TierResponse(
                result=TierResult.BLOCKED,
                message=f"Template image not found: {template_name}",
            )

        h, w = template.shape[:2]
        start_time = time.time()
        tracker = None
        tracking = False

        try:
            while time.time() - start_time < max_duration:
                if self._human_override.is_overridden():
                    return TierResponse(
                        result=TierResult.BLOCKED,
                        message="Human override active — aborting tracking.",
                    )

                with self._mss.mss() as sct:
                    frame_rgb = self._np.array(sct.grab(sct.monitors[0]))
                    frame = self._cv2.cvtColor(frame_rgb, self._cv2.COLOR_BGRA2GRAY)

                if not tracking:
                    result = self._cv2.matchTemplate(frame, template, self._cv2.TM_CCOEFF_NORMED)
                    _, max_val, _, max_loc = self._cv2.minMaxLoc(result)
                    if max_val >= confidence_threshold:
                        tracker = self._cv2.TrackerCSRT.create()
                        tracker.init(frame_rgb, (max_loc[0], max_loc[1], w, h))
                        tracking = True
                    else:
                        await asyncio.sleep(0.5)
                        continue

                success, box = tracker.update(frame_rgb)
                if success:
                    x, y, bw, bh = [int(v) for v in box]
                    center_x = x + bw // 2
                    center_y = y + bh // 2

                    if self._human_override.is_overridden():
                        return TierResponse(
                            result=TierResult.BLOCKED,
                            message="Human override activated during tracking.",
                        )

                    moved = self._move_mouse_bezier(center_x, center_y)
                    if not moved:
                        return TierResponse(
                            result=TierResult.BLOCKED,
                            message="Human override activated during cursor movement.",
                        )

                await asyncio.sleep(0.05)

            return TierResponse(
                result=TierResult.SUCCESS,
                data={"duration": time.time() - start_time},
                message="Tracking completed.",
            )
        except ImportError as e:
            return TierResponse(
                result=TierResult.BLOCKED,
                message=f"Missing dependency: {e}",
            )
        finally:
            del frame, template
            gc.collect()
