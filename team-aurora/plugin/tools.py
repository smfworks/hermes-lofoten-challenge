"""Tool handlers for knowledge-atlas plugin.

Pattern-based entity extraction using only Python stdlib.
No external NLP libraries — relies on capitalized phrases, quoted terms,
technical patterns, and relationship heuristics.
"""

import json
import re
import threading
from collections import defaultdict, Counter
from pathlib import Path
import os

_lock = threading.Lock()
_graph = None
_graph_loaded = False


def _get_graph_path() -> Path:
    """Get the knowledge graph storage path."""
    home = os.environ.get("HERMES_HOME", os.path.expanduser("~/.hermes"))
    atlas_dir = Path(home) / "knowledge-atlas"
    atlas_dir.mkdir(parents=True, exist_ok=True)
    return atlas_dir / "graph.json"


def _load_graph() -> dict:
    """Load the knowledge graph from disk (thread-safe)."""
    global _graph, _graph_loaded
    if not _graph_loaded:
        with _lock:
            if not _graph_loaded:
                path = _get_graph_path()
                if path.exists():
                    try:
                        _graph = json.loads(path.read_text())
                    except Exception:
                        _graph = _empty_graph()
                else:
                    _graph = _empty_graph()
                _graph_loaded = True
    return _graph


def _empty_graph() -> dict:
    """Create an empty graph structure."""
    return {
        "entities": {},  # {id: {name, type, salience, mentions}}
        "relationships": [],  # [{subject, predicate, object, source}]
        "metadata": {
            "created": None,
            "last_updated": None,
            "total_extractions": 0,
        },
    }


def _save_graph():
    """Save the knowledge graph to disk (thread-safe)."""
    import time
    with _lock:
        graph = _load_graph()
        graph["metadata"]["last_updated"] = time.time()
        try:
            path = _get_graph_path()
            path.write_text(json.dumps(graph, indent=2, default=str))
        except Exception:
            pass  # Never crash the agent


def _entity_id(name: str) -> str:
    """Create a stable entity ID from a name."""
    return re.sub(r'[^a-z0-9]+', '_', name.lower()).strip('_')


# Entity type patterns (ordered by specificity)
_TYPE_PATTERNS = [
    ("url", re.compile(r'https?://[^\s]+')),
    ("email", re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b')),
    ("version_number", re.compile(r'\bv?\d+\.\d+(?:\.\d+)?\b')),
    ("file_path", re.compile(r'(?:~|/|\.\.?/)[a-zA-Z0-9_/.-]+\.\w+')),
]

# Proper noun pattern: capitalized words/phrases (not at sentence start alone)
_PROPER_NOUN_RE = re.compile(
    r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\b'
)

# Technical term pattern: snake_case or camelCase identifiers
_TECH_TERM_RE = re.compile(
    r'\b([a-z]+_[a-z_]+|[a-z]+[A-Z][a-zA-Z]+)\b'
)

# Quoted term pattern
_QUOTED_RE = re.compile(r'"([^"]+)"|\'([^\']+)\'|`([^`]+)`')

# Acronym pattern
_ACRONYM_RE = re.compile(r'\b([A-Z]{2,6})\b')

# Relationship patterns
_RELATIONSHIP_PATTERNS = [
    (re.compile(r'(\b[A-Z][a-z]+)\s+is\s+(?:a|an)\s+(\w+)', re.I), "is_a"),
    (re.compile(r'(\b[A-Z][a-z]+)\s+has\s+(?:a|an)\s+(\w+)', re.I), "has"),
    (re.compile(r'(\b[A-Z][a-z]+)\s+uses?\s+(\b[A-Z][a-z]+)', re.I), "uses"),
    (re.compile(r'(\b[A-Z][a-z]+)\s+creates?\s+(\b[A-Z][a-z]+)', re.I), "creates"),
    (re.compile(r'(\b[A-Z][a-z]+)\s+connects?\s+to\s+(\b[A-Z][a-z]+)', re.I), "connects_to"),
    (re.compile(r'(\b[A-Z][a-z]+)\s+depends?\s+on\s+(\b[A-Z][a-z]+)', re.I), "depends_on"),
    (re.compile(r'(\b[A-Z][a-z]+)\s+extends?\s+(\b[A-Z][a-z]+)', re.I), "extends"),
]

# Stop words for entity filtering
_STOP_ENTITIES = {
    "The", "This", "That", "These", "Those", "It", "Its", "Is", "Are",
    "Was", "Were", "Will", "Would", "Could", "Should", "Has", "Have",
    "Had", "Do", "Does", "Did", "Not", "No", "Yes", "And", "Or", "But",
    "If", "Then", "Else", "When", "Where", "Why", "How", "What", "Who",
    "Use", "Using", "Used", "First", "Second", "Third", "Last", "Next",
    "Step", "Section", "Chapter", "Figure", "Table", "Note", "Important",
    "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday",
    "January", "February", "March", "April", "May", "June", "July",
    "August", "September", "October", "November", "December",
}


def _extract_entities(text: str) -> list:
    """Extract entities from text using pattern matching."""
    entities = []
    seen_ids = set()

    # 1. Typed pattern entities (URLs, emails, versions, paths)
    for etype, pattern in _TYPE_PATTERNS:
        for match in pattern.finditer(text):
            value = match.group(0)
            eid = _entity_id(f"{etype}_{value}")
            if eid not in seen_ids:
                seen_ids.add(eid)
                entities.append({
                    "name": value,
                    "type": etype,
                    "salience": 0.8,
                })

    # 2. Proper nouns (capitalized phrases)
    for match in _PROPER_NOUN_RE.finditer(text):
        name = match.group(1).strip()
        if name in _STOP_ENTITIES or len(name) < 3:
            continue
        # Check if it's at the start of a line (likely sentence start, not proper noun)
        start = match.start()
        if start == 0 or text[start - 1] in '.\n':
            # It's sentence-initial — only count if it appears elsewhere too
            if text.count(name) < 2:
                continue
        eid = _entity_id(name)
        if eid not in seen_ids:
            seen_ids.add(eid)
            salience = min(1.0, 0.3 + (text.count(name) * 0.15))
            entities.append({
                "name": name,
                "type": "proper_noun",
                "salience": round(salience, 2),
            })

    # 3. Quoted terms
    for match in _QUOTED_RE.finditer(text):
        name = match.group(1) or match.group(2) or match.group(3)
        if name and len(name) > 2:
            eid = _entity_id(name)
            if eid not in seen_ids:
                seen_ids.add(eid)
                entities.append({
                    "name": name,
                    "type": "quoted_term",
                    "salience": 0.7,
                })

    # 4. Technical terms (snake_case, camelCase)
    for match in _TECH_TERM_RE.finditer(text):
        name = match.group(1)
        if len(name) > 4:
            eid = _entity_id(name)
            if eid not in seen_ids:
                seen_ids.add(eid)
                entities.append({
                    "name": name,
                    "type": "technical_term",
                    "salience": 0.6,
                })

    # 5. Acronyms
    for match in _ACRONYM_RE.finditer(text):
        name = match.group(1)
        if name not in {"API", "URL", "JSON", "XML", "HTML", "CSS", "SQL", "HTTP", "HTTPS", "TCP", "UDP", "DNS", "SSH", "FTP"}:
            # Common acronyms are still entities but we don't filter them out
            pass
        eid = _entity_id(name)
        if eid not in seen_ids:
            seen_ids.add(eid)
            entities.append({
                "name": name,
                "type": "acronym",
                "salience": 0.5,
            })

    return entities


def _extract_relationships(text: str, entities: list) -> list:
    """Extract relationships between entities from text."""
    relationships = []
    entity_names = {e["name"].lower(): e["name"] for e in entities}

    for pattern, predicate in _RELATIONSHIP_PATTERNS:
        for match in pattern.finditer(text):
            subj = match.group(1)
            obj = match.group(2)
            if subj.lower() in entity_names and obj.lower() in entity_names:
                relationships.append({
                    "subject": subj,
                    "predicate": predicate,
                    "object": obj,
                })

    # Co-occurrence relationships (entities mentioned in the same sentence)
    sentences = re.split(r'[.!?]+', text)
    for sent in sentences:
        sent_entities = []
        for e in entities:
            if e["name"].lower() in sent.lower():
                sent_entities.append(e["name"])
        # Link co-occurring entities
        for i, e1 in enumerate(sent_entities):
            for e2 in sent_entities[i+1:]:
                if e1 != e2:
                    relationships.append({
                        "subject": e1,
                        "predicate": "co_occurs_with",
                        "object": e2,
                    })

    return relationships


def _add_to_graph(entities: list, relationships: list):
    """Add extracted entities and relationships to the persistent graph."""
    graph = _load_graph()
    import time

    for e in entities:
        eid = _entity_id(e["name"])
        if eid in graph["entities"]:
            graph["entities"][eid]["mentions"] += 1
            graph["entities"][eid]["salience"] = max(
                graph["entities"][eid]["salience"],
                e["salience"]
            )
        else:
            graph["entities"][eid] = {
                "name": e["name"],
                "type": e["type"],
                "salience": e["salience"],
                "mentions": 1,
            }

    for r in relationships:
        # Deduplicate relationships
        exists = any(
            existing["subject"].lower() == r["subject"].lower()
            and existing["predicate"] == r["predicate"]
            and existing["object"].lower() == r["object"].lower()
            for existing in graph["relationships"]
        )
        if not exists:
            graph["relationships"].append(r)

    graph["metadata"]["total_extractions"] += 1
    if not graph["metadata"]["created"]:
        graph["metadata"]["created"] = time.time()


def knowledge_extract(args: dict, **kwargs) -> str:
    """Extract entities and relationships from text."""
    try:
        text = args.get("text", "")
        if not text or not text.strip():
            return json.dumps({"error": "No text provided"})

        persist = args.get("persist", True)

        entities = _extract_entities(text)
        relationships = _extract_relationships(text, entities)

        if persist:
            _add_to_graph(entities, relationships)
            _save_graph()

        return json.dumps({
            "entities_found": len(entities),
            "relationships_found": len(relationships),
            "entities": entities[:50],  # Cap for response size
            "relationships": relationships[:30],
            "persisted": persist,
        }, indent=2)
    except Exception as e:
        return json.dumps({"error": f"Extraction failed: {e}"})


def knowledge_query(args: dict, **kwargs) -> str:
    """Query the knowledge graph for matching entities."""
    try:
        query = args.get("query", "")
        if not query or not query.strip():
            return json.dumps({"error": "No query provided"})

        limit = args.get("limit", 20)
        graph = _load_graph()

        query_lower = query.lower()
        matches = []
        for eid, entity in graph["entities"].items():
            if query_lower in entity["name"].lower():
                matches.append(entity)

        # Sort by salience * mentions
        matches.sort(key=lambda e: e["salience"] * e["mentions"], reverse=True)
        matches = matches[:limit]

        # Find relationships involving matched entities
        match_names = {m["name"].lower() for m in matches}
        related = []
        for r in graph["relationships"]:
            if r["subject"].lower() in match_names or r["object"].lower() in match_names:
                related.append(r)

        return json.dumps({
            "query": query,
            "entities_found": len(matches),
            "entities": matches,
            "relationships_found": len(related),
            "relationships": related[:30],
        }, indent=2)
    except Exception as e:
        return json.dumps({"error": f"Query failed: {e}"})


def knowledge_graph_stats(args: dict, **kwargs) -> str:
    """Return statistics about the knowledge graph."""
    try:
        graph = _load_graph()
        entities = graph["entities"]
        relationships = graph["relationships"]

        # Type distribution
        type_dist = Counter(e["type"] for e in entities.values())

        # Most connected entities
        entity_connections = Counter()
        for r in relationships:
            entity_connections[r["subject"]] += 1
            entity_connections[r["object"]] += 1

        most_connected = [
            {"name": name, "connections": count}
            for name, count in entity_connections.most_common(10)
        ]

        # Predicate distribution
        predicate_dist = Counter(r["predicate"] for r in relationships)

        return json.dumps({
            "total_entities": len(entities),
            "total_relationships": len(relationships),
            "type_distribution": dict(type_dist),
            "predicate_distribution": dict(predicate_dist),
            "most_connected_entities": most_connected,
            "total_extractions": graph["metadata"].get("total_extractions", 0),
        }, indent=2)
    except Exception as e:
        return json.dumps({"error": f"Stats failed: {e}"})