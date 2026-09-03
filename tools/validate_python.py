import ast
from pathlib import Path


root = Path(__file__).resolve().parent.parent
files = list(root.rglob("*.py"))
for path in files:
    ast.parse(path.read_text(encoding="ascii"), filename=str(path))

print("AST syntax OK: %d files" % len(files))
