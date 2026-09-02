"""
Knowledge Operating System (KOS)

File: knowledge/graph.py
Version: 4.0
Sprint: GRAPH-018

High-performance directed Knowledge Graph.
"""

from __future__ import annotations

from collections import deque
from collections.abc import Iterable, Iterator
from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any

EntityId = str

from knowledge.edge import KnowledgeEdge
from knowledge.node import KnowledgeNode
