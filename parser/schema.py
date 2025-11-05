"""
schema.py; Shared JSON schema definitions for AutoLogger
---------------------------------------------------------
All modules (parser, LLM integration, baselines, evaluation)
must follow these structures to ensure consistent data exchange;)
"""

from typing import List, Literal, Optional, TypedDict


# ===== Candidate schema (output of parser) =====
class Candidate(TypedDict):
    kind: Literal["func_entry", "before_return", "except", "after_call", "loop_iter"]
    line: int
    end_line: Optional[int]
    function: Optional[str]
    class_: Optional[str]
    code: str
    vars_in_scope: List[str]
    why: str
    severity_hint: Literal["DEBUG", "INFO", "WARNING", "ERROR"]


class ParserOutput(TypedDict):
    file: str
    candidates: List[Candidate]


# ===== Log specification schema (output of LLM / baselines) =====
class LogSpec(TypedDict):
    idx: int
    level: Literal["DEBUG", "INFO", "WARNING", "ERROR"]
    message: str
    extra_vars: List[str]
    dedupe_key: str


class LogOutput(TypedDict):
    file: str
    logs: List[LogSpec]


# ===== Evaluation metrics schema =====
class EvalMetrics(TypedDict):
    file: str
    total_candidates: int
    total_logs: int
    precision: float
    recall: float
    f1: float
    bleu: Optional[float]


__all__ = ["Candidate", "ParserOutput", "LogSpec", "LogOutput", "EvalMetrics"]
