"""Check both databases against ground_truth.json.  Usage: python scripts/verify.py [--skip-neo4j]"""
import json
import os
import sys
from pathlib import Path

import psycopg

ROOT = Path(__file__).resolve().parents[1]
truth = json.loads((ROOT / "data" / "out" / "ground_truth.json").read_text())
ok = True


def check(name, got, want):
    global ok
    good = got == want
    ok &= good
    print(("PASS " if good else "FAIL ") + name + ("" if good else f"\n  got  {got}\n  want {want}"))


with psycopg.connect(os.getenv("PG_DSN", "postgresql://etg:etg@localhost:5433/etg")) as c:
    check("postgres: trade count", c.execute("SELECT count(*) FROM etg.trade").fetchone()[0], truth["trade_count"])
    breaches = [r[0] for r in c.execute(
        "SELECT counterparty_id FROM etg.v_exposure WHERE exposure_eur > limit_eur ORDER BY 1")]
    check("postgres: limit breaches", breaches, truth["limit_breaches"])

if "--skip-neo4j" not in sys.argv:
    from neo4j import GraphDatabase

    d = GraphDatabase.driver(os.getenv("NEO4J_URI", "bolt://localhost:7687"),
                             auth=(os.getenv("NEO4J_USER", "neo4j"), os.getenv("NEO4J_PASSWORD", "etgpassword")))
    with d, d.session() as s:
        check("neo4j: trade nodes", s.run("MATCH (t:Trade) RETURN count(t) AS n").single()["n"], truth["trade_count"])
        got = [r["id"] for r in s.run("""
            MATCH (:WatchlistEntry)-[:MATCHES]->(p:Person)-[o:OWNS]->(h:Company)
            WHERE o.pct >= 25
            MATCH (c:Company)-[:SUBSIDIARY_OF*1..3]->(h)
            MATCH (cp:Counterparty)-[:IS_COMPANY]->(c)
            RETURN DISTINCT cp.id AS id ORDER BY id""")]
        check("neo4j: hidden sanctions counterparties", got, truth["hidden_sanctions"]["counterparties"])

        def ids(q):
            return [r["id"] for r in s.run(q)]

        # Reference queries: the definitions the GraphRAG prompt teaches the model (see rag/schema.py).
        check("neo4j: reference query, limit breaches", ids("""
            MATCH (cp:Counterparty)-[:HAS_LIMIT]->(l:CreditLimit)
            MATCH (t:Trade {status: 'open'})-[:WITH]->(cp)
            WITH cp, l, sum(t.mtm_eur) AS net WHERE net > l.limit_eur
            RETURN cp.id AS id ORDER BY id"""), truth["limit_breaches"])
        check("neo4j: reference query, downgrades", ids("""
            MATCH (cp:Counterparty)-[:HAS_RATING]->(r:CreditRating)
            WHERE r.rated_on >= '2026-07-20' AND r.rating IN ['BB+','BB','BB-','B+','B','CCC']
            RETURN DISTINCT cp.id AS id ORDER BY id"""), truth["downgraded_below_ig_last_90d"])
        check("neo4j: reference query, concentration", ids("""
            MATCH (t:Trade)-[:WITH]->(cp:Counterparty)
            WITH cp, sum(t.notional_eur) AS n ORDER BY n DESC LIMIT 1 RETURN cp.id AS id"""),
              [truth["top_concentration"]["counterparty"]])
sys.exit(0 if ok else 1)
