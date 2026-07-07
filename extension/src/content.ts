/// <reference types="chrome" />

interface InteractRequest {
  action: "interact";
  aria_role: string;
  target_text: string;
  action_type: "click" | "type" | "hover" | "extract";
  input_value?: string;
}

function findElement(role: string, text: string): Element | null {
  const candidates = document.querySelectorAll<HTMLElement>(
    `[role="${role}"], input[type="${role}"], button, a, select, textarea`
  );

  for (const el of candidates) {
    const ariaLabel = el.getAttribute("aria-label") || "";
    const innerText = (el.textContent || "").trim();
    const placeholder = (el as HTMLInputElement).placeholder || "";
    const value = (el as HTMLInputElement).value || "";

    if (
      ariaLabel.toLowerCase().includes(text.toLowerCase()) ||
      innerText.toLowerCase().includes(text.toLowerCase()) ||
      placeholder.toLowerCase().includes(text.toLowerCase()) ||
      value.toLowerCase().includes(text.toLowerCase())
    ) {
      return el;
    }
  }
  return null;
}

function showIndicator(el: Element): void {
  const rect = el.getBoundingClientRect();
  const indicator = document.createElement("div");
  indicator.id = "vorlix-indicator";
  indicator.style.cssText = `
    position: fixed;
    top: ${rect.top}px;
    left: ${rect.left}px;
    width: ${rect.width}px;
    height: ${rect.height}px;
    border: 3px solid #ff4444;
    background: rgba(255, 68, 68, 0.1);
    z-index: 2147483647;
    pointer-events: none;
    box-sizing: border-box;
    animation: vorlix-pulse 1s ease-in-out infinite;
  `;
  const style = document.createElement("style");
  style.id = "vorlix-indicator-style";
  style.textContent = `
    @keyframes vorlix-pulse {
      0%, 100% { opacity: 0.6; }
      50% { opacity: 1; }
    }
  `;
  document.head.appendChild(style);
  document.body.appendChild(indicator);
}

function removeIndicator(): void {
  document.getElementById("vorlix-indicator")?.remove();
  document.getElementById("vorlix-indicator-style")?.remove();
}

chrome.runtime.onMessage.addListener((
  message: InteractRequest,
  _sender: chrome.runtime.MessageSender,
  sendResponse: (response: { success: boolean; data?: string; error?: string }) => void
) => {
  if (message.action !== "interact") {
    sendResponse({ success: false, error: "Unknown action." });
    return;
  }

  const target = findElement(message.aria_role, message.target_text);
  if (!target) {
    sendResponse({ success: false, error: `Element not found: role="${message.aria_role}" text="${message.target_text}"` });
    return;
  }

  showIndicator(target);

  try {
    switch (message.action_type) {
      case "click": {
        (target as HTMLElement).click();
        break;
      }
      case "type": {
        const input = target as HTMLInputElement;
        input.focus();
        input.value = "";
        if (message.input_value) {
          input.value = message.input_value;
          input.dispatchEvent(new Event("input", { bubbles: true }));
          input.dispatchEvent(new Event("change", { bubbles: true }));
        }
        break;
      }
      case "hover": {
        target.dispatchEvent(new MouseEvent("mouseover", { bubbles: true }));
        break;
      }
      case "extract": {
        const data = (target as HTMLElement).textContent || "";
        setTimeout(removeIndicator, 1500);
        sendResponse({ success: true, data });
        return;
      }
    }
  } catch (err) {
    setTimeout(removeIndicator, 500);
    sendResponse({ success: false, error: String(err) });
    return;
  }

  setTimeout(removeIndicator, 1500);
  sendResponse({ success: true });
});
