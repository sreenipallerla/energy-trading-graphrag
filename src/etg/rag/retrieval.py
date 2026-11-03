"""Document vectors in Neo4j: embed Document nodes, create the vector index, search it."""
from __future__ import annotations

INDEX = "doc_embedding"


def embed_documents(driver, embedder, batch: int = 32) -> int:
    with driver.session() as s:
        docs = s.run("MATCH (d:Document) RETURN d.id AS id, d.title AS title, d.text AS text ORDER BY id").data()
    if not docs:
        raise RuntimeError("no Document nodes found: run `python -m etg.load_neo4j` first")
    vectors: list[list[float]] = []
    for i in range(0, len(docs), batch):
        part = docs[i:i + batch]
        vectors += embedder.embed([f"{d['title']}. {d['text']}" for d in part])
    dims = len(vectors[0])
    with driver.session() as s:
        s.run("UNWIND $rows AS r MATCH (d:Document {id: r.id}) SET d.embedding = r.v",
              rows=[{"id": d["id"], "v": v} for d, v in zip(docs, vectors)]).consume()
        s.run(f"DROP INDEX {INDEX} IF EXISTS").consume()
        s.run(f"CREATE VECTOR INDEX {INDEX} FOR (d:Document) ON (d.embedding) "
              f"OPTIONS {{indexConfig: {{`vector.dimensions`: {int(dims)}, `vector.similarity_function`: 'cosine'}}}}").consume()
        s.run("CALL db.awaitIndexes(120)").consume()
    return len(docs)


def search_documents(driver, embedder, question: str, k: int = 4) -> list[dict]:
    vec = embedder.embed([question])[0]
    with driver.session() as s:
        return s.execute_read(lambda tx: tx.run(
            f"CALL db.index.vector.queryNodes('{INDEX}', $k, $v) YIELD node, score "
            "OPTIONAL MATCH (node)-[:ABOUT]->(about) "
            "RETURN node.id AS id, node.title AS title, node.text AS text, score, "
            "collect(DISTINCT about.id) AS about ORDER BY score DESC", k=k, v=vec).data())
