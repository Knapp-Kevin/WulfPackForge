"""Section 4 Simplicity Razor, enforced: files, functions, nesting, and ternaries stay small."""
import ast
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
SCAN_DIRS = ("data", "subscripts", "ui", "tools")
MAX_FILE_LINES = 250
MAX_FUNCTION_LINES = 40
MAX_NESTING = 3
NESTING_NODES = (ast.If, ast.For, ast.While, ast.With, ast.Try, ast.AsyncFor, ast.AsyncWith)
SCOPE_NODES = (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)
NO_QT_DIRS = ("data", "subscripts")  # the UI layer is the only place PySide6 may appear


def source_files():
    files = [ROOT / "main.py"]
    for directory in SCAN_DIRS:
        files.extend(sorted((ROOT / directory).rglob("*.py")))
    return files


def nesting_depth(node, level=0):
    worst = level
    for child in ast.iter_child_nodes(node):
        if isinstance(child, NESTING_NODES):
            worst = max(worst, nesting_depth(child, level + 1))
        elif not isinstance(child, SCOPE_NODES):
            worst = max(worst, nesting_depth(child, level))
    return worst


def violations_in(path):
    source = path.read_text(encoding="utf-8")
    rel = path.relative_to(ROOT).as_posix()
    found = []
    line_count = len(source.splitlines())
    if line_count > MAX_FILE_LINES:
        found.append(f"{rel}: {line_count} lines (max {MAX_FILE_LINES})")
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            span = node.end_lineno - node.lineno + 1
            if span > MAX_FUNCTION_LINES:
                found.append(f"{rel}:{node.lineno} {node.name} is {span} lines (max {MAX_FUNCTION_LINES})")
            depth = nesting_depth(node)
            if depth > MAX_NESTING:
                found.append(f"{rel}:{node.lineno} {node.name} nests {depth} deep (max {MAX_NESTING})")
        if isinstance(node, ast.IfExp) and any(isinstance(part, ast.IfExp) for part in (node.body, node.orelse)):
            found.append(f"{rel}:{node.lineno} nested ternary")
        if isinstance(node, ast.ImportFrom) and any(alias.name == "*" for alias in node.names):
            found.append(f"{rel}:{node.lineno} star import from {node.module}")
        if rel.split("/")[0] in NO_QT_DIRS and _imports_qt(node):
            found.append(f"{rel}:{node.lineno} PySide6 import below the UI layer")
        if _connects_self_lambda(node):
            found.append(f"{rel}:{node.lineno} signal connected to a lambda capturing self (freed by GC, not deterministically)")
    return found


def _connects_self_lambda(node) -> bool:
    if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "connect"):
        return False
    return any(isinstance(arg, ast.Lambda) and any(isinstance(n, ast.Name) and n.id == "self" for n in ast.walk(arg))
               for arg in node.args)


def _imports_qt(node) -> bool:
    if isinstance(node, ast.ImportFrom):
        return bool(node.module and node.module.startswith("PySide6"))
    if isinstance(node, ast.Import):
        return any(alias.name.startswith("PySide6") for alias in node.names)
    return False


def razor_violations():
    return [violation for path in source_files() for violation in violations_in(path)]


class RazorTests(unittest.TestCase):
    def test_source_meets_the_simplicity_razor(self):
        found = razor_violations()
        self.assertEqual(found, [], "\n" + "\n".join(found))


if __name__ == "__main__":
    unittest.main()
