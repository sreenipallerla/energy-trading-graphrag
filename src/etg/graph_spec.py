"""The graph model in one place: 23 node labels and the relationships between them.

NODES:  label -> (csv file, id column, extra properties copied from the CSV)
RELS:   (relationship type, csv file, from label, from column, to label, to column, edge properties)
Rows with an empty from/to value are skipped (for example a trade with no broker).
"""
NODES = {
    "Jurisdiction": ("jurisdiction", "jurisdiction_id", ["code", "name", "risk_level", "sanctioned"]),
    "Regulator": ("regulator", "regulator_id", ["name"]),
    "Company": ("company", "company_id", ["name", "kind"]),
    "Counterparty": ("counterparty", "counterparty_id", ["name", "counterparty_type", "onboarded_on"]),
    "Bank": ("bank", "bank_id", ["name"]),
    "Broker": ("broker", "broker_id", ["name"]),
    "Exchange": ("exchange", "exchange_id", ["name"]),
    "ClearingHouse": ("clearing_house", "clearing_house_id", ["name"]),
    "Person": ("person", "person_id", ["name", "nationality"]),
    "WatchlistEntry": ("watchlist_entry", "watchlist_id", ["list_name", "reason", "listed_on"]),
    "Desk": ("desk", "desk_id", ["name"]),
    "Book": ("book", "book_id", ["name"]),
    "Trader": ("trader", "trader_id", ["name"]),
    "Commodity": ("commodity", "commodity_id", ["name", "unit"]),
    "Instrument": ("instrument", "instrument_id", ["name", "instrument_type", "tenor"]),
    "Hub": ("hub", "hub_id", ["name"]),
    "MasterAgreement": ("master_agreement", "agreement_id", ["agreement_type", "signed_on"]),
    "CreditRating": ("credit_rating", "rating_id", ["agency", "rating", "rated_on", "rating_rank", "investment_grade"]),
    "CreditLimit": ("credit_limit", "limit_id", ["limit_eur", "set_on"]),
    "Collateral": ("collateral", "collateral_id", ["collateral_type", "amount_eur"]),
    "Trade": ("trade", "trade_id", ["trade_date", "delivery_start", "delivery_end", "side", "quantity", "price",
                                    "notional_eur", "mtm_eur", "status"]),
    "Settlement": ("settlement", "settlement_id", ["amount_eur", "due_date", "paid_date", "status"]),
    "Document": ("document", "document_id", ["doc_type", "title", "text", "created_on"]),
}

RELS = [
    ("REGULATES", "regulator", "Regulator", "regulator_id", "Jurisdiction", "jurisdiction_id", []),
    ("INCORPORATED_IN", "company", "Company", "company_id", "Jurisdiction", "jurisdiction_id", []),
    ("SUBSIDIARY_OF", "company", "Company", "company_id", "Company", "parent_company_id", []),
    ("IS_COMPANY", "counterparty", "Counterparty", "counterparty_id", "Company", "company_id", []),
    ("BASED_IN", "bank", "Bank", "bank_id", "Jurisdiction", "jurisdiction_id", []),
    ("BASED_IN", "broker", "Broker", "broker_id", "Jurisdiction", "jurisdiction_id", []),
    ("BASED_IN", "exchange", "Exchange", "exchange_id", "Jurisdiction", "jurisdiction_id", []),
    ("BASED_IN", "clearing_house", "ClearingHouse", "clearing_house_id", "Jurisdiction", "jurisdiction_id", []),
    ("OWNS", "person_owns_company", "Person", "person_id", "Company", "company_id", ["pct"]),
    ("DIRECTOR_OF", "person_director_of", "Person", "person_id", "Company", "company_id", []),
    ("MATCHES", "watchlist_entry", "WatchlistEntry", "watchlist_id", "Person", "person_id", []),
    ("HAS_BOOK", "book", "Desk", "desk_id", "Book", "book_id", []),
    ("MEMBER_OF", "trader", "Trader", "trader_id", "Desk", "desk_id", []),
    ("ON_COMMODITY", "instrument", "Instrument", "instrument_id", "Commodity", "commodity_id", []),
    ("DELIVERS_AT", "instrument", "Instrument", "instrument_id", "Hub", "hub_id", []),
    ("LISTED_ON", "instrument", "Instrument", "instrument_id", "Exchange", "exchange_id", []),
    ("IN_JURISDICTION", "hub", "Hub", "hub_id", "Jurisdiction", "jurisdiction_id", []),
    ("PRIMARY_COMMODITY", "desk", "Desk", "desk_id", "Commodity", "primary_commodity_id", []),
    ("HAS_AGREEMENT", "master_agreement", "Counterparty", "counterparty_id", "MasterAgreement", "agreement_id", []),
    ("GOVERNED_BY", "master_agreement", "MasterAgreement", "agreement_id", "Jurisdiction",
     "governing_law_jurisdiction_id", []),
    ("HAS_RATING", "credit_rating", "Counterparty", "counterparty_id", "CreditRating", "rating_id", []),
    ("HAS_LIMIT", "credit_limit", "Counterparty", "counterparty_id", "CreditLimit", "limit_id", []),
    ("POSTED", "collateral", "Counterparty", "counterparty_id", "Collateral", "collateral_id", []),
    ("ISSUED_BY", "collateral", "Collateral", "collateral_id", "Bank", "issuer_bank_id", []),
    ("WITH", "trade", "Trade", "trade_id", "Counterparty", "counterparty_id", []),
    ("UNDER", "trade", "Trade", "trade_id", "MasterAgreement", "agreement_id", []),
    ("OF_INSTRUMENT", "trade", "Trade", "trade_id", "Instrument", "instrument_id", []),
    ("IN_BOOK", "trade", "Trade", "trade_id", "Book", "book_id", []),
    ("BOOKED_BY", "trade", "Trade", "trade_id", "Trader", "trader_id", []),
    ("BROKERED_BY", "trade", "Trade", "trade_id", "Broker", "broker_id", []),
    ("CLEARED_BY", "trade", "Trade", "trade_id", "ClearingHouse", "clearing_house_id", []),
    ("SETTLES", "settlement", "Settlement", "settlement_id", "Trade", "trade_id", []),
    ("ABOUT", "document_about", "Document", "document_id", "Counterparty", "counterparty_id", []),
    ("ABOUT", "document_about", "Document", "document_id", "Company", "company_id", []),
]

NUMERIC = {"rating_rank", "quantity", "price", "notional_eur", "mtm_eur", "amount_eur", "limit_eur", "pct"}
BOOLEAN = {"sanctioned", "investment_grade"}
