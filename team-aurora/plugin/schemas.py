"""Tool schemas for knowledge-atlas plugin — what the LLM sees."""

KNOWLEDGE_EXTRACT = {
    "name": "knowledge_extract",
    "description": (
        "Extract entities and relationships from a given text. Returns structured JSON "
        "with entities (name, type, salience) and relationships (subject, predicate, object). "
        "Use this to build a knowledge graph from documents, research notes, or conversation content."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "text": {
                "type": "string",
                "description": "The text to extract entities and relationships from.",
            },
            "persist": {
                "type": "boolean",
                "description": "If true (default), add extracted entities/relationships to the local knowledge graph. If false, return them without saving.",
            },
        },
        "required": ["text"],
    },
}

KNOWLEDGE_QUERY = {
    "name": "knowledge_query",
    "description": (
        "Query the local knowledge graph for entities matching a search term. "
        "Returns matching entities and their relationships. Use this to find what the "
        "graph knows about a topic, person, place, or concept."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Search term — matches entity names (case-insensitive substring match).",
            },
            "limit": {
                "type": "number",
                "description": "Maximum number of entities to return (default: 20).",
            },
        },
        "required": ["query"],
    },
}

KNOWLEDGE_GRAPH_STATS = {
    "name": "knowledge_graph_stats",
    "description": (
        "Return statistics about the knowledge graph: entity count, relationship count, "
        "entity type distribution, and most connected entities. Use this to understand "
        "what the graph contains."
    ),
    "parameters": {
        "type": "object",
        "properties": {},
        "required": [],
    },
}