"""Evals built from ground_truth.json. Scores two things separately:
  cypher_recall  - did the graph query's rows contain the right counterparties? (text-to-Cypher quality)
  answer_recall / answer_precision - did the final written answer name exactly the right ones?
Comparing the two shows whether a wrong answer came from the query or from the writing.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

ID = re.compile(r"\bCP\d{3}\b")


def build_golden(truth: dict) -> list[dict]:
    return [
        {"id": "sanctions", "question": "Which counterparties have hidden sanctions exposure, meaning a sanctioned "
         "person owns at least 25 percent of a company above them in the ownership chain?",
         "expected": truth["hidden_sanctions"]["counterparties"]},
        {"id": "downgrades", "question": "Which counterparties have a current credit rating below investment grade, "
         "having been downgraded in the last 90 days?", "expected": truth["downgraded_below_ig_last_90d"]},
        {"id": "limits", "question": "Which counterparties have net exposure above their credit limit?",
         "expected": truth["limit_breaches"]},
        {"id": "concentration", "question": "Which single counterparty has the largest share of total trade notional?",
         "expected": [truth["top_concentration"]["counterparty"]]},
    ]


def ids_in(text: str) -> set[str]:
    return set(ID.findall(text))


def score(expected: list[str], found: set[str]) -> tuple[float, float]:
    exp = set(expected)
    hit = len(exp & found)
    recall = hit / len(exp) if exp else 1.0
    precision = hit / len(found) if found else 0.0
    return recall, precision


def _one(pipeline, g: dict) -> dict:
    out = pipeline.ask(g["question"])
    c_rec, _ = score(g["expected"], ids_in(json.dumps(out["rows"], default=str)))
    a_rec, a_prec = score(g["expected"], ids_in(out["answer"]))
    return {"model": out["model"], "cypher_recall": c_rec, "answer_recall": a_rec, "answer_precision": a_prec,
            "passed": a_rec == 1.0 and a_prec >= 0.8, "error": out["error"], "cypher": out["cypher"]}


def run_evals(pipeline, golden: list[dict], runs: int = 1) -> list[dict]:
    """Run every question `runs` times; report the pass rate and the mean scores."""
    results = []
    for g in golden:
        rs = [_one(pipeline, g) for _ in range(runs)]
        mean = lambda k: round(sum(r[k] for r in rs) / runs, 2)
        results.append({"id": g["id"], "model": rs[-1]["model"], "runs": runs,
                        "pass_rate": round(sum(r["passed"] for r in rs) / runs, 2),
                        "cypher_recall": mean("cypher_recall"), "answer_recall": mean("answer_recall"),
                        "answer_precision": mean("answer_precision"),
                        "passed": all(r["passed"] for r in rs), "error": rs[-1]["error"],
                        "cypher": rs[-1]["cypher"], "per_run": rs})
    return results


def save(results: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(results, indent=2))
