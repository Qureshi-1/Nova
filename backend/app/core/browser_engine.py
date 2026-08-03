import re
import subprocess
import webbrowser
from html.parser import HTMLParser
from pathlib import Path

import requests

UA = "Mozilla/5.0 (Linux; Android 13) NOVA-Cognitive-Companion/1.5"
DUCKDUCKGO_API = "https://api.duckduckgo.com/"
DUCKDUCKGO_HTML = "https://html.duckduckgo.com/html/"
MAX_PAGE_CHARS = 3000
MAX_RESULT_CHARS = 1200


class _TextExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self.skip = 0
        self.parts = []

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "noscript"):
            self.skip += 1

    def handle_endtag(self, tag):
        if tag in ("script", "style", "noscript") and self.skip > 0:
            self.skip -= 1

    def handle_data(self, data):
        if self.skip == 0:
            self.parts.append(data)


def _extract_text(html: str) -> str:
    parser = _TextExtractor()
    parser.feed(html)
    text = " ".join(parser.parts)
    text = re.sub(r"\s+", " ", text).strip()
    return text


class BrowserError(Exception):
    pass


class BrowserEngine:
    def search(self, query: str) -> str:
        try:
            res = requests.get(
                DUCKDUCKGO_API,
                params={"q": query, "format": "json", "no_html": 1, "skip_disambig": 1},
                headers={"User-Agent": UA},
                timeout=20,
            )
            res.raise_for_status()
            data = res.json()
            answer = data.get("AbstractText") or data.get("Answer")
            if answer:
                return answer[:MAX_RESULT_CHARS]
        except Exception:
            pass
        return self._search_html_fallback(query)

    def _search_html_fallback(self, query: str) -> str:
        try:
            res = requests.post(
                DUCKDUCKGO_HTML,
                data={"q": query},
                headers={"User-Agent": UA},
                timeout=20,
            )
            res.raise_for_status()
            text = _extract_text(res.text)
            snippet = re.sub(r"^(.*?)(Result|More results|About DuckDuckGo).*$", r"\1", text, flags=re.DOTALL)
            return snippet.strip()[:MAX_RESULT_CHARS]
        except Exception as exc:
            raise BrowserError(f"Search failed: {exc}")

    def read_page(self, url: str) -> str:
        if not url.startswith(("http://", "https://")):
            url = "https://" + url
        try:
            res = requests.get(url, headers={"User-Agent": UA}, timeout=25)
            res.raise_for_status()
            text = _extract_text(res.text)
            if not text:
                raise BrowserError("Page has no readable text")
            return text[:MAX_PAGE_CHARS]
        except requests.RequestException as exc:
            raise BrowserError(f"Could not read page: {exc}")

    def download_file(self, url: str, destination: Path) -> str:
        if not url.startswith(("http://", "https://")):
            raise BrowserError("Not a valid URL")
        destination.parent.mkdir(parents=True, exist_ok=True)
        try:
            with requests.get(url, stream=True, headers={"User-Agent": UA}, timeout=120) as res:
                res.raise_for_status()
                with open(destination, "wb") as f:
                    for chunk in res.iter_content(chunk_size=65536):
                        if chunk:
                            f.write(chunk)
            return f"Downloaded {destination.name} ({destination.stat().st_size} bytes)"
        except requests.RequestException as exc:
            destination.unlink(missing_ok=True)
            raise BrowserError(f"Download failed: {exc}")

    def open_url(self, url: str) -> str:
        for cmd in (
            ["termux-open-url", url],
            ["am", "start", "-a", "android.intent.action.VIEW", "-d", url],
        ):
            if _which(cmd[0]):
                try:
                    subprocess.run(cmd, capture_output=True, text=True, timeout=15)
                    return f"Opened {url}"
                except Exception:
                    continue
        try:
            webbrowser.open(url)
            return f"Opened {url}"
        except Exception:
            raise BrowserError("No browser tool available on this device")


def _which(name: str) -> str:
    import shutil

    return shutil.which(name) or shutil.which(f"termux-{name}")
