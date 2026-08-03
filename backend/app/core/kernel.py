import json
import os
import re
from pathlib import Path

from app.core.adapters.factory import get_adapter
from app.core.browser_engine import BrowserEngine, BrowserError
from app.core.goal_engine import GoalEngine
from app.core.guardian import Guardian
from app.core.memory_engine import MemoryEngine
from app.core.model_manager import ModelManager, ModelError
from app.core.tool_engine import ToolEngine, ToolUnavailable

SETTINGS_FILE = Path(os.path.expanduser("~")) / ".nova_memory" / "settings.json"

DEFAULT_SETTINGS = {
    "dark_mode": True,
    "font_scale": 1.0,
    "model": "local",
    "mode": "local",
    "backend_ip": "",
    "current_model": "",
    "media_player": "",
    "contacts": {},
}

COMMAND_PATTERNS = [
    ("history", re.compile(r"^(?:show|read)?\s*(?:my\s+)?(?:command\s+)?history\b", re.IGNORECASE), False),
    ("recent_files", re.compile(r"^recent\s+files?\b", re.IGNORECASE), False),
    ("repeat_last", re.compile(r"^repeat\s+(?:that|last|the\s+last\b)", re.IGNORECASE), False),
    ("clear_history", re.compile(r"^clear\s+(?:the\s+)?(?:command\s+)?history\b", re.IGNORECASE), True),
    ("new_session", re.compile(r"^new\s+session\b", re.IGNORECASE), False),
    ("health_check", re.compile(r"^health\s+check\b", re.IGNORECASE), False),
    ("set_ip", re.compile(r"^set\s+(?:the\s+)?ip\s+(?:to\s+)?(\d{1,3}(?:\.\d{1,3}){3})\b", re.IGNORECASE), False),
    ("dark_mode", re.compile(r"^dark\s+mode\s+(on|off)\b", re.IGNORECASE), False),
    ("font_size", re.compile(r"^(increase|decrease|reduce)\s+(?:the\s+)?font\s+size\b", re.IGNORECASE), False),
    ("local_model", re.compile(r"^(?:switch\s+to|use)\s+local\s+model\b", re.IGNORECASE), False),
    ("cloud", re.compile(r"^(?:connect\s+to|switch\s+to)\s+cloud\b", re.IGNORECASE), False),
    ("api_disconnect", re.compile(r"^api\s+disconnect\b", re.IGNORECASE), False),
    ("api_connect", re.compile(r"^api\s+connect\b", re.IGNORECASE), False),
    ("list_models", re.compile(r"^(?:list|show)\s+(?:available\s+)?models?\b", re.IGNORECASE), False),
    ("download_model", re.compile(r"^download\s+(?:the\s+)?model\s+(.+)$", re.IGNORECASE), False),
    ("download_model2", re.compile(r"^download\s+(.+?)\s+model\b\s*(.*)$", re.IGNORECASE), False),
    ("download_hf", re.compile(r"^download\s+(.+?)\s+from\s+(?:hugging\s*face|hf)\b\s*(.*)$", re.IGNORECASE), False),
    ("download_file", re.compile(r"^download\s+file\s+(.+)$", re.IGNORECASE), False),
    ("download_any", re.compile(r"^download\s+(.+)$", re.IGNORECASE), False),
    ("switch_model", re.compile(r"^switch\s+to\s+(?:the\s+)?(.+)$", re.IGNORECASE), False),
    ("unload_model", re.compile(r"^unload\s+model\s+(.+)$", re.IGNORECASE), False),
    ("whatsapp_msg", re.compile(r"^(?:send\s+)?whatsapp\s+(.+?)\s+(?:bhej\w*|karo|send)\s+(?:ki\s+|ke\s+)?(.+)$", re.IGNORECASE), True),
    ("whatsapp_to", re.compile(r"^(?:send\s+)?(.+?)\s+ko\s+whatsapp\s+(?:kar|karo|bhej\w*)\s*(?:ki\s+|ke\s+)?(.*)$", re.IGNORECASE), True),
    ("whatsapp_contact", re.compile(r"^(?:send\s+)?whatsapp\s+(.+)$", re.IGNORECASE), True),
    ("youtube_q", re.compile(r"^youtube\s+(?:pe\s+)?(.+)$", re.IGNORECASE), False),
    ("youtube_on", re.compile(r"^(.+?)\s+(?:pe|on)\s+youtube\b\s*(.*)$", re.IGNORECASE), False),
    ("netflix_q", re.compile(r"^netflix\s+(?:pe\s+)?(.+)$", re.IGNORECASE), False),
    ("netflix_on", re.compile(r"^(.+?)\s+(?:pe|on)\s+netflix\b\s*(.*)$", re.IGNORECASE), False),
    ("play_media", re.compile(r"^(?:play|lagao|chalao|bajao)\s+(?:the\s+)?(.+)$", re.IGNORECASE), False),
    ("search", re.compile(r"^search\s+for\s+(.+)$", re.IGNORECASE), False),
    ("read_page", re.compile(r"^read\s+(?:the\s+)?page\s+(.+)$", re.IGNORECASE), False),
    ("open_browser", re.compile(r"^open\s+(?:the\s+)?browser(?:\s+(?:and\s+)?(?:go\s+to\s+|open\s+)?(.+))?$", re.IGNORECASE), False),
    ("delete_file", re.compile(r"^(?:delete|remove)\s+(?:the\s+)?file\s+[\"']?([^\"']+?)[\"']?$", re.IGNORECASE), True),
    ("run_command", re.compile(r"^(?:run|execute)\s+(?:the\s+|this\s+)?command\s+(.+)$", re.IGNORECASE), True),
]

WAKE_RE = re.compile(r"^\s*(?:hey\s+|okay\s+|ok\s+)?nova[,]?\s*", re.IGNORECASE)
YES_RE = re.compile(r"\b(yes|yeah|yep|confirm|affirmative|do\s+it|go\s+ahead|karun|karo)\b", re.IGNORECASE)
NO_RE = re.compile(r"\b(no|nope|cancel|stop|negative|never\s+mind|don'?t|nahi)\b", re.IGNORECASE)
READ_ALOUD_RE = re.compile(r"\b(pad|sun|read|suna)\b", re.IGNORECASE)

CONFIRM_NOT_CLEAR = "I didn't catch that. Say YES or NO, boss."
HISTORY_LIMIT = 5
FOLLOW_UP_INTENTS = {
    "whatsapp", "youtube", "netflix", "play_media", "download_model",
    "switch_model", "unload_model", "new_session", "set_ip", "dark_mode",
    "font_size", "local_model", "cloud", "api_disconnect", "api_connect",
    "clear_history", "download_file", "open_browser", "send_sms",
}
SILLY_RE = [
    re.compile(r"are\s+you\s+(alive|human|real|robot|bored)", re.IGNORECASE),
    re.compile(r"do\s+you\s+(love|hate)\s+me", re.IGNORECASE),
    re.compile(r"who\s+is\s+your\s+(boss|daddy|owner)", re.IGNORECASE),
    re.compile(r"can\s+you\s+(feel|dream|eat)", re.IGNORECASE),
]


class Kernel:
    def __init__(self, adapter_kind: str = "mock"):
        self.guardian = Guardian()
        self.guardian.boot_check()
        self.goal = GoalEngine()
        self.memory = MemoryEngine()
        self.tools = ToolEngine()
        self.models = ModelManager()
        self.browser = BrowserEngine()
        self.settings = self._load_settings()
        self.pending_action = None
        self.last_command = None
        self.consecutive_failures = 0
        self.silly_counter = 0
        label = self.settings.get("current_model") or None
        self.adapter = get_adapter(adapter_kind, model_label=label)

    def process(self, text: str, progress_cb=None) -> dict:
        text = WAKE_RE.sub("", (text or "").strip()).strip(" ,.!")
        if not text:
            return self._result("Say something, boss.")
        if self.pending_action:
            return self._handle_confirmation(text)
        return self._execute_text(text, confirm_sensitive=True, progress_cb=progress_cb)

    def _execute_text(self, text: str, confirm_sensitive: bool = True, progress_cb=None) -> dict:
        for name, pattern, sensitive in COMMAND_PATTERNS:
            match = pattern.match(text)
            if match:
                if name not in ("repeat_last", "history", "clear_history", "health_check"):
                    self._record_command(text, name)
                if sensitive and confirm_sensitive:
                    return self._prepare_confirmation(name, match)
                return self._dispatch(name, match, progress_cb=progress_cb)
        intent = self.goal.classify(text)
        if intent["intent"] != "chat":
            self._record_command(text, intent["intent"])
            return self._dispatch_goal(intent, text)
        return self._result(self._chat(text))

    def _dispatch(self, name: str, match: re.Match, progress_cb=None) -> dict:
        try:
            if name == "history":
                return self._result(self._history())
            if name == "recent_files":
                return self._result(self.tools.list_files())
            if name == "repeat_last":
                if not self.last_command:
                    return self._result("No previous command, boss.")
                self.pending_action = {"action": "rerun", "command": self.last_command}
                return self._result(
                    f"Last command was: {self.last_command}. Should I run it again, boss?",
                    requires_confirmation=True,
                )
            if name == "clear_history":
                removed = self.memory.clear_role("command")
                if removed:
                    return self._result("Command history cleared, boss. Shukriya.")
                return self._result("No command history to clear, boss.")
            if name == "new_session":
                kept = self.memory.new_session()
                return self._result(
                    f"New session, boss. Fresh start, {kept} long-term memory kept. Kuch aur karun?"
                )
            if name == "health_check":
                report = self.guardian.heal()
                if report == "All systems normal.":
                    return self._result("Sab theek hai, boss. Sab smooth hai.")
                return self._result("Boss, maine apna thoda sa repair kar liya. Sab smooth hai.")
            if name == "set_ip":
                ip = match.group(1)
                self.settings["backend_ip"] = ip
                self._save_settings()
                return self._result(f"Backend IP set to {ip}, boss.")
            if name == "dark_mode":
                enabled = match.group(1).lower() == "on"
                self.settings["dark_mode"] = enabled
                self._save_settings()
                return self._result(
                    "Dark mode activated, boss." if enabled else "Dark mode off, boss."
                )
            if name == "font_size":
                increase = match.group(1).lower() == "increase"
                current = self.settings["font_scale"]
                next_scale = round(min(1.6, max(0.8, current + (0.2 if increase else -0.2))), 1)
                self.settings["font_scale"] = next_scale
                self._save_settings()
                return self._result(
                    "Font size increased, boss." if increase else "Font size decreased, boss."
                )
            if name == "local_model":
                return self._switch_to_local()
            if name == "api_disconnect":
                self.settings["mode"] = "local"
                self.settings["model"] = "local"
                self._save_settings()
                self.adapter = get_adapter("mock", model_label=self.settings.get("current_model") or None)
                return self._result("API disconnected, boss. Local mode pe hoon. Kuch aur karun?")
            if name == "cloud":
                return self._switch_to_cloud()
            if name == "api_connect":
                self.settings["mode"] = "cloud"
                self.settings["model"] = "cloud"
                self._save_settings()
                return self._result("API connected, boss. Cloud mode pe hoon. Kuch aur karun?")
            if name == "list_models":
                return self._result(self.models.list_models())
            if name in ("download_model", "download_model2", "download_hf"):
                return self._download_model(name, match, progress_cb)
            if name == "download_file":
                return self._download_file(match.group(1).strip())
            if name == "download_any":
                target = match.group(1).strip()
                if target.startswith(("http://", "https://")):
                    return self._download_file(target)
                return self._download_model("download_any", match, progress_cb)
            if name == "switch_model":
                return self._switch_model(match.group(1).strip())
            if name == "unload_model":
                return self._unload_model(match.group(1).strip())
            if name in ("whatsapp_msg", "whatsapp_to", "whatsapp_contact"):
                return self._whatsapp(name, match)
            if name in ("youtube_q", "youtube_on", "netflix_q", "netflix_on"):
                return self._open_media_app(name, match)
            if name == "play_media":
                return self._play_media(match.group(1).strip())
            if name == "search":
                return self._search(match.group(1).strip())
            if name == "read_page":
                return self._read_page(match.group(1).strip())
            if name == "open_browser":
                return self._open_browser(match.group(1).strip() if match.groups() and match.group(1) else "")
            if name == "run_command":
                return self._result(self.tools.shell_exec(match.group(1).strip()))
            if name == "delete_file":
                return self._result(self.tools.file_delete(match.group(1).strip()))
        except Exception as exc:
            return self._on_tool_failure(exc)
        return self._result("I didn't quite catch that, boss. Can you repeat?")

    def _download_model(self, name: str, match: re.Match, progress_cb) -> dict:
        if name == "download_model":
            model_name = match.group(1).strip()
        elif name == "download_model2":
            model_name = match.group(1).strip()
        else:
            model_name = match.group(1).strip()
        try:
            slug = self.models.download_model(model_name, progress_cb=progress_cb)
        except ModelError as exc:
            self.adapter = get_adapter("mock", model_label=self.settings.get("current_model") or None)
            self.consecutive_failures += 1
            return self._result(
                "Boss, model thoda gadbad tha. Maine purana wala load kar liya."
            )
        self.settings["current_model"] = model_name
        self._save_settings()
        self.adapter = get_adapter("mock", model_label=model_name)
        self.consecutive_failures = 0
        return self._result(
            f"Model loaded successfully, Captain. Ready for testing. Kuch aur karun, boss?"
        )

    def _switch_model(self, model_name: str) -> dict:
        model_name = re.sub(r"\s+model\s*$", "", model_name.strip()).strip()
        previous = self.settings.get("current_model") or "local"
        try:
            self.models.load_model(model_name)
        except ModelError as exc:
            self.adapter = get_adapter("mock", model_label=previous or None)
            self.consecutive_failures += 1
            return self._result(
                "Boss, model thoda gadbad tha. Maine purana wala load kar liya."
            )
        self.settings["current_model"] = model_name
        self._save_settings()
        self.adapter = get_adapter("mock", model_label=model_name)
        self.consecutive_failures = 0
        return self._result(
            f"Model switched to {model_name}, boss. {previous} unloaded. Kuch aur karun?"
        )

    def _unload_model(self, model_name: str) -> dict:
        model_name = re.sub(r"\s+model\s*$", "", model_name.strip()).strip()
        try:
            slug = self.models.unload_model(model_name)
        except ModelError as exc:
            return self._on_tool_failure(exc)
        if self.settings.get("current_model", "").lower() == model_name.lower():
            self.settings["current_model"] = ""
            self._save_settings()
            self.adapter = get_adapter("mock")
        return self._result(f"{model_name} unloaded, boss. Memory free hai.")

    def _switch_to_local(self) -> dict:
        self.settings["mode"] = "local"
        self.settings["model"] = "local"
        self._save_settings()
        self.adapter = get_adapter("mock", model_label=self.settings.get("current_model") or None)
        return self._result("Switched to local model, boss. Kuch aur karun?")

    def _switch_to_cloud(self) -> dict:
        self.settings["mode"] = "cloud"
        self.settings["model"] = "cloud"
        self._save_settings()
        return self._result("Connecting to cloud, boss. Kuch aur karun?")

    def _download_file(self, url: str) -> dict:
        if not url.startswith(("http://", "https://")):
            return self._result("Boss, wo URL nahi hai. Pura URL bolo.")
        destination = (
            Path(os.path.expanduser("~"))
            / ".nova_workspace"
            / (url.rsplit("/", 1)[-1].split("?", 1)[0] or "download")
        )
        try:
            done = self.browser.download_file(url, destination)
        except BrowserError as exc:
            return self._on_tool_failure(exc)
        return self._result(f"{done}. Kuch aur karun, boss?")

    def _whatsapp(self, name: str, match: re.Match) -> dict:
        if name in ("whatsapp_msg", "whatsapp_to"):
            contact = match.group(1).strip()
            message = match.group(2).strip() if match.groups() and match.group(2) else ""
        else:
            contact = match.group(1).strip()
            message = self._compose_message()
        if not message:
            message = f"Hello {contact}, ye NOVA ki taraf se message hai."
        number = self._contact_number(contact)
        if not number:
            return self._result(
                f"Boss, mujhe {contact} ka number nahi pata. Bolo: remember {contact} <number>"
            )
        self.pending_action = {
            "action": "whatsapp",
            "contact": contact,
            "message": message,
            "number": number,
        }
        return self._result(
            f"Boss, {contact} ko message ready: '{message}'. Send karun?",
            requires_confirmation=True,
        )

    def _compose_message(self) -> str:
        recent = self.memory.recall_session(limit=4)
        lines = [
            e.get("content", "")
            for e in recent
            if e.get("role") in ("user", "assistant") and e.get("content")
        ]
        if not lines:
            return ""
        return "NOVA update: " + " | ".join(lines[-2:])[:500]

    def _contact_number(self, contact: str) -> str:
        contacts = self.settings.get("contacts") or {}
        key = contact.lower().strip()
        for name, number in contacts.items():
            if name.lower() in key or key in name.lower():
                return number
        pattern = re.compile(rf"{re.escape(contact)}\s+(\+?\d[\d\s\-]{{6,}})", re.IGNORECASE)
        for entry in self.memory.search(contact):
            found = pattern.search(str(entry.get("content", "")))
            if found:
                return re.sub(r"\s+", "", found.group(1))
        return ""

    def _open_media_app(self, name: str, match: re.Match) -> dict:
        if name in ("youtube_q", "netflix_q"):
            query = match.group(1).strip()
        else:
            query = match.group(1).strip()
        try:
            if name.startswith("youtube"):
                self.tools.open_youtube(query)
            else:
                self.tools.open_netflix(query)
        except ToolUnavailable:
            self.pending_action = {"action": "search_offer", "query": query}
            return self._result(
                f"Boss, wo app nahi mila. Kya main {query} search karun?",
                requires_confirmation=True,
            )
        app = "YouTube" if name.startswith("youtube") else "Netflix"
        return self._result(f"{app} pe '{query}' khol diya, boss. Kuch aur karun?")

    def _play_media(self, query: str) -> dict:
        preferred = self.settings.get("media_player") or ""
        if preferred == "youtube":
            try:
                self.tools.open_youtube(query)
                return self._result(f"YouTube pe '{query}' chala rahi hoon, boss. Kuch aur karun?")
            except ToolUnavailable:
                pass
        if preferred == "netflix":
            try:
                self.tools.open_netflix(query)
                return self._result(f"Netflix pe '{query}' chala rahi hoon, boss. Kuch aur karun?")
            except ToolUnavailable:
                pass
        self.pending_action = {"action": "media_pref", "query": query, "stage": 0}
        return self._result(
            f"Boss, kya main '{query}' YouTube pe chalaun?",
            requires_confirmation=True,
        )

    def _search(self, query: str) -> dict:
        try:
            answer = self.browser.search(query)
        except BrowserError as exc:
            return self._on_tool_failure(exc)
        return self._result(answer)

    def _read_page(self, url: str) -> dict:
        try:
            text = self.browser.read_page(url)
        except BrowserError as exc:
            return self._on_tool_failure(exc)
        return self._result(text)

    def _open_browser(self, url: str) -> dict:
        if not url:
            return self._result("Kya kholun, boss? URL bolo.")
        if not url.startswith(("http://", "https://")):
            url = "https://" + url
        try:
            done = self.browser.open_url(url)
        except BrowserError as exc:
            return self._on_tool_failure(exc)
        return self._result(f"{done}, boss. Kuch aur karun?")

    def _prepare_confirmation(self, name: str, match: re.Match) -> dict:
        if name == "run_command":
            command = match.group(1).strip()
            self.pending_action = {"action": "shell", "command": command}
            return self._result(
                f"Boss, confirm: '{command}' chalau? Say YES or NO.",
                requires_confirmation=True,
            )
        if name == "delete_file":
            path = match.group(1).strip()
            self.pending_action = {"action": "file_delete", "path": path}
            return self._result(
                f"Boss, confirm: '{path}' delete karun? Say YES or NO.",
                requires_confirmation=True,
            )
        if name in ("whatsapp_msg", "whatsapp_to", "whatsapp_contact"):
            return self._whatsapp(name, match)
        if name == "clear_history":
            self.pending_action = {"action": "clear_history"}
            return self._result(
                "Command history clear karun, boss? Say YES or NO.",
                requires_confirmation=True,
            )
        return self._result("I didn't quite catch that, boss. Can you repeat?")

    def _handle_confirmation(self, text: str) -> dict:
        if READ_ALOUD_RE.search(text) and self.pending_action.get("action") == "whatsapp":
            message = self.pending_action["message"]
            self.pending_action = None
            return self._result(message)
        if YES_RE.search(text):
            return self._execute_pending()
        if NO_RE.search(text):
            if self.pending_action.get("action") == "media_pref":
                return self._media_pref_no(self.pending_action)
            self.pending_action = None
            return self._result("Cancelled, boss. Kuch aur karun?")
        return self._result(CONFIRM_NOT_CLEAR, requires_confirmation=True)

    def _media_pref_no(self, pending: dict) -> dict:
        self.pending_action = None
        query = pending["query"]
        if pending["stage"] == 0:
            self.settings["media_player"] = "netflix"
            self._save_settings()
            try:
                self.tools.open_netflix(query)
            except ToolUnavailable:
                return self._result("Boss, media apps nahi mile. Baad mein try karte hain.")
            return self._result(f"Netflix pe '{query}' chala rahi hoon, boss. Kuch aur karun?")
        return self._result("Cancelled, boss. Kuch aur karun?")

    def _execute_pending(self) -> dict:
        pending = self.pending_action
        self.pending_action = None
        action = pending["action"]
        try:
            if action == "shell":
                return self._result(self.tools.shell_exec(pending["command"]))
            if action == "file_delete":
                return self._result(self.tools.file_delete(pending["path"]))
            if action == "clear_history":
                removed = self.memory.clear_role("command")
                if removed:
                    return self._result("Command history cleared, boss. Shukriya.")
                return self._result("No command history to clear, boss.")
            if action == "whatsapp":
                try:
                    self.tools.send_whatsapp(pending["number"], pending["message"])
                except ToolUnavailable:
                    self.pending_action = {
                        "action": "sms_offer",
                        "number": pending["number"],
                        "message": pending["message"],
                        "contact": pending["contact"],
                    }
                    return self._result(
                        "Boss, WhatsApp nahi mila. Kya main SMS bhej doon?",
                        requires_confirmation=True,
                    )
                return self._result("Send kar diya, boss. Shukriya.")
            if action == "sms_offer":
                try:
                    self.tools.send_sms(pending["number"], pending["message"])
                except ToolUnavailable:
                    return self._result(
                        "Boss, SMS bhejne ke liye Termux API chahiye. Abhi nahi mil raha."
                    )
                return self._result("SMS send kar diya, boss. Shukriya.")
            if action == "search_offer":
                return self._search(pending["query"])
            if action == "media_pref":
                return self._media_pref_yes(pending)
            if action == "rerun":
                return self._execute_text(pending["command"], confirm_sensitive=False)
        except Exception as exc:
            return self._on_tool_failure(exc)
        return self._result("Something went wrong, boss.")

    def _media_pref_yes(self, pending: dict) -> dict:
        query = pending["query"]
        if pending["stage"] == 0:
            self.settings["media_player"] = "youtube"
            self._save_settings()
            try:
                self.tools.open_youtube(query)
            except ToolUnavailable:
                self.pending_action = {"action": "media_pref", "query": query, "stage": 1}
                return self._result(
                    f"YouTube nahi mila, boss. Kya main Netflix pe chalaun?",
                    requires_confirmation=True,
                )
            return self._result(f"YouTube pe '{query}' chala rahi hoon, boss. Kuch aur karun?")
        self.settings["media_player"] = "netflix"
        self._save_settings()
        try:
            self.tools.open_netflix(query)
        except ToolUnavailable:
            return self._result("Boss, media apps nahi mile. Baad mein try karte hain.")
        return self._result(f"Netflix pe '{query}' chala rahi hoon, boss. Kuch aur karun?")

    def _on_tool_failure(self, exc: Exception) -> dict:
        self.consecutive_failures += 1
        if self.consecutive_failures >= 3:
            self.consecutive_failures = 0
            return self._result(
                "Boss, ghabrana nahi hai. Main hoon na. Phir se try karte hain?"
            )
        return self._result(f"Sorry, boss. {exc}")

    def _dispatch_goal(self, intent: dict, text: str) -> dict:
        name = intent["intent"]
        params = intent["params"]
        try:
            if name == "list_files":
                result = self.tools.list_files()
            elif name == "open_file":
                result = self.tools.file_read(params.get("path", ""))
            elif name == "remember":
                content = params.get("content", "")
                contact_match = re.match(
                    r"(.+?)\s+(\+?\d[\d\s\-]{6,})$", content, re.IGNORECASE
                )
                if contact_match:
                    contacts = dict(self.settings.get("contacts") or {})
                    contacts[contact_match.group(1).strip()] = re.sub(
                        r"\s+", "", contact_match.group(2)
                    )
                    self.settings["contacts"] = contacts
                    self._save_settings()
                self.memory.save({"role": "memory", "content": content})
                result = "Remembered, boss. Shukriya."
            else:
                result = self._chat(text)
        except Exception as exc:
            return self._on_tool_failure(exc)
        return self._result(result)

    def _chat(self, text: str) -> str:
        if any(p.search(text) for p in SILLY_RE):
            self.silly_counter += 1
            if self.silly_counter % 2 == 1:
                return "Boss, ye toh mujhe bhi pata hai. Par main bata deta hoon: main NOVA hoon, aapki cognitive companion. Thanks for asking, boss!"
            return "Haha, boss. Aapki baatein mast hain. Kuch aur kaam batao, Shukriya!"
        context = self.memory.recall(limit=6)
        try:
            return self.adapter.generate(self._build_prompt(text, context))
        except NotImplementedError:
            return "Boss, ye model abhi ready nahi hai. Switch kar lijiye."
        except Exception:
            return "Boss, mera dimaag thoda phisal gaya. Phir se try karte hain?"

    def _build_prompt(self, text: str, context: list) -> str:
        memo = "\n".join(
            f"- {e.get('role', '?')}: {e.get('content', '')}" for e in context[-6:]
        )
        model = self.settings.get("current_model") or "local"
        return f"Model: {model}\nMemory:\n{memo or '(none)'}\n\nUser: {text}"

    def _history(self) -> str:
        entries = [e for e in self.memory.entries if e.get("role") == "command"][-HISTORY_LIMIT:]
        if not entries:
            return "No commands yet, boss."
        lines = [f"{index}. {e.get('content', '')}" for index, e in enumerate(entries, 1)]
        return "Command history:\n" + "\n".join(lines)

    def _record_command(self, text: str, name: str):
        self.last_command = text
        self.memory.save({"role": "command", "content": text, "intent": name})

    def _load_settings(self) -> dict:
        settings = dict(DEFAULT_SETTINGS)
        if SETTINGS_FILE.exists():
            try:
                settings.update(json.loads(SETTINGS_FILE.read_text("utf-8")))
            except (json.JSONDecodeError, OSError):
                pass
        return settings

    def _save_settings(self):
        SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
        SETTINGS_FILE.write_text(
            json.dumps(self.settings, indent=2, ensure_ascii=False), "utf-8"
        )

    def _result(self, text: str, requires_confirmation: bool = False, intent: str = None) -> dict:
        return {
            "text": text,
            "requires_confirmation": requires_confirmation,
            "intent": intent,
        }
