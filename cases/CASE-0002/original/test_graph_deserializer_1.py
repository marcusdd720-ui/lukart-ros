from knowledge.serialization.deserializer import GraphDeserializer


def test_empty_graph():

    graph = GraphDeserializer().deserialize(
        {
            "nodes": [],
            "edges": [],
        }
    )

    assert graph.node_count() == 0
    assert graph.edge_count() == 0


def test_single_node():

    graph = GraphDeserializer().deserialize(
        {
            "nodes": [
                {
                    "id": "A",
                    "type": "ENTITY",
                    "name": "Node A",
                    "source": "",
                    "description": "",
                }
            ],
            "edges": [],
        }
    )

    assert graph.node_count() == 1
    assert graph.has_node("A")


def test_single_edge():

    graph = GraphDeserializer().deserialize(
        {
            "nodes": [
                {
                    "id": "A",
                    "type": "ENTITY",
                    "name": "A",
                    "source": "",
                    "description": "",
                },
                {
                    "id": "B",
                    "type": "ENTITY",
                    "name": "B",
                    "source": "",
                    "description": "",
                },
            ],
            "edges": [
                {
                    "id": "E1",
                    "source": "A",
                    "target": "B",
                    "type": "RELATES_TO",
                    "description": "",
                }
            ],
        }
    )

    assert graph.node_count() == 2
    assert graph.edge_count() == 1


def test_multiple_nodes_edges():

    graph = GraphDeserializer().deserialize(
        {
            "nodes": [
                {
                    "id": "A",
                    "type": "ENTITY",
                    "name": "A",
                    "source": "",
                    "description": "",
                },
                {
                    "id": "B",
                    "type": "ENTITY",
                    "name": "B",
                    "source": "",
                    "description": "",
                },
                {
                    "id": "C",
                    "type": "ENTITY",
                    "name": "C",
                    "source": "",
                    "description": "",
                },
            ],
            "edges": [
                {
                    "id": "E1",
                    "source": "A",
                    "target": "B",
                    "type": "RELATES_TO",
                    "description": "",
                },
                {
                    "id": "E2",
                    "source": "B",
                    "target": "C",
                    "type": "RELATES_TO",
                    "description": "",
                },
            ],
        }
    )

    assert graph.node_count() == 3
    assert graph.edge_count() == 2