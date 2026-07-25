from pathlib import Path

from packages.knowledge_engine import (
    EntityFlowTracer,
    IntelligenceReportParser,
    SQLiteKnowledgeStore,
)


FIXTURES = Path(__file__).parent / "fixtures" / "intelligence"


def test_intelligence_reports_are_chunked_and_persisted_as_typed_source_nodes(
    tmp_path: Path,
):
    graph = IntelligenceReportParser().parse_path(FIXTURES / "bag-processing.md")
    store = SQLiteKnowledgeStore(tmp_path / "knowledge.db")
    graph.persist(store)

    artifacts = [node for node in graph.nodes if node.type == "artifact.source"]
    assert len(artifacts) == 4
    assert all(node.metadata["path"].endswith((".java", ".yml")) for node in artifacts)
    assert not any(node.type == "document.markdown" for node in graph.nodes)
    assert store.find_nodes(node_type="symbol.method", name_contains="publish")


def test_bag_entity_flow_crosses_broker_and_reaches_arrival_view_table():
    parser = IntelligenceReportParser()
    graph = parser.parse_path(FIXTURES / "bag-processing.md")
    graph = graph.merged(
        parser.parse_path(FIXTURES / "sync-service.md"),
        parser.parse_path(FIXTURES / "arrival-view.md"),
    )

    flow = EntityFlowTracer(graph).trace(
        "bag",
        "sample-bag-processing-service",
        "sample-arrival-view-service",
    )

    names = [node.name for node in flow.nodes]
    edge_types = [edge.type for edge in flow.edges]
    assert "CommonUpdatesService.performCommonUpdates" in names
    assert "AfsEventProducerServiceImpl.publishBagProcessedEvent" in names
    assert "OPS.ARRIVAL.BAG.PROCESSED" in names
    assert "VIEW.ARRIVAL.BAG.QMAIN" in names
    assert "BagEventConsumer.handle" in names
    assert "BagEventFacadeImpl.process" in names
    assert "AfsArrivalBagDaoAdapter.save" in names
    assert names[-1] == "VIEW_OWNER.ARRIVAL_BAGS"
    assert "routes_to" in edge_types
    assert "writes" in edge_types

    broker_edge = next(edge for edge in flow.edges if edge.type == "routes_to")
    assert broker_edge.metadata["inferred"] is True
    assert broker_edge.metadata["confidence"] == 0.55
    assert "binding is absent" in broker_edge.metadata["evidence"]


def test_flow_context_contains_only_path_evidence_and_respects_budget():
    parser = IntelligenceReportParser()
    graph = parser.parse_path(FIXTURES / "bag-processing.md").merged(
        parser.parse_path(FIXTURES / "sync-service.md"),
        parser.parse_path(FIXTURES / "arrival-view.md"),
    )
    flow = EntityFlowTracer(graph).trace(
        "bag",
        "sample-bag-processing-service",
        "sample-arrival-view-service",
    )

    pack = flow.as_context_pack(max_tokens=900)
    assert pack.token_estimate <= 900
    assert all(item.metadata["flow_entity"] == "bag" for item in pack.items)
    assert not any("ScanSyncService" in item.content for item in pack.items)
    assert any(item.metadata["path"].endswith("BagEventConsumer.java") for item in pack.items)
