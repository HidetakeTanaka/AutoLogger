""" 
parser.py - AST Parser for AutoLogger
AST: Abstract Syntax Tree: to understand the code structure
-------------------------------------
Detects candidate positions for inserting logging statements. 
Provides a Python API(extract_candidates) and a CLI that
outputs a JSON file describing all candidates. 
"""
""" Shift + Option + A: comment multiple lines """

import ast
import json
import sys
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import List, Dict, Any, Optional

# ===== Helper function: safe unparse =====
def _safe_unparse(node: ast.AST) -> str: 
    """Try ast.unparse if available, otherwise fall back to a simple placeholder!"""
    try:
        return ast.unparse(node).strip() # type: ignore[attr-defined]
    except Exception:
        if isinstance(node, ast.Return):
            return "return ..."
        return node.__class__.__name__


# ===== Helper function to extract variable names [collect vars in scope] =====
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


# ===== Core data model =====
@dataclass
class LoggingCandidate:
    kind: str                   # "func_entry", "before_return", "except", ...
    line: int
    end_line: int
    function: Optional[str]
    class_name: Optional[str]
    code: str                   # short code snippet or description
    vars_in_scope: List[str]    # variable names visible here
    why: str                    # explanation why this is a candidate
    severity_hint: str          # e.g., "DEBUG", "INFO", "ERROR"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ===== Core visitor class =====
class LogCandidateVisitor(ast.NodeVisitor):
    def __init__(self, source: str, file_path: str):
        self.source = source
        self.file_path = file_path
        self.candidates: List[LoggingCandidate] = []
        self._func_stack: List[ast.FunctionDef] = []
        self._class_stack: List[ast.ClassDef] = []

    # ===== Helpers for current context =====   
    @property
    def current_function(self) -> Optional[ast.FunctionDef]:
        return self._func_stack[-1] if self._func_stack else None
    
    @property
    def current_function_name(self) -> Optional[str]:
        return self.current_function.name if self.current_function else None
    
    @property
    def current_class_name(self) -> Optional[str]:
        return self._class_stack[-1].name if self._class_stack else None
    

    # --- AST Visitors ---
    def visit_ClassDef(self, node: ast.ClassDef):
        self._class_stack.append(node)
        self.generic_visit(node)
        self._class_stack.pop()
    

    def visit_FunctionDef(self, node:ast.FunctionDef):
        self._func_stack.append(node)

        # 1: function entry: try to point to the first body line if present, else def line 
        entry_line = node.body[0].lineno if node.body else node.lineno

        # try to get the full signature from source
        sig = ast.get_source_segment(self.source, node) or f"def {node.name}(...)"

        self.candidates.append(
            LoggingCandidate(
                kind =          "func_entry",
                line =          entry_line,
                end_line =      entry_line,
                function =      node.name,
                class_name =    self.current_class_name,
                code =          sig.splitlines()[0],    # only first line of signature
                vars_in_scope = get_vars_in_scope(node),
                why =           "function entry",
                severity_hint = "DEBUG",
            )
        )

        self.generic_visit(node)
        self._func_stack.pop()

    
    def visit_Return(self, node: ast.Return):
        # 2: before return (inside a function)
        if self.current_function is not None:
            vars_in_scope = get_vars_in_scope(self.current_function)
        else:
            vars_in_scope = []
        
        self.candidates.append(
            LoggingCandidate(
                kind =          "before_return",
                line =          node.lineno,
                end_line =      node.lineno,
                function =      self.current_function_name,
                class_name =    self.current_class_name,
                code =          _safe_unparse(node),
                vars_in_scope = vars_in_scope,
                why =           "before return",
                severity_hint = "INFO",
            )
        )
        
        self.generic_visit(node)
       

    def visit_ExceptHandler(self, node: ast.ExceptHandler):
        # 3: choose a sensible insertion line: first stmt inside expect if present; else the except line
        line = node.body[0].lineno if getattr(node, "body", None) else node.lineno

        if self.current_function is not None:
            vars_in_scope = get_vars_in_scope(self.current_function)
        else:
            vars_in_scope = []
            
        self.candidates.append(
            LoggingCandidate(
                kind =          "except",
                line =          line,
                end_line =      line,
                function =      self.current_function_name,
                class_name =    self.current_class_name,
                code =          "except ...",
                vars_in_scope = vars_in_scope,
                why =           "inside except",
                severity_hint = "ERROR",
            )
        )

        self.generic_visit(node)

# ===== Public API =====
def extract_candidates(source_code: str, file_path: str = "<memory>") -> List[LoggingCandidate]:
    """ 
    Core API: parse Python source code and return a list of LoggingCandidate objects.
    This is what the LLM / baseline modules should use.
    """
    tree = ast.parse(source_code)
    visitor = LogCandidateVisitor(source_code, file_path)
    visitor.visit(tree)
    return visitor.candidates



def parse_file(file_path: str) -> Dict[str, Any]:
    """ 
    Convenience wrapper: read a file and return a JSON-serializable dict.
    This is mainly for the CLI and for dataset generation.
    """
    src = Path(file_path).read_text(encoding="utf-8")
    candidates = extract_candidates(src, file_path=file_path)
    return {
        "file": file_path,
        "candidates": [c.to_dict() for c in candidates],
    }


# ===== CLI entrypoint =====
if __name__ == "__main__":
    # Command-line execution
    if len(sys.argv) < 2:
        print("Usage: python parser.py <source_file.py>")
        sys.exit(1)
    
    src_path = Path(sys.argv[1])
    result = parse_file(str(src_path))
    out_path = src_path.with_suffix(".candidates.json")
    out_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    
    print(f"✅ Parsed {src_path.name} -> {out_path.name}")
    print(f"Found {len(result['candidates'])} candidates in {src_path.name}")
    





    
    