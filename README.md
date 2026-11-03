# Energy Trading GraphRAG (Phase 1: the data, Phase 2: GraphRAG)

A fictitious energy trading company ("Voltaire Energy Trading") with about 10,000 trades, 23 node types and some
facts planted on purpose. Phase 1 builds the data in PostgreSQL (system of record) and Neo4j (graph), and proves
the two agree. Phase 2 is GraphRAG: questions in plain English answered from the graph plus documents.

Everything is invented. Names come from word lists; no real company or person is intended.

## What gets built
```
generator (gen.py) --CSV--> PostgreSQL (tables, view v_exposure)
                      \--CSV--> Neo4j (23 labels, 30 relationship types)
                    ground_truth.json  <-- the answers we check both databases against
```
Node types: Jurisdiction, Regulator, Company, Counterparty, Bank, Broker, Exchange, ClearingHouse, Person,
WatchlistEntry, Desk, Book, Trader, Commodity, Instrument, Hub, MasterAgreement, CreditRating, CreditLimit,
Collateral, Trade, Settlement, Document.

## Planted facts (so we can test answers later)
1. **Hidden sanctions exposure**: a watchlisted person owns 60% of a holding company; counterparties sit under it.
   The counterparties' own KYC text never names the owner, so only the graph can find it.
2. **Downgrades**: five counterparties dropped below investment grade in the last 90 days, all with open exposure.
3. **Limit breaches**: counterparties whose net exposure is above their credit limit.
4. **Concentration**: one counterparty has about 18% of all notional.
The exact answers are in `data/out/ground_truth.json` after you generate.

## Step 1. Set up Python
```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export PYTHONPATH=src
```

## Step 2. Generate the data and run the tests
```bash
python -m etg.gen --out data/out --trades 10000 --seed 42
python -m pytest -q tests
```
Check: 12 tests pass and `data/out` holds 26 CSV files plus `ground_truth.json`. Same seed gives the same data.

## Step 3. Start the databases (needs Docker Desktop)
```bash
docker compose up -d
```
PostgreSQL is published on port **5433** (not 5432) so it cannot clash with a Postgres already on your machine.
Wait about 30 seconds. Neo4j browser: http://localhost:7474 (user `neo4j`, password `etgpassword`).

## Step 4. Load PostgreSQL
```bash
python -m etg.load_pg
```
Check: the last lines show `trade 10000 rows` and `document 156 rows`.

## Step 5. Load Neo4j
```bash
python -m etg.load_neo4j
```
Check: it prints a count per node label and per relationship type, with no errors.

## Step 6. Verify both against the truth
```bash
python scripts/verify.py
```
Check: all lines say PASS. The Neo4j check answers "which counterparties sit under a holding company owned 25% or
more by a watchlisted person" by walking the graph, and compares it with the generator's answer.

## Try these in Neo4j browser
```cypher
// who is behind a counterparty? (ownership chain)
MATCH path = (p:Person)-[:OWNS]->(h:Company)<-[:SUBSIDIARY_OF*1..3]-(c:Company)<-[:IS_COMPANY]-(cp:Counterparty {id:'CP001'})
RETURN path;
// one schema picture
CALL db.schema.visualization();
```

## Status and honest limits
- Phase 1 verified on a real machine: both databases load and match the generator's answers.
- Phase 2 verified live on Azure OpenAI (chat model gpt-4.1-mini, embeddings text-embedding-3-small): `verify.py`
  passes 7 of 7 (including the three reference queries), 156 documents embedded into the Neo4j vector index, and
  `python -m etg.rag eval --runs 3` passed 12 of 12 question-runs.
- Offline tests (fake model, fake database) cover the guard, repair loop, pipeline plumbing, vector index creation
  and scoring. **The Ollama path has not been run**; it is written but untested.
- Eval history: baseline 3 of 4 (sanctions failed: the model walked SUBSIDIARY_OF in the wrong direction), then
  3 of 4 again (downgrades failed: a LIMIT 1 bug and string comparison of ratings), then 12 of 12 after adding
  `rating_rank` / `investment_grade` to the data, a direction example to the prompt, and an empty-result retry.
- **Caveat:** the prompt and data were tuned against these same four questions, so 12 of 12 shows the pipeline
  works, not that it generalises. Spot checks with unseen questions (for example "Why was CP007 downgraded?" and
  "Who owns the holding company above CP001?") returned correct answers, but that is three questions, not a test set.
- The evals score the graph half (which counterparty IDs come back). They do not measure document retrieval quality.
- Exposure here is simplified: net sum of mark-to-market on open trades per counterparty, floored at zero.

## Phase 2: GraphRAG with Neo4j and a model (Ollama locally, or Azure OpenAI)

```
question --> model writes Cypher --> guard (read-only) --> Neo4j --> rows ----+
   |                                                                          +--> model writes the answer
   +--> embed question --> vector search over Document nodes --> documents ---+
```
The graph answers questions that need joins and sums (ownership chains, exposure). The documents add context
(KYC notes, rating news). Which model runs is chosen by `LLM_PROVIDER` (`ollama` default, `azure` later).

### Step 7. Pick a model provider
Either Azure OpenAI (see "Azure provider" below; no load on your machine) or Ollama (local, free, heavier on a
laptop). For Ollama, install it from ollama.com, then:
```bash
ollama pull qwen2.5:7b
ollama pull nomic-embed-text
```
Check: `ollama list` shows both. (About 5 GB. On a Mac with less than 16 GB RAM, try `OLLAMA_CHAT_MODEL=qwen2.5:3b`.)

### Step 8. Make sure the graph passes its checks
```bash
python scripts/verify.py
```
Check: every line PASS, including the three `reference query` lines. Those prove the definitions the model is taught
(exposure, current rating, concentration) reproduce the known answers. If one fails, stop and send me the output.

### Step 9. Embed the documents
```bash
python -m etg.rag embed
```
Check: `embedded 156 documents with <provider>:<model> and built the vector index` (for example `azure:embed`).

### Step 10. Ask questions
```bash
python -m etg.rag ask "Which counterparties have a current credit rating below investment grade?"
python -m etg.rag ask "What do we know about the owners of CP001's parent company?"
```
Each answer shows the Cypher the model wrote, the answer, and the documents it retrieved. Read the Cypher: that is
where small models go wrong.

### Step 11. Run the evals
```bash
python -m etg.rag eval --runs 3
```
`--runs 3` asks every question three times and reports how many runs passed, because a single run of a language model can be lucky or unlucky.
Four questions built from `ground_truth.json`. Each prints how many runs passed, and:
- `cypher_recall`: did the model's query return the right counterparties? (query quality)
- `answer_recall` / `answer_precision`: did the final written answer name exactly the right ones? (answer quality)

Results are saved to `evals/results-<model>.json`; copy the file to a new name (for example
`cp evals/results-azure_chat.json evals/after-rank-azure_chat.json`) before the next run so you can compare. Small
local models may fail multi-step questions such as "exposure above limit"; comparing a local model with an Azure
model on the same questions is the point of the two providers.

### Data tip learned from the evals
Ratings carry `rating_rank` (1 best to 12 worst) and `investment_grade` (true/false) in both databases. Without
them the model had to reason about the rating scale itself and sometimes wrote a wrong or fragile query (string
comparison of rating text). Putting the logic in the data is cheaper and more reliable than a longer prompt.

## Safety
The model only proposes Cypher. `rag/guard.py` rejects anything that writes (CREATE, MERGE, DELETE, SET, CALL, ...),
allows one statement only, adds a LIMIT, and the query runs in a read-only transaction. Failed queries get one repair
attempt with the error message shown to the model.

## Azure provider (used for the results above)
`LLM_PROVIDER=azure` and `EMBED_PROVIDER=azure` switch the chat and embedding calls to Azure OpenAI deployments.
Needs `pip install openai azure-identity`, and in `.env` (loaded automatically; never commit it or paste keys into
chat or screenshots): `AZURE_OPENAI_ENDPOINT`, `AZURE_CHAT_DEPLOYMENT` (a chat model such as gpt-4.1-mini),
`AZURE_EMBED_DEPLOYMENT` (text-embedding-3-small), and `AZURE_OPENAI_API_KEY` (or sign in with `az login`).
Re-run `python -m etg.rag embed` after switching embedding models, because vector sizes differ.

Cost control: create the resources for one session, run the evals, then delete the resource group. A deleted
Azure OpenAI account is only soft-deleted, so purge it too:
`az group delete -n <group> --yes --no-wait`, then `az cognitiveservices account list-deleted -o table` and
`az cognitiveservices account purge -n <account> -g <group> -l <location>`.

## Clean up
`docker compose down -v`
