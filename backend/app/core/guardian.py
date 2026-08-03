import hashlib
import json
import os
from pathlib import Path

CORE_DIR = Path(__file__).resolve().parent
MANIFEST_DIR = Path(os.path.expanduser("~")) / ".nova_guardian"
MANIFEST_FILE = MANIFEST_DIR / "manifest.json"

WATCHED_FILES = ["kernel.py", "goal_engine.py", "adapters/base.py"]


class GuardianException(Exception):
    pass


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


class Guardian:
    def __init__(self):
        self.manifest = {}

    def boot_check(self):
        if not MANIFEST_FILE.exists():
            self._write_manifest()
            return
        try:
            self.manifest = json.loads(MANIFEST_FILE.read_text("utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            raise GuardianException(
                f"Guardian manifest is corrupt: {exc}"
            ) from exc
        for name in WATCHED_FILES:
            target = CORE_DIR / name
            stored = self.manifest.get(name)
            if stored is None:
                raise GuardianException(
                    f"Guardian: no stored hash for {name}. Core integrity unknown."
                )
            current = sha256_of(target)
            if current != stored:
                raise GuardianException(
                    f"Guardian: CORE FILE TAMPERED -> {name}. "
                    f"Hash mismatch (stored {stored[:12]}..., current {current[:12]}...). "
                    "Refusing to boot."
                )

    def _write_manifest(self):
        MANIFEST_DIR.mkdir(parents=True, exist_ok=True)
        manifest = {}
        for name in WATCHED_FILES:
            manifest[name] = sha256_of(CORE_DIR / name)
        MANIFEST_FILE.write_text(
            json.dumps(manifest, indent=2, sort_keys=True), "utf-8"
        )
        self.manifest = manifest

    def health_check(self) -> list:
        issues = []
        try:
            self.boot_check()
        except GuardianException as exc:
            issues.append(f"core integrity: {exc}")
        models_dir = Path(os.path.expanduser("~")) / ".nova_models"
        manifest_file = models_dir / "manifest.json"
        if manifest_file.exists():
            try:
                data = json.loads(manifest_file.read_text("utf-8"))
                for slug, meta in data.items():
                    model_file = models_dir / slug / meta.get("file", "config.json")
                    if not model_file.exists() or model_file.stat().st_size == 0:
                        issues.append(f"model {slug} is missing or empty")
            except (json.JSONDecodeError, OSError) as exc:
                issues.append(f"model manifest corrupt: {exc}")
        elif not models_dir.exists():
            issues.append("models directory missing")
        memory_file = Path(os.path.expanduser("~")) / ".nova_memory" / "memory.json"
        if memory_file.exists():
            try:
                entries = json.loads(memory_file.read_text("utf-8"))
                if not isinstance(entries, list):
                    issues.append("memory file is not a list")
            except (json.JSONDecodeError, OSError):
                issues.append("memory file corrupt")
        try:
            from app.core.tool_engine import ToolEngine

            for tool, available in ToolEngine().availability().items():
                if not available:
                    issues.append(f"tool unavailable: {tool}")
        except Exception as exc:
            issues.append(f"tool check failed: {exc}")
        return issues

    def auto_heal(self, issues: list) -> list:
        fixes = []
        models_dir = Path(os.path.expanduser("~")) / ".nova_models"
        manifest_file = models_dir / "manifest.json"
        if manifest_file.exists() and manifest_file.stat().st_size > 0:
            try:
                data = json.loads(manifest_file.read_text("utf-8"))
                changed = False
                for slug in list(data.keys()):
                    model_file = models_dir / slug / data[slug].get("file", "config.json")
                    if not model_file.exists() or model_file.stat().st_size == 0:
                        del data[slug]
                        changed = True
                if changed:
                    manifest_file.write_text(json.dumps(data, indent=2), "utf-8")
                    fixes.append("cleaned model manifest")
            except (json.JSONDecodeError, OSError):
                manifest_file.write_text("{}", "utf-8")
                fixes.append("rebuilt model manifest")
        elif models_dir.exists() and not manifest_file.exists():
            manifest_file.write_text("{}", "utf-8")
            fixes.append("created model manifest")
        if not models_dir.exists():
            models_dir.mkdir(parents=True, exist_ok=True)
            fixes.append("created models directory")
        memory_dir = Path(os.path.expanduser("~")) / ".nova_memory"
        memory_file = memory_dir / "memory.json"
        memory_dir.mkdir(parents=True, exist_ok=True)
        if memory_file.exists():
            try:
                entries = json.loads(memory_file.read_text("utf-8"))
                if not isinstance(entries, list):
                    raise ValueError("not a list")
            except (json.JSONDecodeError, ValueError, OSError):
                memory_file.write_text("[]", "utf-8")
                fixes.append("rebuilt memory store")
        if not MANIFEST_FILE.exists():
            self._write_manifest()
            fixes.append("reinitialized guardian manifest")
        return fixes

    def heal(self) -> str:
        issues = self.health_check()
        if not issues:
            return "All systems normal."
        fixes = self.auto_heal(issues)
        remaining = [i for i in issues if not any(f.split(":")[0] in i for f in fixes)]
        if remaining:
            return f"Found issues: {', '.join(issues)}"
        return "Repaired: " + ", ".join(fixes) if fixes else "Checked and stable."
