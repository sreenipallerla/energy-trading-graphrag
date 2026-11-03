"""GraphRAG: ask the graph (text-to-Cypher) and the documents (vector search), then answer from both."""
from __future__ import annotations

from .retrieval import search_documents
from .text2cypher import Text2Cypher, rows_for_prompt

ANSWER_SYSTEM = """You answer questions for a risk analyst at an energy trading company.
Use ONLY the graph results and documents given. If they do not contain the answer, say so plainly.
Name counterparties by id (for example CP001) and cite documents by id (for example D0012).
Keep the answer short. Never invent numbers; copy them from the graph results."""


class GraphRAG:
    def __init__(self, driver, llm, embedder, k: int = 4):
        self.driver, self.llm, self.embedder, self.k = driver, llm, embedder, k
        self.t2c = Text2Cypher(llm, driver)

    def ask(self, question: str) -> dict:
        graph = self.t2c.run(question)
        try:
            docs = search_documents(self.driver, self.embedder, question, self.k)
        except Exception as e:  # index missing: still answer from the graph
            docs, graph["doc_error"] = [], str(e)[:200]
        doc_text = "\n".join(f"[{d['id']}] {d['title']}: {d['text']}" for d in docs) or "(none)"
        prompt = (f"Question: {question}\n\nGraph query used:\n{graph['cypher']}\n\n"
                  f"Graph results (JSON):\n{rows_for_prompt(graph['rows'])}\n\n"
                  f"Related documents:\n{doc_text}\n\nAnswer:")
        if graph["error"]:
            prompt += f"\n(Note: the graph query failed: {graph['error']})"
        return {"answer": self.llm.chat(ANSWER_SYSTEM, prompt), "cypher": graph["cypher"], "rows": graph["rows"],
                "docs": [d["id"] for d in docs], "error": graph["error"], "model": self.llm.name}
