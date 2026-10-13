from __future__ import annotations

from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
REQUIRED = ("android", "backend", "protocol", "tools", "README.md")
SECRET_PATTERNS = (
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    re.compile(r"(?i)\b(?:api[_-]?key|secret[_-]?key|access[_-]?token)\s*[:=]\s*[\"']?[A-Za-z0-9_\-]{16,}"),
)
IGNORED = {".git", ".gradle", "__pycache__", ".venv", "node_modules", "build"}


def iter_text_files():
    for path in ROOT.rglob("*"):
        if not path.is_file() or any(part in IGNORED for part in path.parts):
            continue
        if path.suffix.lower() in {".md", ".py", ".toml", ".yml", ".yaml", ".json", ".kt", ".kts", ".xml", ".properties", ".java", ".sh", ".cfg", ".txt"}:
            yield path


def main() -> int:
    errors: list[str] = []
    for relative in REQUIRED:
        if not (ROOT / relative).exists():
            errors.append(f"missing required path: {relative}")
    for path in iter_text_files():
        text = path.read_text(encoding="utf-8", errors="ignore")
        for pattern in SECRET_PATTERNS:
            if pattern.search(text) and path.name != "check_repo.py":
                errors.append(f"possible secret marker: {path.relative_to(ROOT)}")
                break
    if errors:
        print("Repository check failed:")
        print("\n".join(f"- {error}" for error in errors))
        return 1
    print(f"Repository check passed: {len(REQUIRED)} required paths; secret scan passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
