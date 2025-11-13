""" 
parser.py - AST Parser for AutoLogger
AST: Abstract Syntax Tree: to understand the code structure
-------------------------------------
Detects candidate positions for inserting logging statements. 
Outputs a JSON file describing all candidates. 
"""
""" Shift + Option + A: comment multiple lines """

import ast
import json
import sys
from pathlib import Path
from typing import List, Dict, Any, Optional

def _safe_unparse(node: ast.AST) -> str: # Python 3.9 may not have ast.unparse; fall back to a readable placeholder
    try:
        return ast.unparse(node).strip() # type: ignore[attr-defined]
    except Exception:
        if isinstance(node, ast.Return):
            return "return ..."
        return node.__class__.__name__


# ===== Helper function to extract variable names =====
def get_vars_in_scope(func_node: ast.FunctionDef) -> List[str]:
    """ Collect variable names visible inside the function (args + assigned names). """
    vars_: set[str] = set()

    # --- function arguments ---
    for arg in func_node.args.args:
        vars_.add(arg.arg)
    if func_node.args.vararg:
        vars_.add(func_node.args.vararg.arg)
    if func_node.args.kwarg:
        vars_.add(func_node.args.kwarg.arg)

    # --- variable assignments ---
    for child in ast.walk(func_node):
        if isinstance(child, ast.Assign):
            for t in child.targets:
                if isinstance(t, ast.Name):
                    vars_.add(t.id)
        elif isinstance(child, ast.AnnAssign) and isinstance(child.target, ast.Name):
            vars_.add(child.target.id)       
    return sorted(vars_)

# ===== Core visitor class =====
class LogCandidateVisitor(ast.NodeVisitor):
    def __init__(self):
        self.candidates: List[Dict[str, Any]] = []
        self._func_stack: List[ast.FunctionDef] = []
    
    @property
    def current_function(self) -> Optional[str]:
        return self._func_stack[-1].name if self._func_stack else None
    

    def visit_FunctionDef(self, node:ast.FunctionDef):
        self._func_stack.append(node)
        # 1: function entry: try to point to the first body line if present, else def line 
        entry_line = node.body[0].lineno if node.body else node.lineno
        self.candidates.append({
            "kind": "func_entry",
            "line": entry_line,
            "end_line": entry_line,
            "function": node.name,
            "class": None,
            "code": f"def {node.name}(...):",
            "vars_in_scope": get_vars_in_scope(node),
            "why": "function entry",
            "severity_hint": "DEBUG",
        })
        self.generic_visit(node)
        self._func_stack.pop()

    
    def visit_Return(self, node: ast.Return):
        # 2: before return
        self.candidates.append({
            "kind": "before_return",
            "line": node.lineno,
            "end_line": node.lineno,
            "function": self.current_function,
            "class": None, 
            "code": _safe_unparse(node),
            "vars_in_scope": [],  # keep simple for MVP
            "why": "before return",
            "severity_hint": "INFO",
        })

    def visit_ExceptHandler(self, node: ast.ExceptHandler):
        # 3: choose a sensible insertion line: first stmt inside expect if present; else the except line
        line = node.body[0].lineno if getattr(node, "body", None) else node.lineno

        self.candidates.append({
            "kind": "except",
            "line": line,
            "end_line": line,
            "function": self.current_function,
            "class": None, 
            "code": "except ...",
            "vars_in_scope": [],  
            "why": "inside except",
            "severity_hint": "ERROR",
        })
        self.generic_visit(node)

# ===== Main execution =====
def parse_file(file_path: str) -> Dict[str, Any]:
    src = Path(file_path).read_text(encoding="utf-8")
    tree = ast.parse(src)
    visitor = LogCandidateVisitor()
    visitor.visit(tree)
    return {"file": file_path, "candidates": visitor.candidates}

if __name__ == "__main__":
    # Command-line execution
    if len(sys.argv) <2:
        print("Usage: python parser.py <source_file.py>")
        sys.exit(1)
    src_path = Path(sys.argv[1])
    result = parse_file(str(src_path))
    out_path = src_path.with_suffix(".candidates.json")
    out_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(f"✅ Parsed {src_path.name} -> {out_path.name}")
    print(f"Found {len(result['candidates'])} candidates in {src_path.name}")
    





    
    