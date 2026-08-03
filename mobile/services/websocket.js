import { log } from "./bootlog";

log("websocket.js loaded");

const RECONNECT_BASE_DELAY_MS = 1000;

export function connectNovaSocket(ip, handlers = {}) {
  const ws = new WebSocket(`ws://${ip}:8000/ws`);

  ws.onopen = () => handlers.onOpen && handlers.onOpen();
  ws.onclose = () => handlers.onClose && handlers.onClose();
  ws.onerror = () => handlers.onError && handlers.onError();
  ws.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data);
      if (handlers.onMessage) handlers.onMessage(data);
    } catch (error) {}
  };

  return ws;
}

export function retryDelay(attempt) {
  return Math.min(5000, RECONNECT_BASE_DELAY_MS * 2 ** attempt);
}
