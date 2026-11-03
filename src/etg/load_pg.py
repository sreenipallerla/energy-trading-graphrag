"""Load the generated CSVs into PostgreSQL (schema etg). Usage: python -m etg.load_pg"""
from __future__ import annotations

import csv
import os
from pathlib import Path

import psycopg

ROOT = Path(__file__).resolve().parents[2]
# Parents before children so foreign keys hold.
ORDER = ["jurisdiction", "regulator", "bank", "broker", "exchange", "clearing_house", "commodity", "hub", "desk",
         "book", "instrument", "person", "company", "person_owns_company", "person_director_of", "watchlist_entry",
         "counterparty", "master_agreement", "credit_rating", "credit_limit", "collateral", "trader", "trade",
         "settlement", "document", "document_about"]


def dsn() -> str:
    return os.getenv("PG_DSN", "postgresql://etg:etg@localhost:5433/etg")


def main(data_dir: Path = ROOT / "data" / "out") -> None:
    with psycopg.connect(dsn()) as conn:
        conn.execute((ROOT / "sql" / "schema.sql").read_text())
        for t in ORDER:
            path = data_dir / f"{t}.csv"
            with open(path, newline="", encoding="utf-8") as f:
                cols = next(csv.reader(f))
            collist = ", ".join(cols)
            with conn.cursor() as cur, open(path, encoding="utf-8") as f:
                with cur.copy(f"COPY etg.{t} ({collist}) FROM STDIN WITH (FORMAT csv, HEADER true, NULL '')") as cp:
                    while chunk := f.read(65536):
                        cp.write(chunk)
            n = conn.execute(f"SELECT count(*) FROM etg.{t}").fetchone()[0]
            print(f"{t:22s} {n:>7d} rows")
        conn.commit()


if __name__ == "__main__":
    main()
