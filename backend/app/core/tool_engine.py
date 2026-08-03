import os
import re
import shlex
import shutil
import subprocess
from pathlib import Path
from urllib.parse import quote

WORKSPACE = Path(os.path.expanduser("~")) / ".nova_workspace"

SHELL_TIMEOUT_SECONDS = 30


class ToolUnavailable(Exception):
    pass


class ToolEngine:
    def __init__(self):
        WORKSPACE.mkdir(parents=True, exist_ok=True)

    def _resolve(self, path: str) -> Path:
        target = (WORKSPACE / path).resolve()
        if WORKSPACE.resolve() not in target.parents and target != WORKSPACE.resolve():
            raise PermissionError(f"Path escapes NOVA workspace: {path}")
        return target

    def _which(self, name: str) -> str:
        return shutil.which(name) or shutil.which(f"termux-{name}")

    def availability(self) -> dict:
        return {
            "open-url": bool(self._which("open-url")),
            "am": bool(self._which("am")),
            "send-sms": bool(self._which("send-sms")),
            "shell": True,
            "files": True,
            "browser": bool(self._which("open-url") or self._which("am")),
        }

    def shell_exec(self, command: str) -> str:
        if not command:
            return "No command given."
        try:
            proc = subprocess.run(
                shlex.split(command),
                capture_output=True,
                text=True,
                timeout=SHELL_TIMEOUT_SECONDS,
                cwd=str(WORKSPACE),
            )
        except FileNotFoundError as exc:
            return f"Command not found: {exc}"
        except subprocess.TimeoutExpired:
            return f"Command timed out after {SHELL_TIMEOUT_SECONDS}s."
        output = proc.stdout.strip()
        error = proc.stderr.strip()
        if proc.returncode != 0:
            return f"Exit {proc.returncode}\n{error or output}"
        return output or "(no output)"

    def file_read(self, path: str) -> str:
        target = self._resolve(path)
        if not target.exists():
            return f"File not found: {path}"
        if target.is_dir():
            return self.list_files(
                str(target.relative_to(WORKSPACE)) if target != WORKSPACE else ""
            )
        return target.read_text("utf-8", errors="replace")

    def file_write(self, path: str, content: str) -> str:
        target = self._resolve(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, "utf-8")
        return f"Wrote {len(content)} bytes to {path}"

    def file_create_folder(self, path: str) -> str:
        target = self._resolve(path)
        target.mkdir(parents=True, exist_ok=True)
        return f"Created folder {path}"

    def file_delete(self, path: str) -> str:
        target = self._resolve(path)
        if not target.exists():
            return f"File not found: {path}"
        if target.is_dir():
            shutil.rmtree(target)
            return f"Deleted folder {path}"
        target.unlink()
        return f"Deleted file {path}"

    def list_files(self, path: str = "") -> str:
        target = WORKSPACE if not path else self._resolve(path)
        if not target.exists():
            return f"Path not found: {path}"
        if not target.is_dir():
            return f"Not a folder: {path}"
        lines = [f"{p.name}/" if p.is_dir() else p.name for p in sorted(target.iterdir())]
        return "\n".join(lines) if lines else "(empty)"

    def android_open_url(self, url: str) -> str:
        opener = self._which("open-url")
        if opener:
            try:
                subprocess.run([opener, url], capture_output=True, text=True, timeout=15)
                return "opened"
            except Exception:
                pass
        am = self._which("am")
        if am:
            try:
                subprocess.run(
                    [am, "start", "-a", "android.intent.action.VIEW", "-d", url],
                    capture_output=True,
                    text=True,
                    timeout=15,
                )
                return "opened"
            except Exception:
                pass
        raise ToolUnavailable("browser")

    def send_whatsapp(self, number: str, message: str) -> str:
        number = re.sub(r"\D", "", number or "")
        if len(number) == 10:
            number = "91" + number
        url = f"https://wa.me/{number}?text={quote(message)}"
        return self.android_open_url(url)

    def send_sms(self, number: str, message: str) -> str:
        sender = self._which("send-sms")
        if not sender:
            raise ToolUnavailable("send-sms")
        try:
            proc = subprocess.run(
                [sender, "-n", number, message],
                capture_output=True,
                text=True,
                timeout=20,
            )
            if proc.returncode != 0:
                return f"Exit {proc.returncode}: {proc.stderr.strip()}"
            return "sent"
        except Exception as exc:
            raise ToolUnavailable(f"send-sms: {exc}")

    def open_youtube(self, query: str) -> str:
        url = f"https://www.youtube.com/results?search_query={quote(query)}"
        return self.android_open_url(url)

    def open_netflix(self, query: str) -> str:
        url = f"https://www.netflix.com/search?q={quote(query)}"
        return self.android_open_url(url)

    def play_media(self, query: str, player: str = None) -> str:
        if player == "netflix":
            return self.open_netflix(query)
        if player == "youtube":
            return self.open_youtube(query)
        try:
            return self.open_youtube(query)
        except ToolUnavailable:
            return self.open_netflix(query)
