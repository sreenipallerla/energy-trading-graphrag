"""Synthetic data for a fictitious energy trading company ("Voltaire Energy Trading").

Everything is invented. Names are made from word lists; no real company or person is intended.
Run:  python -m etg.gen --out data/out --trades 10000 --seed 42
Writes one CSV per table plus ground_truth.json (answers to questions we plant on purpose).
"""
from __future__ import annotations

import argparse
import csv
import json
import random
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

TODAY = date(2026, 10, 18)
RATINGS = ["AAA", "AA", "A", "BBB+", "BBB", "BBB-", "BB+", "BB", "BB-", "B+", "B", "CCC"]
INVESTMENT_GRADE_MAX_IDX = RATINGS.index("BBB-")  # index <= this is investment grade

FIRST = ["Aiden", "Beatriz", "Callum", "Dara", "Elif", "Farid", "Greta", "Hamza", "Ines", "Jonas", "Katya", "Liam",
         "Mei", "Nikhil", "Orla", "Pavel", "Quinn", "Rosa", "Sven", "Tariq", "Uma", "Viktor", "Wen", "Xavier",
         "Yara", "Zoltan", "Anselm", "Bridget", "Cormac", "Dalia", "Emeka", "Freya", "Gunnar", "Hana", "Ivor"]
LAST = ["Alder", "Brennan", "Castellan", "Dunmore", "Eriksen", "Fairweather", "Galvin", "Haldane", "Ibsen",
        "Jankowski", "Kowalczyk", "Lindqvist", "Marlowe", "Novak", "Okafor", "Petrov", "Quigley", "Rasmussen",
        "Sorensen", "Tremblay", "Ulrich", "Vasquez", "Whitcombe", "Yilmaz", "Zielinski", "Hargreave", "Delacroix"]
CO_A = ["North", "Cinder", "Harbour", "Basalt", "Tidal", "Amber", "Granite", "Solent", "Fjord", "Meridian", "Aurora",
        "Kestrel", "Lumen", "Ironwood", "Cobalt", "Zephyr", "Marlin", "Thistle", "Vantage", "Orchard", "Ridgeway",
        "Silverline", "Quarry", "Beacon", "Falcon", "Redwater", "Highfield", "Copperleaf", "Stormvale", "Delta"]
CO_B = ["Power", "Gas", "Energy", "Utilities", "Resources", "Renewables", "Fuels", "Generation", "Supply", "Trading"]
CO_C = ["Ltd", "GmbH", "SA", "BV", "AS", "plc", "Inc", "SpA", "AB", "Sp. z o.o."]
HOLD_B = ["Holdings", "Capital", "Group", "Partners", "Investments"]

JURISDICTIONS = [  # code, name, risk, sanctioned
    ("IE", "Ireland", "low", False), ("GB", "United Kingdom", "low", False), ("DE", "Germany", "low", False),
    ("NL", "Netherlands", "low", False), ("NO", "Norway", "low", False), ("FR", "France", "low", False),
    ("US", "United States", "low", False), ("CH", "Switzerland", "low", False), ("CY", "Cyprus", "medium", False),
    ("AE", "United Arab Emirates", "medium", False), ("VG", "British Virgin Islands", "high", False),
    ("RU", "Ruritania Federation", "high", True),  # fictitious sanctioned jurisdiction
]
REGULATORS = [("Energy Markets Authority", "GB"), ("Commission for Energy Regulation", "IE"),
              ("Federal Network Agency", "DE"), ("Authority for Consumers and Markets", "NL"),
              ("Financial Conduct Office", "GB"), ("Markets in Derivatives Board", "FR"),
              ("Commodity Futures Panel", "US"), ("Energy Regulatory Council", "NO")]
BANKS = [("Harcourt & Wells", "GB"), ("Banque Lumiere", "FR"), ("Nordhafen Bank", "DE"), ("Clydeford Bank", "IE"),
         ("Alpine Privatbank", "CH"), ("Atlantic Trust", "US"), ("Dutch Merchant Bank", "NL"), ("Fjordbanken", "NO")]
BROKERS = [("Tradewind Brokers", "GB"), ("Spark Spread Partners", "DE"), ("Gridline Brokerage", "NL"),
           ("Meridian Energy Brokers", "IE"), ("Contango Markets", "US"), ("Norrland Brokers", "NO")]
EXCHANGES = [("Continental Power Exchange", "DE"), ("Northern Gas Exchange", "NL"), ("Nordic Spot Market", "NO"),
             ("Atlantic Futures Exchange", "GB"), ("Western Commodity Exchange", "US")]
CLEARING = [("Continental Clearing", "DE"), ("Atlantic Clear", "GB"), ("Western Clearing Corp", "US")]
COMMODITIES = [("Power", "MWh"), ("Natural Gas", "MWh"), ("Brent Crude", "bbl"), ("Coal", "t"),
               ("Carbon Allowance", "t CO2"), ("LNG", "MMBtu")]
HUBS = [("DE Power Hub", "DE", "Power"), ("GB Power Hub", "GB", "Power"), ("FR Power Hub", "FR", "Power"),
        ("NL Gas Hub", "NL", "Natural Gas"), ("GB Gas Hub", "GB", "Natural Gas"), ("US Gas Hub", "US", "Natural Gas"),
        ("Rotterdam Hub", "NL", "Coal"), ("North Sea Hub", "NO", "Brent Crude"),
        ("EU Carbon Registry", "DE", "Carbon Allowance"), ("Atlantic LNG Terminal", "IE", "LNG")]
DESKS = [("Power", "Power"), ("Gas", "Natural Gas"), ("Oil and Coal", "Brent Crude"), ("Emissions and LNG", "Carbon Allowance")]
PRICE = {"Power": 85.0, "Natural Gas": 38.0, "Brent Crude": 82.0, "Coal": 120.0, "Carbon Allowance": 70.0, "LNG": 12.0}
INSTR_TYPES = ["forward", "future", "swap", "option"]
TENORS = ["M+1", "M+2", "Q+1", "Q+2", "Cal+1", "Spot"]
MA_TYPES = ["EFET", "ISDA", "GTMA"]


def write(out: Path, name: str, rows: list[dict]) -> None:
    with open(out / f"{name}.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)


def generate(out: Path, n_trades: int = 10000, seed: int = 42) -> dict:
    rnd = random.Random(seed)
    out.mkdir(parents=True, exist_ok=True)
    used_names: set[str] = set()

    def company_name(suffix_pool=CO_B) -> str:
        for _ in range(1000):
            n = f"{rnd.choice(CO_A)} {rnd.choice(suffix_pool)} {rnd.choice(CO_C)}"
            if n not in used_names:
                used_names.add(n)
                return n
        raise RuntimeError("name pool exhausted")

    # ---- reference data -------------------------------------------------------------------------
    jur = [dict(jurisdiction_id=f"J{i+1:02d}", code=c, name=n, risk_level=r, sanctioned=s)
           for i, (c, n, r, s) in enumerate(JURISDICTIONS)]
    jid = {j["code"]: j["jurisdiction_id"] for j in jur}
    reg = [dict(regulator_id=f"RG{i+1:02d}", name=n, jurisdiction_id=jid[c]) for i, (n, c) in enumerate(REGULATORS)]
    bank = [dict(bank_id=f"BK{i+1:02d}", name=n, jurisdiction_id=jid[c]) for i, (n, c) in enumerate(BANKS)]
    broker = [dict(broker_id=f"BR{i+1:02d}", name=n, jurisdiction_id=jid[c]) for i, (n, c) in enumerate(BROKERS)]
    exch = [dict(exchange_id=f"EX{i+1:02d}", name=n, jurisdiction_id=jid[c]) for i, (n, c) in enumerate(EXCHANGES)]
    clear = [dict(clearing_house_id=f"CH{i+1:02d}", name=n, jurisdiction_id=jid[c]) for i, (n, c) in enumerate(CLEARING)]
    comm = [dict(commodity_id=f"CM{i+1:02d}", name=n, unit=u) for i, (n, u) in enumerate(COMMODITIES)]
    cid = {c["name"]: c["commodity_id"] for c in comm}
    hub = [dict(hub_id=f"HB{i+1:02d}", name=n, jurisdiction_id=jid[c], commodity_id=cid[cm])
           for i, (n, c, cm) in enumerate(HUBS)]
    desk = [dict(desk_id=f"DK{i+1:02d}", name=n, primary_commodity_id=cid[cm]) for i, (n, cm) in enumerate(DESKS)]
    book = []
    for d in desk:
        for k in range(3):
            book.append(dict(book_id=f"BO{len(book)+1:02d}", name=f"{d['name']} Book {k+1}", desk_id=d["desk_id"]))

    instruments = []
    for h in hub:
        cname = next(c["name"] for c in comm if c["commodity_id"] == h["commodity_id"])
        for t in rnd.sample(INSTR_TYPES, 3):
            tenor = rnd.choice(TENORS)
            ex = rnd.choice(exch)["exchange_id"] if t in ("future", "option") else ""
            instruments.append(dict(instrument_id=f"IN{len(instruments)+1:03d}", name=f"{h['name']} {t} {tenor}",
                                    instrument_type=t, tenor=tenor, commodity_id=h["commodity_id"],
                                    hub_id=h["hub_id"], exchange_id=ex, _cname=cname))

    # ---- people ----------------------------------------------------------------------------------
    persons, used_p = [], set()
    nat_codes = [j["code"] for j in jur]

    def new_person(nat=None) -> str:
        for _ in range(1000):
            nm = f"{rnd.choice(FIRST)} {rnd.choice(LAST)}"
            if nm not in used_p:
                used_p.add(nm)
                break
        pid = f"P{len(persons)+1:04d}"
        persons.append(dict(person_id=pid, name=nm, nationality=nat or rnd.choice(nat_codes[:9])))
        return pid

    for _ in range(120):
        new_person()

    # ---- companies and counterparties -------------------------------------------------------------
    companies, owns, directors = [], [], []

    def new_company(kind, name=None, parent="", jur_code=None) -> str:
        coid = f"C{len(companies)+1:04d}"
        companies.append(dict(company_id=coid, name=name or company_name(),
                              jurisdiction_id=jid[jur_code or rnd.choice(nat_codes[:11])],
                              parent_company_id=parent, kind=kind))
        return coid

    group = new_company("internal", "Voltaire Energy Trading Ltd", "", "IE")
    new_company("internal", "Voltaire Energy Trading GmbH", group, "DE")
    new_company("internal", "Voltaire Energy Trading UK Ltd", group, "GB")

    holdings = []
    for _ in range(22):
        h = new_company("external", company_name(HOLD_B), "", rnd.choice(["CY", "AE", "VG", "CH", "NL", "GB"]))
        holdings.append(h)
        owners = rnd.sample([p["person_id"] for p in persons], rnd.randint(1, 3))
        remaining = 100
        for i, p in enumerate(owners):
            pct = remaining if i == len(owners) - 1 else rnd.choice([10, 20, 25, 30, 40])
            pct = min(pct, remaining)
            remaining -= pct
            if pct > 0:
                owns.append(dict(person_id=p, company_id=h, pct=pct))

    cpty_companies = []
    for i in range(60):
        parent = rnd.choice(holdings) if rnd.random() < 0.55 else ""
        cpty_companies.append(new_company("external", parent=parent))
    for co in cpty_companies:
        for p in rnd.sample([p["person_id"] for p in persons], rnd.randint(1, 2)):
            directors.append(dict(person_id=p, company_id=co))

    # Planted fact 1: hidden sanctions exposure. A watchlisted person owns 60% of a holding company;
    # two counterparties sit under that holding. The counterparties' own KYC text never mentions the owner.
    sanc_person = new_person("RU")
    sanc_holding = holdings[0]
    owns[:] = [o for o in owns if o["company_id"] != sanc_holding]
    owns.append(dict(person_id=sanc_person, company_id=sanc_holding, pct=60))
    owns.append(dict(person_id=persons[0]["person_id"], company_id=sanc_holding, pct=40))
    sanc_cos = cpty_companies[:2]
    for co in sanc_cos:
        next(c for c in companies if c["company_id"] == co)["parent_company_id"] = sanc_holding

    watch = [dict(watchlist_id="W001", list_name="OFAC-SDN-sim", reason="Sectoral sanctions (fictitious)",
                  listed_on="2026-03-02", person_id=sanc_person)]
    for k, p in enumerate(rnd.sample([p["person_id"] for p in persons[1:100]], 6), start=2):
        watch.append(dict(watchlist_id=f"W{k:03d}", list_name=rnd.choice(["EU-Consolidated-sim", "UK-OFSI-sim"]),
                          reason="Asset freeze (fictitious)", listed_on=str(date(2025, rnd.randint(1, 12), rnd.randint(1, 28))),
                          person_id=p))

    cpty, ma, ratings, collateral = [], [], [], []
    ctypes = ["utility", "producer", "trader", "industrial", "retailer"]
    for i, co in enumerate(cpty_companies):
        cp = f"CP{i+1:03d}"
        coj = next(c for c in companies if c["company_id"] == co)["jurisdiction_id"]
        cpty.append(dict(counterparty_id=cp, company_id=co, name=next(c["name"] for c in companies if c["company_id"] == co),
                         counterparty_type=rnd.choice(ctypes), onboarded_on=str(TODAY - timedelta(days=rnd.randint(200, 2500)))))
        ma.append(dict(agreement_id=f"MA{i+1:03d}", counterparty_id=cp, agreement_type=rnd.choice(MA_TYPES),
                       signed_on=str(TODAY - timedelta(days=rnd.randint(150, 2400))),
                       governing_law_jurisdiction_id=jid[rnd.choice(["GB", "IE", "DE", "NL"])]))
        start = rnd.randint(2, 8)  # base rating index (A .. BB)
        history = [start]
        if rnd.random() < 0.4:
            history.append(max(0, start + rnd.choice([-1, 1])))
        for k, r in enumerate(history):
            d = TODAY - timedelta(days=rnd.randint(300, 700) - k * 200)
            ratings.append(dict(rating_id=f"R{len(ratings)+1:04d}", counterparty_id=cp,
                                agency=rnd.choice(["S&P-sim", "Moodys-sim", "Fitch-sim"]),
                                rating=RATINGS[r], rated_on=str(d)))

    # Planted fact 2: five counterparties downgraded to sub-investment grade in the last 90 days.
    downgraded = [c["counterparty_id"] for c in cpty[5:10]]
    ratings = [r for r in ratings if r["counterparty_id"] not in downgraded]
    for cp in downgraded:
        ratings.append(dict(rating_id=f"R{len(ratings)+1:04d}", counterparty_id=cp, agency="S&P-sim",
                            rating="BBB-", rated_on=str(TODAY - timedelta(days=300))))
        ratings.append(dict(rating_id=f"R{len(ratings)+1:04d}", counterparty_id=cp, agency="S&P-sim",
                            rating=rnd.choice(["BB+", "BB", "BB-"]), rated_on=str(TODAY - timedelta(days=rnd.randint(8, 80)))))

    for k, r in enumerate(ratings, start=1):  # renumber: filtering above would otherwise leave duplicate ids
        r["rating_id"] = f"R{k:04d}"
        idx = RATINGS.index(r["rating"])
        r["rating_rank"] = idx + 1  # 1 = best (AAA) ... 12 = worst (CCC), so models need not reason about the scale
        r["investment_grade"] = idx <= INVESTMENT_GRADE_MAX_IDX

    # ---- traders and trades ------------------------------------------------------------------------
    traders = []
    for i in range(20):
        traders.append(dict(trader_id=f"T{i+1:02d}", name=f"{rnd.choice(FIRST)} {rnd.choice(LAST)}",
                            desk_id=desk[i % len(desk)]["desk_id"]))
    books_by_desk = defaultdict(list)
    for b in book:
        books_by_desk[b["desk_id"]].append(b["book_id"])
    traders_by_desk = defaultdict(list)
    for t in traders:
        traders_by_desk[t["desk_id"]].append(t["trader_id"])
    desk_of_commodity = {d["primary_commodity_id"]: d["desk_id"] for d in desk}
    instr_by_comm = defaultdict(list)
    for ins in instruments:
        instr_by_comm[ins["commodity_id"]].append(ins)

    # Planted fact 3: concentration. One counterparty gets a much larger share of activity.
    concentrated = cpty[20]["counterparty_id"]
    weights = [3.0 if c["counterparty_id"] == concentrated else rnd.choice([0.4, 0.7, 1.0, 1.0, 1.6]) for c in cpty]
    weights = [w * 4 if c["counterparty_id"] == concentrated else w for w, c in zip(weights, cpty)]  # ~15-20% share
    ma_of = {m["counterparty_id"]: m["agreement_id"] for m in ma}

    trades, settlements = [], []
    for i in range(n_trades):
        cp = rnd.choices(cpty, weights)[0]["counterparty_id"]
        ins = rnd.choice(instruments)
        cm = next(c for c in comm if c["commodity_id"] == ins["commodity_id"])
        d_id = desk_of_commodity.get(cm["commodity_id"], rnd.choice(desk)["desk_id"])
        td = TODAY - timedelta(days=rnd.randint(1, 380))
        ds = td + timedelta(days=rnd.randint(1, 120))
        de = ds + timedelta(days=rnd.choice([30, 90, 365]))
        qty = round(rnd.choice([500, 1000, 2500, 5000, 10000, 25000]) * rnd.uniform(0.5, 1.5), 0)
        price = round(PRICE[cm["name"]] * rnd.uniform(0.8, 1.2), 2)
        notional = round(qty * price, 2)
        status = "delivered" if de < TODAY else "open"
        mtm = round(notional * rnd.gauss(0.02, 0.05), 2) if status == "open" else 0.0
        cleared = ins["exchange_id"] != ""
        trades.append(dict(
            trade_id=f"TR{i+1:06d}", trade_date=str(td), delivery_start=str(ds), delivery_end=str(de),
            side=rnd.choice(["buy", "sell"]), quantity=qty, price=price, notional_eur=notional, mtm_eur=mtm,
            status=status, counterparty_id=cp, agreement_id=ma_of[cp], instrument_id=ins["instrument_id"],
            book_id=rnd.choice(books_by_desk[d_id]), trader_id=rnd.choice(traders_by_desk[d_id]),
            broker_id=rnd.choice(broker)["broker_id"] if rnd.random() < 0.35 else "",
            clearing_house_id=rnd.choice(clear)["clearing_house_id"] if cleared else ""))
        if status == "delivered":
            st = rnd.choices(["settled", "late", "failed"], [0.88, 0.09, 0.03])[0]
            due = de + timedelta(days=5)
            paid = "" if st == "failed" else str(due + timedelta(days=0 if st == "settled" else rnd.randint(3, 20)))
            settlements.append(dict(settlement_id=f"SE{len(settlements)+1:06d}", trade_id=f"TR{i+1:06d}",
                                    amount_eur=notional, due_date=str(due), paid_date=paid, status=st))
    for ins in instruments:
        ins.pop("_cname")

    # ---- exposure, limits, collateral (derived from the trades above, so the answers are exact) -------
    exposure: dict[str, float] = defaultdict(float)
    notional_by: dict[str, float] = defaultdict(float)
    for t in trades:
        exposure[t["counterparty_id"]] += t["mtm_eur"]
        notional_by[t["counterparty_id"]] += t["notional_eur"]
    exposure = {cp: max(v, 0.0) for cp, v in exposure.items()}  # net exposure under the master agreement

    ranked = sorted(exposure, key=exposure.get, reverse=True)
    breach_targets = set(ranked[:8])  # Planted fact 4: eight biggest exposures are over limit
    limits = []
    for c in cpty:
        cp = c["counterparty_id"]
        e = exposure.get(cp, 0.0)
        lim = e * 0.7 if cp in breach_targets else e * rnd.uniform(1.3, 3.0) + 1_000_000
        limits.append(dict(limit_id=f"L{len(limits)+1:03d}", counterparty_id=cp,
                           limit_eur=round(max(lim, 500_000), 2), set_on=str(TODAY - timedelta(days=rnd.randint(30, 400)))))
    limit_of = {l["counterparty_id"]: l["limit_eur"] for l in limits}
    for c in cpty:
        cp = c["counterparty_id"]
        if rnd.random() < 0.6 and exposure.get(cp, 0) > 0:
            collateral.append(dict(collateral_id=f"COL{len(collateral)+1:03d}", counterparty_id=cp,
                                   collateral_type=rnd.choice(["cash", "letter_of_credit", "parent_guarantee"]),
                                   amount_eur=round(exposure[cp] * rnd.uniform(0.1, 0.6), 2),
                                   issuer_bank_id=rnd.choice(bank)["bank_id"]))

    # ---- documents (text for the RAG half) -------------------------------------------------------
    docs, doc_about = [], []

    def add_doc(kind, title, text, cp="", co=""):
        did = f"D{len(docs)+1:04d}"
        docs.append(dict(document_id=did, doc_type=kind, title=title, text=text,
                         created_on=str(TODAY - timedelta(days=rnd.randint(1, 365)))))
        doc_about.append(dict(document_id=did, counterparty_id=cp, company_id=co))

    cur_rating = {}
    for r in sorted(ratings, key=lambda r: r["rated_on"]):
        cur_rating[r["counterparty_id"]] = r["rating"]
    for c in cpty:
        cp = c["counterparty_id"]
        co = next(x for x in companies if x["company_id"] == c["company_id"])
        jname = next(j["name"] for j in jur if j["jurisdiction_id"] == co["jurisdiction_id"])
        add_doc("kyc_report", f"KYC review: {c['name']}",
                f"{c['name']} is a {c['counterparty_type']} incorporated in {jname}. Onboarded on {c['onboarded_on']}. "
                f"Standard due diligence completed. No adverse media found at the time of review. "
                f"Directors were screened against sanctions lists with no direct matches.", cp, co["company_id"])
        add_doc("credit_memo", f"Credit memo: {c['name']}",
                f"Counterparty {c['name']} is rated {cur_rating[cp]}. Approved credit limit is EUR {limit_of[cp]:,.0f}. "
                f"Trading is governed by master agreement {ma_of[cp]}. Credit review is due annually.", cp, co["company_id"])
    for cp in downgraded:
        c = next(x for x in cpty if x["counterparty_id"] == cp)
        add_doc("news", f"Ratings agency lowers {c['name']}",
                f"A ratings agency has lowered {c['name']} to {cur_rating[cp]}, below investment grade, citing weaker "
                f"cash generation and refinancing risk.", cp, c["company_id"])
    sp_name = next(p["name"] for p in persons if p["person_id"] == sanc_person)
    hold_name = next(c["name"] for c in companies if c["company_id"] == sanc_holding)
    add_doc("news", f"Sanctions designation: {sp_name}",
            f"{sp_name} was added to a sanctions list on 2026-03-02. Regulators noted that {sp_name} controls "
            f"{hold_name} through a 60 percent shareholding.", "", sanc_holding)
    for _ in range(30):
        c = rnd.choice(cpty)
        add_doc("compliance_note", f"Compliance note: {c['name']}",
                f"Routine monitoring of {c['name']}. Trade confirmations reconciled. Settlement performance reviewed; "
                f"no escalation required.", c["counterparty_id"], c["company_id"])

    # ---- ground truth ------------------------------------------------------------------------------
    sanc_cpty = [c["counterparty_id"] for c in cpty if c["company_id"] in sanc_cos]
    # Every counterparty with a watchlisted owner (>=25%) within 3 parent hops: the rule the graph query uses.
    watched = {w["person_id"] for w in watch}
    flagged_holdings = {o["company_id"] for o in owns if o["person_id"] in watched and float(o["pct"]) >= 25}
    parent_of = {c["company_id"]: c["parent_company_id"] for c in companies}
    all_sanc_cpty = []
    for c in cpty:
        node, hops = c["company_id"], 0
        while parent_of.get(node) and hops < 3:
            node, hops = parent_of[node], hops + 1
            if node in flagged_holdings:
                all_sanc_cpty.append(c["counterparty_id"])
                break
    total_notional = sum(notional_by.values())
    truth = {
        "as_of": str(TODAY),
        "downgraded_below_ig_last_90d": sorted(downgraded),
        "hidden_sanctions": {"person": sanc_person, "holding_company": sanc_holding, "planted_counterparties": sorted(sanc_cpty),
                             "counterparties": sorted(all_sanc_cpty),
                             "combined_exposure_eur": round(sum(exposure.get(c, 0) for c in all_sanc_cpty), 2)},
        "limit_breaches": sorted(cp for cp in exposure if exposure[cp] > limit_of[cp]),
        "top_concentration": {"counterparty": max(notional_by, key=notional_by.get),
                              "share_of_notional": round(max(notional_by.values()) / total_notional, 4)},
        "trade_count": len(trades),
        "total_notional_eur": round(total_notional, 2),
        "exposure_eur": {k: round(v, 2) for k, v in sorted(exposure.items())},
    }

    # ---- write ---------------------------------------------------------------------------------------
    tables = dict(jurisdiction=jur, regulator=reg, bank=bank, broker=broker, exchange=exch, clearing_house=clear,
                  commodity=comm, hub=hub, desk=desk, book=book, instrument=instruments, person=persons,
                  company=companies, person_owns_company=owns, person_director_of=directors,
                  watchlist_entry=watch, counterparty=cpty, master_agreement=ma, credit_rating=ratings,
                  credit_limit=limits, collateral=collateral, trader=traders, trade=trades,
                  settlement=settlements, document=docs, document_about=doc_about)
    for name, rows in tables.items():
        write(out, name, rows)
    (out / "ground_truth.json").write_text(json.dumps(truth, indent=2))
    return truth


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="data/out")
    ap.add_argument("--trades", type=int, default=10000)
    ap.add_argument("--seed", type=int, default=42)
    a = ap.parse_args()
    t = generate(Path(a.out), a.trades, a.seed)
    print(json.dumps({k: v for k, v in t.items() if k != "exposure_eur"}, indent=2))
