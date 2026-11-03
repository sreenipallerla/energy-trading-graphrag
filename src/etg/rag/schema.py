"""Builds the graph description that goes into the text-to-Cypher prompt, straight from graph_spec.py."""
from __future__ import annotations

from ..graph_spec import NODES, RELS

AS_OF = "2026-10-18"

DOMAIN_NOTES = f"""Domain rules (use these definitions exactly):
- Every node has a string property `id`. Counterparty ids look like CP001, Company ids like C0004, Person ids like P0121.
- Today is {AS_OF}. "Last 90 days" means a date on or after 2026-07-20. Dates are ISO strings, so compare with strings.
- Open trades have Trade.status = 'open'. Trade.mtm_eur is the mark-to-market in EUR (can be negative).
- Exposure of a counterparty = max(sum(Trade.mtm_eur) over its OPEN trades, 0).
- A counterparty breaches its limit when exposure > CreditLimit.limit_eur (via HAS_LIMIT).
- Current rating of a counterparty = the CreditRating with the latest rated_on.
- CreditRating.rating_rank runs from 1 (best, AAA) to 12 (worst, CCC); a HIGHER rank is a WORSE rating.
  CreditRating.investment_grade is true for BBB- or better and false below that ("below investment grade").
  Always use rating_rank and investment_grade, never compare rating text.
- A downgrade is when a counterparty's latest rating has a higher rating_rank than its previous rating.
- Share of notional = sum(Trade.notional_eur) for a counterparty divided by the sum over all trades.
- A company's owners come from (:Person)-[:OWNS {{pct}}]->(:Company). Parents come from (:Company)-[:SUBSIDIARY_OF]->(:Company)
  (child to parent). A counterparty's company is reached with (:Counterparty)-[:IS_COMPANY]->(:Company).
- A person is sanctioned when a WatchlistEntry has (:WatchlistEntry)-[:MATCHES]->(:Person).
"""


def schema_text() -> str:
    lines = ["Node labels and properties:"]
    for label, (_, _, props) in NODES.items():
        shown = [p for p in props if p != "text"]  # long document text stays out of the prompt
        lines.append(f"  (:{label} {{id, {', '.join(shown)}}})")
    lines.append("Relationships:")
    seen = set()
    for rel, _, fl, _, tl, _, eprops in RELS:
        pat = f"  (:{fl})-[:{rel}{' {' + ', '.join(eprops) + '}' if eprops else ''}]->(:{tl})"
        if pat not in seen:
            seen.add(pat)
            lines.append(pat)
    return "\n".join(lines)
