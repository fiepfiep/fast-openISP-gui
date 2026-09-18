"""Print the section of docs/release-notes.md for one version (used by the release workflow).

Usage: python scripts/release_notes.py v0.2.0 > dist/RELEASE_NOTES.md
"""

import re
import sys
from pathlib import Path

NOTES = Path(__file__).resolve().parents[1] / "docs" / "release-notes.md"


def section(tag: str) -> str:
    text = NOTES.read_text(encoding="utf-8")
    # Sections start with "## v<version>"; take everything up to the next one
    parts = re.split(r"^## ", text, flags=re.MULTILINE)
    for part in parts[1:]:
        heading, _, body = part.partition("\n")
        if heading.split()[0] == tag:
            return f"## {heading}\n{body}".strip() + "\n"
    raise SystemExit(f"No section for {tag} in {NOTES.name}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    sys.stdout.write(section(sys.argv[1]))
