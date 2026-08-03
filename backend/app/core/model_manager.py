import json
import os
import re
import time
from pathlib import Path

import requests

MODELS_DIR = Path(os.path.expanduser("~")) / ".nova_models"
MODELS_MANIFEST = MODELS_DIR / "manifest.json"
HUGGINGFACE_RESOLVE = "https://huggingface.co/{repo}/resolve/main/{file}"
HUGGINGFACE_API = "https://huggingface.co/api/models"

KNOWN_MODELS = {
    "deepseek v4": {"repo": "deepseek-ai/DeepSeek-R1", "file": "config.json", "note": "DeepSeek official repo (alias for V1.5)"},
    "deepseek": {"repo": "deepseek-ai/DeepSeek-R1", "file": "config.json"},
    "qwen": {"repo": "Qwen/Qwen2.5-0.5B", "file": "config.json"},
    "tiny": {"repo": "sshleifer/tiny-gpt2", "file": "config.json"},
    "mistral": {"repo": "mistralai/Mistral-7B-Instruct-v0.3", "file": "config.json"},
}

UA = "NOVA-Cognitive-Companion/1.5"


class ModelError(Exception):
    pass


class ModelManager:
    def __init__(self):
        MODELS_DIR.mkdir(parents=True, exist_ok=True)
        self.manifest = self._load_manifest()

    def _load_manifest(self) -> dict:
        if MODELS_MANIFEST.exists():
            try:
                return json.loads(MODELS_MANIFEST.read_text("utf-8"))
            except (json.JSONDecodeError, OSError):
                pass
        return {}

    def _save_manifest(self):
        MODELS_MANIFEST.write_text(
            json.dumps(self.manifest, indent=2, ensure_ascii=False), "utf-8"
        )

    def _slug(self, repo: str) -> str:
        return re.sub(r"[^a-z0-9]+", "-", repo.lower()).strip("-")

    def _match_registry(self, name: str):
        for key, meta in KNOWN_MODELS.items():
            if key in name:
                return meta
        return None

    def _hf_search(self, name: str) -> str:
        try:
            res = requests.get(
                HUGGINGFACE_API,
                params={"search": name, "limit": 1, "sort": "downloads", "direction": -1},
                headers={"User-Agent": UA},
                timeout=20,
            )
            res.raise_for_status()
            items = res.json()
            if items and items[0].get("id"):
                return items[0]["id"]
        except Exception:
            pass
        raise ModelError(f"Model '{name}' not found on HuggingFace")

    def _resolve(self, name: str) -> tuple:
        name = name.strip().lower()
        meta = self._match_registry(name)
        if meta:
            return meta["repo"], meta["file"]
        repo = self._hf_search(name)
        return repo, "config.json"

    def list_models(self) -> str:
        lines = []
        for key, meta in KNOWN_MODELS.items():
            marker = " (downloaded)" if self._slug(meta["repo"]) in self.manifest else ""
            lines.append(f"- {key}{marker}")
        for slug, meta in self.manifest.items():
            if slug not in {self._slug(m["repo"]) for m in KNOWN_MODELS.values()}:
                lines.append(f"- {meta.get('name', slug)} (downloaded)")
        return "\n".join(lines) if lines else "No models yet, boss."

    def downloaded(self) -> list:
        return list(self.manifest.keys())

    def is_downloaded(self, name: str) -> bool:
        try:
            repo, _ = self._resolve(name)
        except ModelError:
            return False
        return self._slug(repo) in self.manifest

    def download_model(self, name: str, progress_cb=None) -> str:
        name = name.strip().lower()
        repo, file = self._resolve(name)
        slug = self._slug(repo)
        target_dir = MODELS_DIR / slug
        target_dir.mkdir(parents=True, exist_ok=True)
        target = target_dir / file
        if target.exists():
            self.manifest[slug] = {"name": name, "repo": repo, "file": file}
            self._save_manifest()
            if progress_cb:
                progress_cb(f"Downloading {name}... 100% completed.")
            return slug
        url = HUGGINGFACE_RESOLVE.format(repo=repo, file=file)
        try:
            with requests.get(url, stream=True, headers={"User-Agent": UA}, timeout=60) as res:
                res.raise_for_status()
                total = int(res.headers.get("content-length", 0) or 0)
                received = 0
                last_pct = -1
                with open(target, "wb") as f:
                    for chunk in res.iter_content(chunk_size=65536):
                        if not chunk:
                            continue
                        f.write(chunk)
                        received += len(chunk)
                        if progress_cb and total:
                            pct = min(99, int(received * 100 / total))
                            if pct >= last_pct + 5:
                                last_pct = pct
                                progress_cb(f"Downloading {name}... {pct}% completed.")
        except requests.RequestException as exc:
            target.unlink(missing_ok=True)
            raise ModelError(f"Download failed for {name}: {exc}")
        self.manifest[slug] = {"name": name, "repo": repo, "file": file}
        self._save_manifest()
        if progress_cb:
            progress_cb(f"Downloading {name}... 100% completed.")
            progress_cb(f"Download complete. Setting up model... Done.")
        return slug

    def load_model(self, name: str) -> str:
        name = name.strip().lower()
        if not self.is_downloaded(name):
            raise ModelError(f"Model '{name}' is not downloaded yet")
        repo, _ = self._resolve(name)
        return self._slug(repo)

    def unload_model(self, name: str) -> str:
        name = name.strip().lower()
        try:
            repo, _ = self._resolve(name)
        except ModelError:
            repo = name
        slug = self._slug(repo)
        if slug in self.manifest:
            del self.manifest[slug]
            self._save_manifest()
            return slug
        raise ModelError(f"Model '{name}' is not in memory")

    def integrity_check(self) -> list:
        issues = []
        for slug, meta in self.manifest.items():
            model_file = MODELS_DIR / slug / meta.get("file", "config.json")
            if not model_file.exists() or model_file.stat().st_size == 0:
                issues.append(f"model {slug} is missing or empty")
        return issues
