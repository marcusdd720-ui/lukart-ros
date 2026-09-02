from knowledge.graph import KnowledgeGraph
from knowledge.node import KnowledgeNode
from knowledge.types import NodeType
from validation.extraction_quality import ExtractionMetrics
from validation.measurement import MeasurementCollector


def _metrics() -> ExtractionMetrics:
    return ExtractionMetrics(
        true_positive=8,
        false_positive=2,
        false_negative=1,
        precision=0.8,
        recall=8 / 9,
        f1=0.8421052631578947,
        critical_true_positive=4,
        critical_false_positive=0,
        critical_false_negative=0,
        critical_recall=1.0,
        critical_precision=1.0,
        critical_fact_loss=0,
        case_number_false_positive_rate=0.0,
        provenance_completeness=1.0,
    )


def test_extraction_measurement_preserves_all_numeric_metrics() -> None:
    snapshot = MeasurementCollector().from_extraction(_metrics())

    assert snapshot.metrics["true_positive"] == 8
    assert snapshot.metrics["false_negative"] == 1
    assert snapshot.metrics["precision"] == 0.8
    assert snapshot.metrics["critical_recall"] == 1.0
    assert snapshot.as_dict()["metrics"] == dict(sorted(snapshot.metrics.items()))


def test_graph_measurement_comes_from_graph_statistics() -> None:
    graph = KnowledgeGraph()
    graph.add_node(KnowledgeNode(id="a", type=NodeType.FACT, name="A"))

    snapshot = MeasurementCollector().from_graph(graph)

    assert snapshot.as_dict() == {
        "metrics": {
            "connected_nodes": 0,
            "edges": 0,
            "isolated_nodes": 1,
            "nodes": 1,
        }
    }
