"""Validation syntaxique minimale de tous les modules source."""

from __future__ import annotations

from pathlib import Path


def test_all_source_modules_compile() -> None:
    root = Path(__file__).resolve().parents[1] / "src" / "howimetyourcorpus"
    failures: list[str] = []
    for py_file in sorted(root.rglob("*.py")):
        source = py_file.read_text(encoding="utf-8")
        try:
            compile(source, str(py_file), "exec")
        except SyntaxError as exc:
            failures.append(f"{py_file}: {exc.msg} (line {exc.lineno})")
    assert not failures, "Syntax errors found:\n" + "\n".join(failures)
