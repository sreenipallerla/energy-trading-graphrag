"""Safety checks for model-written Cypher. The model proposes; this code decides what is allowed to run."""
from __future__ import annotations

import re

FORBIDDEN = re.compile(r"\b(CREATE|MERGE|DELETE|DETACH|SET|REMOVE|DROP|LOAD|FOREACH|CALL|APOC|DBMS)\b", re.I)
START = re.compile(r"^\s*(MATCH|OPTIONAL\s+MATCH|WITH|UNWIND|RETURN)\b", re.I)


class UnsafeCypher(ValueError):
    pass


def _strip_literals(q: str) -> str:
    q = re.sub(r"'(?:[^'\\]|\\.)*'", "''", q)
    q = re.sub(r'"(?:[^"\\]|\\.)*"', '""', q)
    return re.sub(r"`[^`]*`", "``", q)


def extract_cypher(text: str) -> str:
    """Pull the query out of a model reply (fenced block if present)."""
    m = re.search(r"```(?:cypher)?\s*(.*?)```", text, re.S | re.I)
    return (m.group(1) if m else text).strip()


def validate(query: str, default_limit: int = 100) -> str:
    q = query.strip().rstrip(";").strip()
    if not q:
        raise UnsafeCypher("empty query")
    bare = _strip_literals(q)
    if ";" in bare:
        raise UnsafeCypher("only one statement is allowed")
    if not START.match(bare):
        raise UnsafeCypher("query must start with MATCH, WITH, UNWIND or RETURN")
    bad = FORBIDDEN.search(bare)
    if bad:
        raise UnsafeCypher(f"read-only queries only; found {bad.group(1).upper()}")
    if not re.search(r"\bRETURN\b", bare, re.I):
        raise UnsafeCypher("query has no RETURN")
    if not re.search(r"\bLIMIT\s+\d+", bare, re.I):
        q += f" LIMIT {default_limit}"
    return q
