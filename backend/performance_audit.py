"""Static performance audit for the FastAPI backend.

The audit is intentionally conservative: it reports suspicious constructs and
can be made blocking with PERF_AUDIT_STRICT=1.  CI currently runs it in report
mode so legacy findings are visible while the codebase is migrated incrementally.
"""
from __future__ import annotations

import ast
import os
from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).resolve().parent
STRICT = os.environ.get("PERF_AUDIT_STRICT", "0").strip() == "1"


def dotted_name(node: ast.AST) -> str:
    parts: list[str] = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name):
        parts.append(node.id)
    return ".".join(reversed(parts))


def iter_python_files() -> Iterable[Path]:
    for path in ROOT.rglob("*.py"):
        if any(part in {".venv", "venv", "__pycache__"} for part in path.parts):
            continue
        yield path


class AsyncBlockingVisitor(ast.NodeVisitor):
    def __init__(self, path: Path) -> None:
        self.path = path
        self.async_depth = 0
        self.findings: list[tuple[str, int, str]] = []

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self.async_depth += 1
        self.generic_visit(node)
        self.async_depth -= 1

    def visit_Call(self, node: ast.Call) -> None:
        name = dotted_name(node.func)
        if self.async_depth:
            if name == "time.sleep":
                self.findings.append(("CRITICAL", node.lineno, "time.sleep inside async function"))
            if name.startswith("requests."):
                self.findings.append(("CRITICAL", node.lineno, f"sync HTTP call inside async function: {name}"))
            if name in {"pymongo.MongoClient", "MongoClient"}:
                self.findings.append(("CRITICAL", node.lineno, "sync PyMongo client created inside async function"))

            if name.endswith("to_list"):
                size = None
                if node.args and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, int):
                    size = node.args[0].value
                for kw in node.keywords:
                    if kw.arg == "length" and isinstance(kw.value, ast.Constant) and isinstance(kw.value.value, int):
                        size = kw.value.value
                if size is not None and size > 500:
                    self.findings.append(("WARN", node.lineno, f"large Mongo to_list(length={size})"))

        self.generic_visit(node)


def audit_file(path: Path) -> list[tuple[str, int, str]]:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except SyntaxError as exc:
        return [("CRITICAL", exc.lineno or 0, f"syntax error: {exc.msg}")]
    visitor = AsyncBlockingVisitor(path)
    visitor.visit(tree)
    return visitor.findings


def main() -> int:
    findings: list[tuple[Path, str, int, str]] = []
    for path in iter_python_files():
        for severity, line, message in audit_file(path):
            findings.append((path, severity, line, message))

    print("=== Gestionale Elios Tech performance audit ===")
    if not findings:
        print("OK: no suspicious blocking patterns found")
        return 0

    critical = 0
    for path, severity, line, message in findings:
        rel = path.relative_to(ROOT)
        print(f"{severity:8} {rel}:{line}: {message}")
        if severity == "CRITICAL":
            critical += 1

    print(f"Findings: {len(findings)} (critical={critical})")
    if STRICT and critical:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
