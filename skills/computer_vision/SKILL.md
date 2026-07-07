# Computer Vision

## Name
Computer Vision

## Description
Last-resort fallback tier. Takes a screenshot, scans it with OpenCV template matching to locate a target icon/button, then drives the mouse cursor with Bezier-interpolated paths and clicks.

## When to use it
- When Terminal and Web Bridge cannot reach the target
- Legacy desktop applications
- Games or locked-down OS settings
- Any UI element that does not expose ARIA roles or command-line access

## Tools

### `computer_vision.click_target`
Find a template image on screen and click it.

```json
{
  "tool": "computer_vision.click_target",
  "arguments": {
    "template_image": "string (filename.png)",
    "dpi_scaling_factor": "float (optional, default 1.0)",
    "confidence_threshold": "float (optional, default 0.8)"
  }
}
```

- If confidence_threshold is not met, returns BLOCKED — never guesses a location.
- Respects `HumanOverride.is_overridden()` before and during cursor movement.
- Bezier-interpolated cursor paths for natural-looking motion.

### `computer_vision.track_target`
Continuously track a moving target on screen.

```json
{
  "tool": "computer_vision.track_target",
  "arguments": {
    "template_image": "string (filename.png)",
    "confidence_threshold": "float (optional, default 0.8)",
    "max_duration_seconds": "integer (optional, default 30)"
  }
}
```

- Auto-times-out after max_duration_seconds.
- Respects HumanOverride throughout.

## Resource Cost
Heavy. Requires `opencv-python`, `pyautogui`, `mss`, `numpy`. Lazily imported — only loaded when this tier activates. RAM footprint: 400-500 MB transiently while active. Never loaded at startup.
