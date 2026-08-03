import re

INTENT_PATTERNS = [
    (
        "list_files",
        re.compile(r"(?:show|list)\s+(?:my\s+|all\s+)?files?\b", re.IGNORECASE),
    ),
    (
        "open_file",
        re.compile(
            r"(?:open|read)\s+(?:the\s+|a\s+)?file\s+[\"']?([^\"']+?)[\"']?$",
            re.IGNORECASE,
        ),
    ),
    (
        "run_command",
        re.compile(r"(?:run|execute)\s+(?:the\s+|this\s+)?command\s+(.+)$", re.IGNORECASE),
    ),
    (
        "remember",
        re.compile(r"(?:remember|recall)\s+(?:that\s+)?(.+)$", re.IGNORECASE),
    ),
]

FALLBACK_INTENT = "chat"


class GoalEngine:
    def classify(self, text: str) -> dict:
        for intent_name, pattern in INTENT_PATTERNS:
            match = pattern.match(text.strip())
            if match:
                params = {}
                if intent_name == "open_file":
                    params["path"] = match.group(1).strip()
                elif intent_name == "run_command":
                    params["command"] = match.group(1).strip()
                elif intent_name == "remember":
                    params["content"] = match.group(1).strip()
                return {"intent": intent_name, "params": params}
        return {"intent": FALLBACK_INTENT, "params": {}}
