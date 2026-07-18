from pathlib import Path

from packages.context_engine import ContextItem, ContextPackBuilder
from packages.knowledge_engine import DocumentIngestor, KnowledgeEdge, SQLiteKnowledgeStore


def test_context_pack_ranks_deduplicates_and_applies_budget():
    builder = ContextPackBuilder(max_tokens=20)
    pack = builder.build(
        "implement feature",
        [
            ContextItem("1", "repo/a", "A", "same content", 0.9),
            ContextItem("2", "repo/b", "B", "same   content", 0.8),
            ContextItem("3", "repo/c", "C", "different", 0.7),
        ],
    )
    assert [item.id for item in pack.items] == ["1", "3"]
    assert pack.metadata["candidate_count"] == 3


def test_markdown_ingestion_and_graph_queries(tmp_path: Path):
    document = tmp_path / "README.md"
    document.write_text("# Service\n\nHandles account operations.", encoding="utf-8")
    node = DocumentIngestor().ingest_path(document, "sample-repo")[0]

    store = SQLiteKnowledgeStore(tmp_path / "knowledge.db")
    store.upsert_node(node)
    assert store.find_nodes(node_type="document.markdown")[0]["name"] == "README.md"
    assert store.search("account")[0]["id"] == node.id


def test_graph_edges_are_queryable(tmp_path: Path):
    document = tmp_path / "README.md"
    document.write_text("# API", encoding="utf-8")
    first = DocumentIngestor().ingest_path(document, "repo")[0]
    second = type(first)(
        id="service:api",
        type="service",
        name="API",
        source="repo",
    )
    store = SQLiteKnowledgeStore(tmp_path / "knowledge.db")
    store.upsert_node(first)
    store.upsert_node(second)
    store.upsert_edge(KnowledgeEdge(second.id, first.id, "documented_by"))
    assert store.neighbors(second.id, "out")[0]["target_id"] == first.id
