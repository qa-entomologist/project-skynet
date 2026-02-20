"""Graph storage for the website exploration map.

Supports Neo4j for persistent storage and falls back to an in-memory graph.
Both backends expose the same interface so the agent tools don't care which is active.
"""

import json
import time
import logging
from dataclasses import dataclass, field, asdict

logger = logging.getLogger(__name__)


@dataclass
class PageNode:
    id: str
    url: str
    title: str
    domain: str
    path: str
    page_type: str = "unknown"
    screenshot_path: str = ""
    element_count: int = 0
    timestamp: float = field(default_factory=time.time)
    visited: bool = False
    depth: int = 0
    observations: str = ""
    available_actions: str = ""


@dataclass
class ActionEdge:
    from_id: str
    to_id: str
    action_type: str  # "click", "navigate", "back"
    element_text: str = ""
    element_selector: str = ""
    timestamp: float = field(default_factory=time.time)
    observation: str = ""


class MemoryGraphStore:
    """In-memory graph store using plain dicts."""

    def __init__(self):
        self.pages: dict[str, PageNode] = {}
        self.edges: list[ActionEdge] = []

    def add_page(self, page: PageNode) -> bool:
        """Add a page node. Returns True if it's new."""
        if page.id in self.pages:
            return False
        self.pages[page.id] = page
        return True

    def update_page(self, page_id: str, **kwargs):
        if page_id in self.pages:
            for k, v in kwargs.items():
                setattr(self.pages[page_id], k, v)

    def add_edge(self, edge: ActionEdge):
        self.edges.append(edge)

    def get_page(self, page_id: str) -> PageNode | None:
        return self.pages.get(page_id)

    def is_visited(self, page_id: str) -> bool:
        page = self.pages.get(page_id)
        return page.visited if page else False

    def mark_visited(self, page_id: str):
        if page_id in self.pages:
            self.pages[page_id].visited = True

    def page_count(self) -> int:
        return len(self.pages)

    def visited_count(self) -> int:
        return sum(1 for p in self.pages.values() if p.visited)

    def get_stats(self) -> dict:
        return {
            "total_pages": len(self.pages),
            "visited_pages": self.visited_count(),
            "total_edges": len(self.edges),
            "domains": list({p.domain for p in self.pages.values()}),
        }

    def get_flows(self) -> list[list[dict]]:
        """Extract all distinct user flows (paths) from the graph.

        Each flow is a sequence of steps: page -> action -> page -> action -> ...
        Only follows forward edges (click/navigate), not back edges.
        """
        forward_edges = [e for e in self.edges if e.action_type != "back"]

        adj: dict[str, list[ActionEdge]] = {}
        for edge in forward_edges:
            adj.setdefault(edge.from_id, []).append(edge)

        roots = set(self.pages.keys())
        for edge in forward_edges:
            roots.discard(edge.to_id)
        if not roots:
            roots = {next(iter(self.pages))} if self.pages else set()

        flows = []

        def dfs(node_id: str, path: list[dict]):
            page = self.pages.get(node_id)
            if not page:
                return

            step = {
                "page_id": page.id,
                "url": page.url,
                "title": page.title,
                "page_type": page.page_type,
                "observations": page.observations,
                "available_actions": page.available_actions,
            }
            path.append(step)

            outgoing = adj.get(node_id, [])
            if not outgoing:
                flows.append(list(path))
            else:
                for edge in outgoing:
                    action_step = {
                        "action": edge.action_type,
                        "element_text": edge.element_text,
                        "element_selector": edge.element_selector,
                        "observation": edge.observation,
                    }
                    path.append(action_step)
                    dfs(edge.to_id, path)
                    path.pop()

            path.pop()

        for root in roots:
            dfs(root, [])

        return flows

    def to_json(self) -> str:
        """Export the full graph as JSON for visualization."""
        nodes = [asdict(p) for p in self.pages.values()]
        edges = [asdict(e) for e in self.edges]
        return json.dumps({"nodes": nodes, "edges": edges}, indent=2, default=str)


class Neo4jGraphStore:
    """Neo4j-backed graph store."""

    def __init__(self, uri: str, user: str, password: str):
        from neo4j import GraphDatabase
        self._driver = GraphDatabase.driver(uri, auth=(user, password))
        self._ensure_constraints()

    def _ensure_constraints(self):
        with self._driver.session() as session:
            session.run(
                "CREATE CONSTRAINT page_id IF NOT EXISTS FOR (p:Page) REQUIRE p.id IS UNIQUE"
            )

    def close(self):
        self._driver.close()

    def add_page(self, page: PageNode) -> bool:
        with self._driver.session() as session:
            result = session.run(
                """
                MERGE (p:Page {id: $id})
                ON CREATE SET
                    p.url = $url, p.title = $title, p.domain = $domain,
                    p.path = $path, p.page_type = $page_type,
                    p.screenshot_path = $screenshot_path,
                    p.element_count = $element_count,
                    p.timestamp = $timestamp, p.visited = $visited,
                    p.depth = $depth, p._created = true
                RETURN p._created AS created
                """,
                **asdict(page),
            )
            record = result.single()
            return bool(record and record["created"])

    def update_page(self, page_id: str, **kwargs):
        set_clauses = ", ".join(f"p.{k} = ${k}" for k in kwargs)
        with self._driver.session() as session:
            session.run(
                f"MATCH (p:Page {{id: $page_id}}) SET {set_clauses}",
                page_id=page_id,
                **kwargs,
            )

    def add_edge(self, edge: ActionEdge):
        with self._driver.session() as session:
            session.run(
                """
                MATCH (from:Page {id: $from_id})
                MATCH (to:Page {id: $to_id})
                CREATE (from)-[:ACTION {
                    action_type: $action_type,
                    element_text: $element_text,
                    element_selector: $element_selector,
                    timestamp: $timestamp
                }]->(to)
                """,
                **asdict(edge),
            )

    def get_page(self, page_id: str) -> PageNode | None:
        with self._driver.session() as session:
            result = session.run("MATCH (p:Page {id: $id}) RETURN p", id=page_id)
            record = result.single()
            if not record:
                return None
            props = dict(record["p"])
            props.pop("_created", None)
            return PageNode(**{k: v for k, v in props.items() if k in PageNode.__dataclass_fields__})

    def is_visited(self, page_id: str) -> bool:
        page = self.get_page(page_id)
        return page.visited if page else False

    def mark_visited(self, page_id: str):
        self.update_page(page_id, visited=True)

    def page_count(self) -> int:
        with self._driver.session() as session:
            result = session.run("MATCH (p:Page) RETURN count(p) AS c")
            return result.single()["c"]

    def visited_count(self) -> int:
        with self._driver.session() as session:
            result = session.run("MATCH (p:Page {visited: true}) RETURN count(p) AS c")
            return result.single()["c"]

    def get_stats(self) -> dict:
        with self._driver.session() as session:
            pages = session.run("MATCH (p:Page) RETURN count(p) AS c").single()["c"]
            visited = session.run("MATCH (p:Page {visited: true}) RETURN count(p) AS c").single()["c"]
            edges = session.run("MATCH ()-[r:ACTION]->() RETURN count(r) AS c").single()["c"]
            domains = session.run("MATCH (p:Page) RETURN DISTINCT p.domain AS d").values()
            return {
                "total_pages": pages,
                "visited_pages": visited,
                "total_edges": edges,
                "domains": [r[0] for r in domains],
            }

    def to_json(self) -> str:
        with self._driver.session() as session:
            pages = session.run("MATCH (p:Page) RETURN p").values()
            edges = session.run(
                "MATCH (a)-[r:ACTION]->(b) RETURN a.id AS from_id, b.id AS to_id, r.action_type AS action_type, r.element_text AS element_text"
            ).values()

        nodes = []
        for (p,) in pages:
            props = dict(p)
            props.pop("_created", None)
            nodes.append(props)

        edge_list = [
            {"from_id": e[0], "to_id": e[1], "action_type": e[2], "element_text": e[3]}
            for e in edges
        ]
        return json.dumps({"nodes": nodes, "edges": edge_list}, indent=2, default=str)


def create_graph_store(use_neo4j: bool = False) -> MemoryGraphStore | Neo4jGraphStore:
    """Factory function - tries Neo4j, falls back to in-memory."""
    if use_neo4j:
        from src.config import NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD
        try:
            store = Neo4jGraphStore(NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD)
            logger.info("Connected to Neo4j at %s", NEO4J_URI)
            return store
        except Exception as e:
            logger.warning("Neo4j unavailable (%s), falling back to in-memory graph", e)

    logger.info("Using in-memory graph store")
    return MemoryGraphStore()
