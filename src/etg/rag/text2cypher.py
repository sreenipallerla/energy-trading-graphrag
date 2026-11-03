"""Question -> Cypher -> rows, with a read-only guard and one repair attempt."""
from __future__ import annotations

import json

from .guard import UnsafeCypher, extract_cypher, validate
from .schema import DOMAIN_NOTES, schema_text

SYSTEM = f"""You translate questions about an energy trading company's graph database into ONE read-only Cypher query.
Return only the query inside a ```cypher fenced block. No explanation.

{{schema}}

{DOMAIN_NOTES}
Query rules:
- Only MATCH, OPTIONAL MATCH, WITH, UNWIND, WHERE, RETURN, ORDER BY, LIMIT. Never write data.
- Return ids and the values asked for, with readable aliases (for example cp.id AS counterparty).
- Use only the labels, properties and relationships listed above.

Examples (patterns, not answers):
Q: How many trades does counterparty CP010 have?
```cypher
MATCH (t:Trade)-[:WITH]->(cp:Counterparty {{id: 'CP010'}}) RETURN count(t) AS trades
```
Q: Who owns company C0004 and with what percentage?
```cypher
MATCH (p:Person)-[o:OWNS]->(c:Company {{id: 'C0004'}}) RETURN p.id AS person, p.name AS name, o.pct AS pct ORDER BY o.pct DESC
```
Q: Who ultimately owns the company behind counterparty CP005, through any parent companies?
```cypher
MATCH (cp:Counterparty {{id: 'CP005'}})-[:IS_COMPANY]->(c:Company)-[:SUBSIDIARY_OF*0..3]->(top:Company)<-[o:OWNS]-(p:Person)
RETURN top.id AS owning_company, p.id AS person, p.name AS name, o.pct AS pct ORDER BY o.pct DESC
```
(Note the direction: SUBSIDIARY_OF arrows point UP from child to parent, so a parent is reached with ->.)
Q: Total open mark-to-market per commodity?
```cypher
MATCH (t:Trade {{status: 'open'}})-[:OF_INSTRUMENT]->(:Instrument)-[:ON_COMMODITY]->(c:Commodity)
RETURN c.name AS commodity, sum(t.mtm_eur) AS mtm ORDER BY mtm DESC
```
"""


class Text2Cypher:
    def __init__(self, llm, driver):
        self.llm, self.driver = llm, driver
        self.system = SYSTEM.replace("{schema}", schema_text())

    def _run(self, query: str) -> list[dict]:
        with self.driver.session() as s:
            return s.execute_read(lambda tx: [r.data() for r in tx.run(query)])

    def run(self, question: str) -> dict:
        prompt, last_err, cypher = question, None, ""
        empty = None  # a valid query that returned no rows: kept in case the retry does no better
        for attempt in range(2):
            reply = self.llm.chat(self.system, prompt)
            cypher = extract_cypher(reply)
            try:
                safe = validate(cypher)
                rows = self._run(safe)
                result = {"cypher": safe, "rows": rows, "error": None, "attempts": attempt + 1}
                if not rows and attempt == 0:
                    empty = result
                    prompt = (f"{question}\n\nYour query ran but returned no rows:\n{safe}\n"
                              f"Check the relationship DIRECTIONS and property values against the schema (for "
                              f"example SUBSIDIARY_OF points from child to parent). If the true answer is none, "
                              f"repeat the same query. Otherwise write a corrected query.")
                    continue
                return result if rows or not empty else empty
            except UnsafeCypher as e:
                last_err = f"rejected: {e}"
            except Exception as e:  # database error: syntax, unknown label, and so on
                last_err = f"database error: {str(e)[:300]}"
            if empty:
                return empty
            prompt = (f"{question}\n\nYour previous query failed.\nQuery: {cypher}\nProblem: {last_err}\n"
                      f"Write a corrected query.")
        return {"cypher": cypher, "rows": [], "error": last_err, "attempts": 2}


def rows_for_prompt(rows: list[dict], max_rows: int = 40, max_chars: int = 5000) -> str:
    text = json.dumps(rows[:max_rows], default=str)
    return text if len(text) <= max_chars else text[:max_chars] + " ...(truncated)"
