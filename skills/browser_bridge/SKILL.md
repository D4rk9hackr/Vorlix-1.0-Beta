# Browser Bridge

## Name
Browser Bridge

## Description
Controls web pages via ARIA roles and visible text content. Uses a Chrome extension with native messaging to interact directly inside a webpage's DOM.

## When to use it
- Filling web forms
- Clicking buttons or links on web pages
- Extracting text content from pages
- Any web-based task where DOM access is faster than CV

## Tools

### `browser_controls.interact`
Interacts with a page element identified by ARIA role and visible text.

```json
{
  "tool": "browser_controls.interact",
  "arguments": {
    "aria_role": "string",
    "target_text": "string",
    "action_type": "click | type | hover | extract",
    "input_value": "string (optional)"
  }
}
```

- Anchors on ARIA roles and visible text, not brittle CSS selectors.
- Every action shows a visible on-page highlight indicator.
- Requires the Vorlix Web Bridge extension to be installed in the browser.

## Resource Cost
Lightweight on the Python side. The extension runs in the browser. RAM footprint: <20 MB on the Python side.
