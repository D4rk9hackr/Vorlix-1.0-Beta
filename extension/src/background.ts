/// <reference types="chrome" />

interface BridgeRequest {
  action: "interact";
  aria_role: string;
  target_text: string;
  action_type: "click" | "type" | "hover" | "extract";
  input_value?: string;
}

interface BridgeResponse {
  success: boolean;
  data?: string;
  error?: string;
}

let nativePort: chrome.runtime.Port | null = null;

function connectNative(): chrome.runtime.Port {
  if (nativePort) return nativePort;
  nativePort = chrome.runtime.connectNative("com.vorlix.web_bridge");
  nativePort.onDisconnect.addListener(() => {
    nativePort = null;
  });
  return nativePort;
}

chrome.runtime.onMessage.addListener((
  message: BridgeRequest,
  _sender: chrome.runtime.MessageSender,
  sendResponse: (response: BridgeResponse) => void
) => {
  if (message.action === "interact") {
    chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
      const tabId = tabs[0]?.id;
      if (tabId === undefined) {
        sendResponse({ success: false, error: "No active tab." });
        return;
      }

      chrome.tabs.sendMessage(tabId, message, (contentResponse: BridgeResponse) => {
        if (contentResponse?.success) {
          try {
            const port = connectNative();
            port.postMessage({ type: "bridge_result", data: contentResponse.data });
          } catch (_) {
            // Native host not available — log and continue.
          }
        }
        sendResponse(contentResponse ?? { success: false, error: "No response from content script." });
      });
    });

    return true; // Keep channel open for async response
  }
  return false;
});
