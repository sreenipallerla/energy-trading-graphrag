import csv
import json
import re
from pathlib import Path

import pytest

from etg.gen import generate, RATINGS, INVESTMENT_GRADE_MAX_IDX
from etg.graph_spec import NODES, RELS

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def data(tmp_path_factory):
    out = tmp_path_factory.mktemp("out")
    truth = generate(out, n_trades=3000, seed=7)

    def rows(name):
        with open(out / f"{name}.csv", newline="", encoding="utf-8") as f:
            return list(csv.DictReader(f))

    return out, truth, rows


def test_deterministic(tmp_path):
    a = generate(tmp_path / "a", 500, 1)
    b = generate(tmp_path / "b", 500, 1)
    assert a == b


def test_trade_count_and_ids_unique(data):
    _, truth, rows = data
    t = rows("trade")
    assert len(t) == truth["trade_count"] == 3000
    assert len({r["trade_id"] for r in t}) == 3000


def test_primary_keys_unique_in_every_table(data):
    _, _, rows = data
    for label, (csvname, idcol, _) in NODES.items():
        ids = [r[idcol] for r in rows(csvname)]
        assert len(ids) == len(set(ids)), f"{csvname}.{idcol} has duplicates"


def test_node_types_at_least_20(data):
    assert len(NODES) >= 20


def test_spec_columns_exist_in_csvs(data):
    out, _, rows = data
    for label, (csvname, idcol, props) in NODES.items():
        header = set(rows(csvname)[0].keys())
        assert idcol in header and set(props) <= header, label
    for rel, csvname, fl, fc, tl, tc, eprops in RELS:
        header = set(rows(csvname)[0].keys())
        assert {fc, tc, *eprops} <= header, rel
        assert fl in NODES and tl in NODES, rel


def test_schema_columns_match_csv_headers(data):
    out, _, rows = data
    sql = (ROOT / "sql" / "schema.sql").read_text()
    for m in re.finditer(r"CREATE TABLE (\w+) \((.*?)\);", sql, re.S):
        table, body = m.group(1), m.group(2)
        cols = []
        for part in re.split(r",\s*(?![^()]*\))", body):
            w = part.strip().split()[0]
            if w.upper() not in ("PRIMARY", "FOREIGN", "UNIQUE"):
                cols.append(w)
        assert cols == list(rows(table)[0].keys()), table


def test_foreign_keys_resolve(data):
    _, _, rows = data
    cpty = {r["counterparty_id"] for r in rows("counterparty")}
    assert {r["counterparty_id"] for r in rows("trade")} <= cpty
    trade_ids = {r["trade_id"] for r in rows("trade")}
    assert {r["trade_id"] for r in rows("settlement")} <= trade_ids
    companies = {r["company_id"] for r in rows("company")}
    assert {r["parent_company_id"] for r in rows("company") if r["parent_company_id"]} <= companies
    assert {r["company_id"] for r in rows("person_owns_company")} <= companies


def test_ownership_never_exceeds_100(data):
    _, _, rows = data
    tot = {}
    for r in rows("person_owns_company"):
        tot[r["company_id"]] = tot.get(r["company_id"], 0) + float(r["pct"])
    assert max(tot.values()) <= 100.0001


def test_planted_downgrades_are_real(data):
    _, truth, rows = data
    latest = {}
    for r in sorted(rows("credit_rating"), key=lambda r: r["rated_on"]):
        latest[r["counterparty_id"]] = r["rating"]
    for cp in truth["downgraded_below_ig_last_90d"]:
        assert RATINGS.index(latest[cp]) > INVESTMENT_GRADE_MAX_IDX


def test_hidden_sanctions_chain(data):
    _, truth, rows = data
    h = truth["hidden_sanctions"]
    owns = [r for r in rows("person_owns_company") if r["person_id"] == h["person"] and r["company_id"] == h["holding_company"]]
    assert owns and float(owns[0]["pct"]) == 60
    assert any(w["person_id"] == h["person"] for w in rows("watchlist_entry"))
    comp = {r["company_id"]: r for r in rows("company")}
    assert set(h["planted_counterparties"]) <= set(h["counterparties"])
    for cp in h["planted_counterparties"]:
        co = next(r["company_id"] for r in rows("counterparty") if r["counterparty_id"] == cp)
        assert comp[co]["parent_company_id"] == h["holding_company"]
    # the counterparty's own KYC text must not reveal the owner (it is a graph-only fact)
    pname = next(r["name"] for r in rows("person") if r["person_id"] == h["person"])
    for d in rows("document"):
        if d["doc_type"] == "kyc_report":
            assert pname not in d["text"]


def test_limit_breaches_match_data(data):
    _, truth, rows = data
    expo = {}
    for t in rows("trade"):
        if t["status"] == "open":
            expo[t["counterparty_id"]] = expo.get(t["counterparty_id"], 0) + float(t["mtm_eur"])
    lim = {r["counterparty_id"]: float(r["limit_eur"]) for r in rows("credit_limit")}
    breaches = sorted(cp for cp, v in expo.items() if max(v, 0) > lim[cp])
    assert breaches == truth["limit_breaches"]
    assert len(breaches) >= 5


def test_concentration(data):
    _, truth, _ = data
    assert truth["top_concentration"]["share_of_notional"] > 0.10


def test_rating_rank_and_investment_grade_are_consistent(data):
    _, _, rows = data
    for r in rows("credit_rating"):
        idx = RATINGS.index(r["rating"])
        assert int(r["rating_rank"]) == idx + 1
        assert (r["investment_grade"] == "True") == (idx <= INVESTMENT_GRADE_MAX_IDX)
