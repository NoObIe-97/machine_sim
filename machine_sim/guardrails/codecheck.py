"""AST-level anthropomorphic checker."""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Dict, List

FORBIDDEN_ASSIGNMENTS = {"goal", "desire", "emotion", "feeling", "belief", "motive"}
FORBIDDEN_CLASS_BASES = {
    "SocialAgent", "EmotionalAgent", "LanguageAgent", "GoalAgent",
    "SentientAgent", "ConsciousAgent",
}
FORBIDDEN_PARAMS = {"goal", "desire", "emotion", "feeling", "belief"}


class AnthropomorphicChecker(ast.NodeVisitor):
    def __init__(self) -> None:
        self.violations: List[Dict] = []

    def visit_Assign(self, node: ast.Assign) -> None:
        for target in node.targets:
            if isinstance(target, ast.Name) and target.id.lower() in FORBIDDEN_ASSIGNMENTS:
                self.violations.append({
                    "line": node.lineno,
                    "type": "forbidden_assignment",
                    "name": target.id,
                })
        self.generic_visit(node)

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        for base in node.bases:
            if isinstance(base, ast.Name) and base.id in FORBIDDEN_CLASS_BASES:
                self.violations.append({
                    "line": node.lineno,
                    "type": "forbidden_base_class",
                    "name": base.id,
                })
        self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        for arg in node.args.args:
            if arg.arg.lower() in FORBIDDEN_PARAMS:
                self.violations.append({
                    "line": node.lineno,
                    "type": "forbidden_parameter",
                    "name": arg.arg,
                })
        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        for arg in node.args.args:
            if arg.arg.lower() in FORBIDDEN_PARAMS:
                self.violations.append({
                    "line": node.lineno,
                    "type": "forbidden_parameter",
                    "name": arg.arg,
                })
        self.generic_visit(node)


def check_ast(filepath: Path) -> List[Dict]:
    """Parse a Python file and check for anthropomorphic AST patterns."""
    with open(filepath, "r", encoding="utf-8") as f:
        source = f.read()
    tree = ast.parse(source, filename=str(filepath))
    checker = AnthropomorphicChecker()
    checker.visit(tree)
    return checker.violations
