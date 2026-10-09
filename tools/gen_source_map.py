"""Regenerate docs/SOURCE_MAP.md from docs/source_map.json and the live route table."""
import sys
from pathlib import Path

root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root))

import main  # noqa: E402
from managers.source_map import SourceMap  # noqa: E402

(root / "docs" / "SOURCE_MAP.md").write_text(SourceMap(main.app, root).markdown(), encoding="utf-8", newline="\n")
print("Wrote docs/SOURCE_MAP.md")