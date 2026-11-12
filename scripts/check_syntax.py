"""Parse project Python sources without writing bytecode caches."""

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCES = [ROOT / "app.py", ROOT / "create_demo.py"]
SOURCES.extend((ROOT / "app").glob("*.py"))
SOURCES.extend((ROOT / "tests").glob("test_*.py"))

for source in SOURCES:
    ast.parse(source.read_text(encoding="utf-8"), filename=str(source))

print(f"Python syntax OK ({len(SOURCES)} files)")
