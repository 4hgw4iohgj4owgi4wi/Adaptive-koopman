"""AST-only audit for references to retired connector implementations."""

from __future__ import annotations

import ast
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable


@dataclass(frozen=True)
class AuditFinding:
    path: str
    line: int
    column: int
    kind: str
    symbol: str


def _root_name(node: ast.AST) -> str | None:
    while isinstance(node, ast.Attribute):
        node = node.value
    return node.id if isinstance(node, ast.Name) else None


def _constant_string(node: ast.AST) -> str | None:
    return node.value if isinstance(node, ast.Constant) and isinstance(node.value, str) else None


def audit_source(
    source: str,
    *,
    path: str = "<memory>",
    forbidden_modules: Iterable[str] = ("four_vehicle_coupled",),
    forbidden_symbols: Iterable[str] = ("ConnectorParams",),
) -> list[AuditFinding]:
    """Return only executable syntax references; comments and string literals are ignored."""
    tree = ast.parse(source, filename=path)
    modules = tuple(forbidden_modules)
    symbols = frozenset(forbidden_symbols)
    findings: list[AuditFinding] = []

    def add(node: ast.AST, kind: str, symbol: str) -> None:
        findings.append(
            AuditFinding(path, getattr(node, "lineno", 0), getattr(node, "col_offset", 0), kind, symbol)
        )

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if any(alias.name == item or alias.name.startswith(item + ".") for item in modules):
                    add(node, "import", alias.name)
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if any(module == item or module.startswith(item + ".") for item in modules):
                add(node, "import_from", module)
        elif isinstance(node, ast.Call) and node.args:
            value = _constant_string(node.args[0])
            if value and any(value == item or value.startswith(item + ".") for item in modules):
                if isinstance(node.func, ast.Name) and node.func.id == "__import__":
                    add(node, "dynamic_import", value)
                elif (
                    isinstance(node.func, ast.Attribute)
                    and node.func.attr == "import_module"
                    and _root_name(node.func) == "importlib"
                ):
                    add(node, "dynamic_import", value)
        elif isinstance(node, ast.Name) and node.id in symbols:
            add(node, "retired_symbol", node.id)
        elif isinstance(node, ast.Attribute) and node.attr in symbols:
            add(node, "retired_attribute", node.attr)
    return findings


def audit_paths(paths: Iterable[Path], root: Path | None = None) -> list[dict]:
    results: list[AuditFinding] = []
    for path in paths:
        display = path.relative_to(root).as_posix() if root is not None else str(path)
        results.extend(audit_source(path.read_text(encoding="utf-8"), path=display))
    return [asdict(item) for item in results]
