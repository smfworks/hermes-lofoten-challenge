"""Knowledge-atlas plugin — registration.

Lightweight knowledge graph with pattern-based entity extraction.
Provides three tools and a /atlas slash command. Passively extracts
entities from session turns via a post_llm_call hook.

Like the Lofoten stockfish racks — each turn adds to the graph slowly,
patiently, until the accumulated knowledge is ready to use.
"""

import json
import logging

from . import schemas, tools

logger = logging.getLogger(__name__)


def _on_post_llm_call(session_id, user_message, assistant_response,
                      conversation_history=None, model="", platform="",
                      is_first_turn=False, **kwargs):
    """Hook: passively extracts entities from the assistant response."""
    try:
        if not assistant_response or len(assistant_response) < 50:
            return None

        # Only extract from substantial responses (skip short replies)
        if len(assistant_response) > 200:
            entities = tools._extract_entities(assistant_response)
            if entities:
                # Persist quietly — no context injection
                tools._add_to_graph(entities, [])
                tools._save_graph()
                logger.debug("knowledge-atlas: extracted %d entities from turn", len(entities))
    except Exception as e:
        logger.debug("knowledge-atlas: post_llm_call hook error: %s", e)

    # Return None — observer-only, no context injection
    return None


def _handle_atlas(raw_args: str) -> str:
    """Slash command: /atlas — shows graph stats or queries."""
    try:
        raw = raw_args.strip()
        if not raw or raw == "stats":
            result = tools.knowledge_graph_stats({})
            data = json.loads(result)
            if "error" in data:
                return f"❌ {data['error']}"

            lines = ["🗺️ **Knowledge Atlas Stats**", ""]
            lines.append(f"**Entities:** {data['total_entities']}")
            lines.append(f"**Relationships:** {data['total_relationships']}")
            lines.append(f"**Extractions:** {data['total_extractions']}")
            lines.append("")

            type_dist = data.get("type_distribution", {})
            if type_dist:
                lines.append("**Entity types:**")
                for t, c in sorted(type_dist.items(), key=lambda x: -x[1]):
                    lines.append(f"  • {t}: {c}")

            pred_dist = data.get("predicate_distribution", {})
            if pred_dist:
                lines.append(f"\n**Relationship types:**")
                for p, c in sorted(pred_dist.items(), key=lambda x: -x[1]):
                    lines.append(f"  • {p}: {c}")

            most_connected = data.get("most_connected_entities", [])
            if most_connected:
                lines.append(f"\n**Most connected:**")
                for e in most_connected[:5]:
                    lines.append(f"  • {e['name']}: {e['connections']} connections")

            return "\n".join(lines)

        else:
            # Treat as a query
            result = tools.knowledge_query({"query": raw})
            data = json.loads(result)
            if "error" in data:
                return f"❌ {data['error']}"

            lines = [f"🗺️ **Atlas query: '{raw}'**", ""]
            lines.append(f"**Entities found:** {data['entities_found']}")

            for e in data.get("entities", [])[:10]:
                lines.append(f"  • {e['name']} ({e['type']}, salience={e['salience']}, mentions={e['mentions']})")

            if data.get("relationships"):
                lines.append(f"\n**Relationships:** {data['relationships_found']}")
                for r in data["relationships"][:10]:
                    lines.append(f"  • {r['subject']} — {r['predicate']} → {r['object']}")

            return "\n".join(lines)
    except Exception as e:
        return f"❌ Atlas command failed: {e}"


def register(ctx):
    """Wire schemas to handlers and register hooks."""
    ctx.register_tool(
        name="knowledge_extract",
        toolset="knowledge_atlas",
        schema=schemas.KNOWLEDGE_EXTRACT,
        handler=tools.knowledge_extract,
    )

    ctx.register_tool(
        name="knowledge_query",
        toolset="knowledge_atlas",
        schema=schemas.KNOWLEDGE_QUERY,
        handler=tools.knowledge_query,
    )

    ctx.register_tool(
        name="knowledge_graph_stats",
        toolset="knowledge_atlas",
        schema=schemas.KNOWLEDGE_GRAPH_STATS,
        handler=tools.knowledge_graph_stats,
    )

    # Passive extraction hook — observer only, no context injection
    ctx.register_hook("post_llm_call", _on_post_llm_call)

    # Slash command
    ctx.register_command(
        "atlas",
        handler=_handle_atlas,
        description="Knowledge atlas — /atlas stats or /atlas <query>",
    )

    logger.info("knowledge-atlas: registered 3 tools, 1 hook, 1 command")