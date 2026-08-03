"use strict";

const WebSocketServer = require("ws").WebSocketServer;
const http = require("http");

const PORT = Number(process.env.PORT || 8000);
const HOST = process.env.HOST || "0.0.0.0";

const server = http.createServer((req, res) => {
  if (req.url === "/health") {
    res.writeHead(200, { "Content-Type": "application/json" });
    res.end(JSON.stringify({ status: "ok", brain: "node-fallback", model: "mock" }));
    return;
  }
  res.writeHead(404);
  res.end("not found");
});

const wss = new WebSocketServer({ server });

const YES_RE = /\b(yes|yeah|yep|confirm|do it|go ahead|haan|karo)\b/i;
const NO_RE = /\b(no|nope|cancel|stop|nahi|mat karo)\b/i;
const SENSITIVE = [
  { re: /^(?:run|execute)\s+(?:the\s+|this\s+)?command\s+(.+)$/i, label: "shell" },
  { re: /^(?:delete|remove)\s+(?:the\s+)?file\s+["']?([^"']+?)["']?$/i, label: "file_delete" },
  { re: /^(?:send\s+)?whatsapp\b/i, label: "whatsapp" },
  { re: /^clear\s+(?:the\s+)?(?:command\s+)?history\b/i, label: "clear_history" },
];

const pending = new Map();

function result(text, requiresConfirmation = false, intent = null) {
  return {
    type: "result",
    payload: text,
    requires_confirmation: requiresConfirmation,
    intent: intent,
  };
}

function handle(ws, text) {
  const wake = /^\s*(?:hey\s+|okay\s+|ok\s+)?nova[,]?\s*/i;
  text = text.replace(wake, "").trim().replace(/[,.!]+$/, "");

  if (pending.has(ws)) {
    if (YES_RE.test(text)) {
      const action = pending.get(ws);
      pending.delete(ws);
      if (action.label === "shell") return result(`(node-fallback) ran: ${action.text}`);
      if (action.label === "whatsapp") return result("Send kar diya, boss. Shukriya.");
      return result("Done, boss. Shukriya.");
    }
    if (NO_RE.test(text)) {
      pending.delete(ws);
      return result("Cancelled, boss. Kuch aur karun?");
    }
    return result("I didn't catch that. Say YES or NO, boss.", true);
  }

  if (/^(?:list|show)\s+(?:available\s+)?models?\b/i.test(text)) {
    return result("- deepseek v4\n- deepseek\n- qwen\n- tiny\n- mistral\n(Brain module pending: download karke isse replace karenge)");
  }
  if (/^(?:switch\s+to|use)\s+local\s+model\b/i.test(text)) {
    return result("Switched to local model, boss. Kuch aur karun?");
  }
  if (/^(?:connect\s+to|switch\s+to)\s+cloud\b/i.test(text)) {
    return result("Connecting to cloud, boss. Kuch aur karun?");
  }
  if (/^api\s+disconnect\b/i.test(text)) {
    return result("API disconnected, boss. Local mode pe hoon.");
  }
  if (/^api\s+connect\b/i.test(text)) {
    return result("API connected, boss. Cloud mode pe hoon.");
  }
  if (/^new\s+session\b/i.test(text)) {
    return result("New session, boss. Fresh start, long-term memory kept. Kuch aur karun?");
  }
  if (/^health\s+check\b/i.test(text)) {
    return result("Sab theek hai, boss. Node fallback brain chal raha hai.");
  }
  if (/^dark\s+mode\s+(on|off)\b/i.test(text)) {
    return result(text.includes("on") ? "Dark mode activated, boss." : "Dark mode off, boss.");
  }
  if (/^(increase|decrease)\s+(?:the\s+)?font\s+size\b/i.test(text)) {
    return result(text.includes("increase") ? "Font size increased, boss." : "Font size decreased, boss.");
  }
  if (/^set\s+(?:the\s+)?ip\s+(?:to\s+)?(\d{1,3}(?:\.\d{1,3}){3})\b/i.test(text)) {
    return result("Backend IP set, boss.");
  }
  if (/^(?:play|lagao|chalao)\s+(.+)$/i.test(text)) {
    return result("Boss, AI Brain module abhi install nahi hai. Pehle 'Captain, AI Brain download karna padega. Karun?' — haan bolo, main download kar doon. Kuch aur karun?");
  }

  for (const rule of SENSITIVE) {
    const m = text.match(rule.re);
    if (m) {
      pending.set(ws, { label: rule.label, text: m[1] || "" });
      if (rule.label === "shell") {
        return result(`Boss, confirm: '${m[1]}' chalau? Say YES or NO.`, true);
      }
      if (rule.label === "file_delete") {
        return result(`Boss, confirm: '${m[1]}' delete karun? Say YES or NO.`, true);
      }
      if (rule.label === "whatsapp") {
        return result("Boss, message ready. Send karun? (AI Brain module download hone ke baad pura WhatsApp flow milega)", true);
      }
      return result("Command history clear karun, boss? Say YES or NO.", true);
    }
  }

  return result(`[node-fallback] Captain, main abhi light mode mein hoon — AI Brain download hone ke baad main poora dimaag load kar lungi. Kya bol rahe the? Kuch aur karun?`);
}

wss.on("connection", (ws) => {
  ws.on("message", (raw) => {
    let data;
    try {
      data = JSON.parse(raw.toString());
    } catch (err) {
      ws.send(JSON.stringify({ type: "error", payload: "Invalid JSON message" }));
      return;
    }
    if (data.type === "ping") {
      ws.send(JSON.stringify({ type: "pong", payload: "pong" }));
      return;
    }
    if (data.type === "voice_text") {
      ws.send(JSON.stringify(handle(ws, String(data.payload || ""))));
      return;
    }
    ws.send(JSON.stringify({ type: "error", payload: `Unknown message type: ${data.type}` }));
  });
});

server.listen(PORT, HOST, () => {
  console.log(`NOVA node-fallback brain on ws://${HOST}:${PORT}`);
});
