"""Load the generated CSVs into Neo4j using the model in graph_spec.py. Usage: python -m etg.load_neo4j"""
from __future__ import annotations

import csv
import os
from pathlib import Path

from neo4j import GraphDatabase

from .graph_spec import BOOLEAN, NODES, NUMERIC, RELS

ROOT = Path(__file__).resolve().parents[2]
BATCH = 2000


def convert(key: str, value: str):
    if value == "":
        return None
    if key in NUMERIC:
        return float(value)
    if key in BOOLEAN:
        return value.lower() == "true"
    return value


def read(data_dir: Path, name: str) -> list[dict]:
    with open(data_dir / f"{name}.csv", newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def chunks(rows, n=BATCH):
    for i in range(0, len(rows), n):
        yield rows[i:i + n]


def main(data_dir: Path = ROOT / "data" / "out") -> None:
    driver = GraphDatabase.driver(os.getenv("NEO4J_URI", "bolt://localhost:7687"),
                                  auth=(os.getenv("NEO4J_USER", "neo4j"), os.getenv("NEO4J_PASSWORD", "etgpassword")))
    with driver, driver.session() as s:
        s.run("MATCH (n) DETACH DELETE n").consume()
        for label in NODES:
            s.run(f"CREATE CONSTRAINT {label.lower()}_id IF NOT EXISTS FOR (n:{label}) REQUIRE n.id IS UNIQUE").consume()
        for label, (csvname, idcol, props) in NODES.items():
            rows = [{"id": r[idcol], **{p: convert(p, r[p]) for p in props}} for r in read(data_dir, csvname)]
            for part in chunks(rows):
                s.run(f"UNWIND $rows AS r CREATE (n:{label}) SET n += r", rows=part).consume()
            print(f"node {label:16s} {len(rows):>6d}")
        for rel, csvname, fl, fc, tl, tc, eprops in RELS:
            rows = []
            for r in read(data_dir, csvname):
                if r[fc] and r[tc]:
                    rows.append({"a": r[fc], "b": r[tc], "p": {k: convert(k, r[k]) for k in eprops}})
            for part in chunks(rows):
                s.run(f"UNWIND $rows AS r MATCH (a:{fl} {{id: r.a}}) MATCH (b:{tl} {{id: r.b}}) "
                      f"CREATE (a)-[x:{rel}]->(b) SET x += r.p", rows=part).consume()
            print(f"rel  {rel:18s} {fl}->{tl}: {len(rows)}")


if __name__ == "__main__":
    main()
