import json

import pytest

from etg.graph_spec import NODES
from etg.rag import evals, pipeline, providers, retrieval
from etg.rag.guard import UnsafeCypher, extract_cypher, validate
from etg.rag.schema import schema_text
from etg.rag.text2cypher import Text2Cypher


# ---- fakes ---------------------------------------------------------------------------------------
class Rec:
    def __init__(self, d): self.d = d
    def data(self): return self.d


class FakeTx:
    def __init__(self, db): self.db = db
    def run(self, q, **kw):
        self.db.queries.append(q)
        if self.db.fail_first and len(self.db.queries) == 1:
            raise RuntimeError("Unknown label Foo")
        return [Rec(r) for r in self.db.rows]


class FakeSession:
    def __init__(self, db): self.db = db
    def __enter__(self): return self
    def __exit__(self, *a): pass
    def execute_read(self, fn): return fn(FakeTx(self.db))
    def run(self, q, **kw):
        self.db.queries.append(q)
        self.db.params.append(kw)
        return self
    def consume(self): pass
    def data(self): return self.db.rows


class FakeDriver:
    def __init__(self, rows=None, fail_first=False):
        self.rows, self.fail_first, self.queries, self.params = rows or [], fail_first, [], []
    def session(self): return FakeSession(self)


class ScriptedLLM:
    name = "fake:llm"
    def __init__(self, *replies): self.replies, self.calls = list(replies), []
    def chat(self, system, user, temperature=0.0):
        self.calls.append(user)
        return self.replies.pop(0) if len(self.replies) > 1 else self.replies[0]


class FakeEmbedder:
    name = "fake:embed"
    def embed(self, texts): return [[float(len(t)), 1.0, 0.0] for t in texts]


# ---- guard ---------------------------------------------------------------------------------------
def test_guard_allows_read_and_adds_limit():
    assert validate("MATCH (t:Trade) RETURN count(t)").endswith("LIMIT 100")
    assert validate("MATCH (t:Trade) RETURN t LIMIT 5").endswith("LIMIT 5")


@pytest.mark.parametrize("q", [
    "MATCH (n) DETACH DELETE n", "MATCH (n) SET n.x = 1 RETURN n", "CREATE (n:X) RETURN n",
    "CALL db.labels()", "MATCH (n) RETURN n; MATCH (m) RETURN m", "LOAD CSV FROM 'x' AS r RETURN r",
    "MATCH (n) MERGE (m:Y) RETURN m", "", "MATCH (n)"])
def test_guard_blocks_writes_and_junk(q):
    with pytest.raises(UnsafeCypher):
        validate(q)


def test_guard_ignores_keywords_inside_strings():
    assert "set delete" in validate("MATCH (n {name: 'set delete'}) RETURN n")


def test_extract_cypher_fenced_and_bare():
    assert extract_cypher("Sure:\n```cypher\nMATCH (n) RETURN n\n```\nDone") == "MATCH (n) RETURN n"
    assert extract_cypher("MATCH (n) RETURN n") == "MATCH (n) RETURN n"


# ---- schema --------------------------------------------------------------------------------------
def test_schema_lists_every_label_and_hides_document_text():
    s = schema_text()
    for label in NODES:
        assert f"(:{label} " in s
    assert "(:Document {id, doc_type, title, created_on})" in s
    assert "-[:OWNS {pct}]->" in s


# ---- text-to-Cypher ------------------------------------------------------------------------------
def test_text2cypher_happy_path():
    d = FakeDriver(rows=[{"counterparty": "CP001"}])
    out = Text2Cypher(ScriptedLLM("```cypher\nMATCH (c:Counterparty) RETURN c.id AS counterparty\n```"), d).run("q")
    assert out["rows"] == [{"counterparty": "CP001"}] and out["error"] is None and out["attempts"] == 1


def test_text2cypher_repairs_after_unsafe_query():
    llm = ScriptedLLM("MATCH (n) DETACH DELETE n", "MATCH (c:Counterparty) RETURN c.id AS counterparty")
    out = Text2Cypher(llm, FakeDriver(rows=[{"counterparty": "CP002"}])).run("q")
    assert out["attempts"] == 2 and out["error"] is None
    assert "rejected" in llm.calls[1]  # the model was told why


def test_text2cypher_repairs_after_database_error():
    llm = ScriptedLLM("MATCH (f:Foo) RETURN f", "MATCH (c:Counterparty) RETURN c.id AS counterparty")
    out = Text2Cypher(llm, FakeDriver(rows=[{"counterparty": "CP003"}], fail_first=True)).run("q")
    assert out["attempts"] == 2 and "database error" in llm.calls[1]


def test_text2cypher_gives_up_cleanly():
    out = Text2Cypher(ScriptedLLM("DROP everything"), FakeDriver()).run("q")
    assert out["rows"] == [] and out["error"].startswith("rejected")


def test_text2cypher_retries_when_result_is_empty_and_uses_better_query():
    class Db(FakeDriver):
        def session(self):
            outer = self
            class S(FakeSession):
                def execute_read(self, fn):
                    rows = [] if len(outer.queries) == 0 else [{"counterparty": "CP001"}]
                    outer.queries.append("q")
                    return rows
            return S(self)
    llm = ScriptedLLM("MATCH (c:Counterparty)<-[:X]-(d) RETURN c.id AS counterparty",
                      "MATCH (c:Counterparty)-[:X]->(d) RETURN c.id AS counterparty")
    out = Text2Cypher(llm, Db()).run("q")
    assert out["rows"] == [{"counterparty": "CP001"}] and out["attempts"] == 2
    assert "DIRECTIONS" in llm.calls[1]


def test_text2cypher_keeps_empty_result_when_retry_does_not_help():
    llm = ScriptedLLM("MATCH (c:Counterparty) RETURN c.id AS counterparty")
    out = Text2Cypher(llm, FakeDriver(rows=[])).run("q")
    assert out["rows"] == [] and out["error"] is None


def test_text2cypher_keeps_empty_result_when_retry_is_unsafe():
    llm = ScriptedLLM("MATCH (c:Counterparty) RETURN c.id AS counterparty", "DROP everything")
    out = Text2Cypher(llm, FakeDriver(rows=[])).run("q")
    assert out["rows"] == [] and out["error"] is None


# ---- retrieval -----------------------------------------------------------------------------------
def test_embed_documents_builds_index_with_right_dimension():
    d = FakeDriver(rows=[{"id": "D1", "title": "t", "text": "x"}, {"id": "D2", "title": "t", "text": "y"}])
    assert retrieval.embed_documents(d, FakeEmbedder()) == 2
    create = [q for q in d.queries if q.startswith("CREATE VECTOR INDEX")][0]
    assert "`vector.dimensions`: 3" in create and "cosine" in create


def test_embed_documents_errors_when_graph_empty():
    with pytest.raises(RuntimeError):
        retrieval.embed_documents(FakeDriver(rows=[]), FakeEmbedder())


# ---- pipeline ------------------------------------------------------------------------------------
def test_pipeline_combines_graph_and_documents(monkeypatch):
    monkeypatch.setattr(pipeline, "search_documents",
                        lambda *a, **k: [{"id": "D0001", "title": "KYC", "text": "clean", "score": 0.9, "about": ["CP001"]}])
    llm = ScriptedLLM("MATCH (c:Counterparty) RETURN c.id AS counterparty", "CP001 is exposed. See D0001.")
    out = pipeline.GraphRAG(FakeDriver(rows=[{"counterparty": "CP001"}]), llm, FakeEmbedder()).ask("who?")
    assert out["answer"].startswith("CP001") and out["docs"] == ["D0001"]
    assert '"counterparty": "CP001"' in llm.calls[1] and "[D0001]" in llm.calls[1]


def test_pipeline_survives_missing_vector_index(monkeypatch):
    def boom(*a, **k): raise RuntimeError("no such index")
    monkeypatch.setattr(pipeline, "search_documents", boom)
    llm = ScriptedLLM("MATCH (c:Counterparty) RETURN c.id AS counterparty", "answer")
    out = pipeline.GraphRAG(FakeDriver(rows=[]), llm, FakeEmbedder()).ask("q")
    assert out["answer"] == "answer" and out["docs"] == []


# ---- evals ---------------------------------------------------------------------------------------
TRUTH = {"hidden_sanctions": {"counterparties": ["CP001", "CP002"]}, "downgraded_below_ig_last_90d": ["CP006"],
         "limit_breaches": ["CP001", "CP021"], "top_concentration": {"counterparty": "CP021"}}


def test_golden_built_from_truth():
    g = evals.build_golden(TRUTH)
    assert [x["id"] for x in g] == ["sanctions", "downgrades", "limits", "concentration"]
    assert g[0]["expected"] == ["CP001", "CP002"]


def test_score():
    assert evals.score(["CP001", "CP002"], {"CP001"}) == (0.5, 1.0)
    assert evals.score(["CP001"], {"CP001", "CP005"}) == (1.0, 0.5)
    assert evals.score(["CP001"], set()) == (0.0, 0.0)


def test_run_evals_separates_query_quality_from_answer_quality():
    class P:
        def ask(self, q):  # query found both ids, but the written answer dropped one
            return {"answer": "Only CP001.", "rows": [{"c": "CP001"}, {"c": "CP002"}], "cypher": "x",
                    "error": None, "model": "fake"}
    r = evals.run_evals(P(), evals.build_golden(TRUTH)[:1])[0]
    assert r["cypher_recall"] == 1.0 and r["answer_recall"] == 0.5 and r["passed"] is False


# ---- providers -----------------------------------------------------------------------------------
def test_provider_factory(monkeypatch):
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    assert providers.make_llm().name.startswith("ollama:")
    assert providers.make_embedder().name.startswith("ollama:")
    with pytest.raises(ValueError):
        providers.make_llm("nope")


def test_ollama_calls_expected_endpoints(monkeypatch):
    seen = []

    class R:
        def __init__(self, j): self.j = j
        def raise_for_status(self): pass
        def json(self): return self.j

    def fake_post(url, json=None, timeout=None):
        seen.append((url, json))
        return R({"message": {"content": "hi"}} if url.endswith("/api/chat") else {"embeddings": [[0.1, 0.2]]})

    monkeypatch.setattr(providers.httpx, "post", fake_post)
    assert providers.OllamaLLM(host="http://h:1", model="m").chat("s", "u") == "hi"
    assert providers.OllamaEmbedder(host="http://h:1", model="e").embed(["x"]) == [[0.1, 0.2]]
    assert seen[0][0] == "http://h:1/api/chat" and seen[1][0] == "http://h:1/api/embed"
    assert seen[0][1]["stream"] is False and seen[0][1]["options"]["temperature"] == 0.0


def test_run_evals_repeats_and_reports_pass_rate():
    answers = iter(["CP001 and CP002", "CP001 only", "CP001 and CP002"])

    class P:
        def ask(self, q):
            return {"answer": next(answers), "rows": [{"c": "CP001"}, {"c": "CP002"}], "cypher": "x",
                    "error": None, "model": "fake"}
    r = evals.run_evals(P(), evals.build_golden(TRUTH)[:1], runs=3)[0]
    assert r["runs"] == 3 and r["pass_rate"] == 0.67 and r["passed"] is False
    assert len(r["per_run"]) == 3 and r["cypher_recall"] == 1.0


def test_prompt_teaches_rank_and_never_text_comparison():
    from etg.rag.schema import DOMAIN_NOTES
    assert "rating_rank" in DOMAIN_NOTES and "investment_grade" in DOMAIN_NOTES
    assert "never compare rating text" in DOMAIN_NOTES
