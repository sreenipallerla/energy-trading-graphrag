-- PostgreSQL system of record for the fictitious energy trading company.
-- Column names match the CSV headers written by src/etg/gen.py (loader uses the CSV header).
DROP SCHEMA IF EXISTS etg CASCADE;
CREATE SCHEMA etg;
SET search_path = etg;

CREATE TABLE jurisdiction (jurisdiction_id text PRIMARY KEY, code text, name text, risk_level text, sanctioned boolean);
CREATE TABLE regulator (regulator_id text PRIMARY KEY, name text, jurisdiction_id text REFERENCES jurisdiction);
CREATE TABLE bank (bank_id text PRIMARY KEY, name text, jurisdiction_id text REFERENCES jurisdiction);
CREATE TABLE broker (broker_id text PRIMARY KEY, name text, jurisdiction_id text REFERENCES jurisdiction);
CREATE TABLE exchange (exchange_id text PRIMARY KEY, name text, jurisdiction_id text REFERENCES jurisdiction);
CREATE TABLE clearing_house (clearing_house_id text PRIMARY KEY, name text, jurisdiction_id text REFERENCES jurisdiction);
CREATE TABLE commodity (commodity_id text PRIMARY KEY, name text, unit text);
CREATE TABLE hub (hub_id text PRIMARY KEY, name text, jurisdiction_id text REFERENCES jurisdiction, commodity_id text REFERENCES commodity);
CREATE TABLE desk (desk_id text PRIMARY KEY, name text, primary_commodity_id text REFERENCES commodity);
CREATE TABLE book (book_id text PRIMARY KEY, name text, desk_id text REFERENCES desk);
CREATE TABLE instrument (instrument_id text PRIMARY KEY, name text, instrument_type text, tenor text,
  commodity_id text REFERENCES commodity, hub_id text REFERENCES hub, exchange_id text);
CREATE TABLE person (person_id text PRIMARY KEY, name text, nationality text);
CREATE TABLE company (company_id text PRIMARY KEY, name text, jurisdiction_id text REFERENCES jurisdiction,
  parent_company_id text, kind text);
CREATE TABLE person_owns_company (person_id text REFERENCES person, company_id text REFERENCES company, pct numeric);
CREATE TABLE person_director_of (person_id text REFERENCES person, company_id text REFERENCES company);
CREATE TABLE watchlist_entry (watchlist_id text PRIMARY KEY, list_name text, reason text, listed_on date,
  person_id text REFERENCES person);
CREATE TABLE counterparty (counterparty_id text PRIMARY KEY, company_id text REFERENCES company, name text,
  counterparty_type text, onboarded_on date);
CREATE TABLE master_agreement (agreement_id text PRIMARY KEY, counterparty_id text REFERENCES counterparty,
  agreement_type text, signed_on date, governing_law_jurisdiction_id text REFERENCES jurisdiction);
CREATE TABLE credit_rating (rating_id text PRIMARY KEY, counterparty_id text REFERENCES counterparty,
  agency text, rating text, rated_on date, rating_rank int, investment_grade boolean);
CREATE TABLE credit_limit (limit_id text PRIMARY KEY, counterparty_id text REFERENCES counterparty,
  limit_eur numeric, set_on date);
CREATE TABLE collateral (collateral_id text PRIMARY KEY, counterparty_id text REFERENCES counterparty,
  collateral_type text, amount_eur numeric, issuer_bank_id text REFERENCES bank);
CREATE TABLE trader (trader_id text PRIMARY KEY, name text, desk_id text REFERENCES desk);
CREATE TABLE trade (trade_id text PRIMARY KEY, trade_date date, delivery_start date, delivery_end date, side text,
  quantity numeric, price numeric, notional_eur numeric, mtm_eur numeric, status text,
  counterparty_id text REFERENCES counterparty, agreement_id text REFERENCES master_agreement,
  instrument_id text REFERENCES instrument, book_id text REFERENCES book, trader_id text REFERENCES trader,
  broker_id text, clearing_house_id text);
CREATE TABLE settlement (settlement_id text PRIMARY KEY, trade_id text REFERENCES trade, amount_eur numeric,
  due_date date, paid_date date, status text);
CREATE TABLE document (document_id text PRIMARY KEY, doc_type text, title text, text text, created_on date);
CREATE TABLE document_about (document_id text REFERENCES document, counterparty_id text, company_id text);

CREATE INDEX ON trade (counterparty_id);
CREATE INDEX ON trade (status);
CREATE INDEX ON settlement (trade_id);

-- Net positive exposure per counterparty (open trades, netted under the master agreement).
CREATE VIEW v_exposure AS
SELECT t.counterparty_id, c.name, GREATEST(SUM(t.mtm_eur), 0) AS exposure_eur, l.limit_eur
FROM trade t JOIN counterparty c USING (counterparty_id)
JOIN credit_limit l USING (counterparty_id)
WHERE t.status = 'open'
GROUP BY t.counterparty_id, c.name, l.limit_eur;
