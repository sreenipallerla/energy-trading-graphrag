"""Usage:
  python -m etg.rag schema                 show the schema text sent to the model
  python -m etg.rag embed                  embed Document nodes and build the vector index
  python -m etg.rag ask "your question"    answer from graph + documents
  python -m etg.rag eval                   run the evals and save evals/results-<model>.json
Provider: LLM_PROVIDER=ollama (default) or azure.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from neo4j import GraphDatabase

from ..envfile import load_env
from .evals import build_golden, run_evals, save
from .pipeline import GraphRAG
from .providers import make_embedder, make_llm
from .retrieval import embed_documents
from .schema import schema_text

ROOT = Path(__file__).resolve().parents[3]


def driver():
    return GraphDatabase.driver(os.getenv("NEO4J_URI", "bolt://localhost:7687"),
                                auth=(os.getenv("NEO4J_USER", "neo4j"), os.getenv("NEO4J_PASSWORD", "etgpassword")))


def main() -> None:
    load_env()
    ap = argparse.ArgumentParser(prog="etg.rag")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("schema")
    sub.add_parser("embed")
    a = sub.add_parser("ask")
    a.add_argument("question")
    e = sub.add_parser("eval")
    e.add_argument("--runs", type=int, default=1, help="repeat each question N times")
    args = ap.parse_args()

    if args.cmd == "schema":
        print(schema_text())
        return
    with driver() as d:
        emb = make_embedder()
        if args.cmd == "embed":
            n = embed_documents(d, emb)
            print(f"embedded {n} documents with {emb.name} and built the vector index")
            return
        llm = make_llm()
        rag = GraphRAG(d, llm, emb)
        if args.cmd == "ask":
            out = rag.ask(args.question)
            print(f"\nModel: {out['model']}\nCypher:\n{out['cypher']}\n\nAnswer:\n{out['answer']}")
            print(f"\nDocuments retrieved: {', '.join(out['docs']) or 'none'}")
            if out["error"]:
                print(f"Graph query problem: {out['error']}")
        else:
            truth = json.loads((ROOT / "data" / "out" / "ground_truth.json").read_text())
            results = run_evals(rag, build_golden(truth), runs=args.runs)
            for r in results:
                ok = round(r["pass_rate"] * r["runs"])
                print(f"{'PASS' if r['passed'] else 'FAIL'} {r['id']:14s} passed {ok}/{r['runs']} runs  "
                      f"cypher_recall={r['cypher_recall']} answer_recall={r['answer_recall']} "
                      f"answer_precision={r['answer_precision']}")
            safe = llm.name.replace(":", "_").replace("/", "_")
            save(results, ROOT / "evals" / f"results-{safe}.json")
            total = sum(round(r["pass_rate"] * r["runs"]) for r in results)
            print(f"{total}/{len(results) * args.runs} question-runs passed; saved evals/results-{safe}.json")


if __name__ == "__main__":
    main()
