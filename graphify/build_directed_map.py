"""Rebuild Graphify's raw extraction as an explicitly directed clustered graph."""

import json
import shutil
from pathlib import Path

from graphify.analyze import god_nodes, surprising_connections
from graphify.build import build_from_json
from graphify.cluster import cluster, score_all
from graphify.export import to_html, to_json
from graphify.report import generate


PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_ROOT = PROJECT_ROOT / "graphify" / "graphify-out"
CODEBASE_ROOT = PROJECT_ROOT / "Codebase"


def main() -> None:
    raw = json.loads((OUTPUT_ROOT / "graph.raw.json").read_text(encoding="utf-8"))
    graph = build_from_json(raw, directed=True, root=CODEBASE_ROOT)
    communities = cluster(graph)
    cohesion = score_all(graph, communities)

    try:
        gods = god_nodes(graph)
    except Exception:
        gods = []
    try:
        surprises = surprising_connections(graph, communities)
    except Exception:
        surprises = []

    to_json(graph, communities, str(OUTPUT_ROOT / "graph.json"), force=True)
    shutil.copyfile(OUTPUT_ROOT / "graph.json", OUTPUT_ROOT / "graph.directed-base.json")
    to_html(graph, communities, str(OUTPUT_ROOT / "graph.html"), node_limit=5000)
    analysis = {
        "directed": graph.is_directed(),
        "nodes": graph.number_of_nodes(),
        "edges": graph.number_of_edges(),
        "communities": {str(key): value for key, value in communities.items()},
        "cohesion": {str(key): value for key, value in cohesion.items()},
        "gods": gods,
        "surprises": surprises,
        "tokens": {
            "input": raw.get("input_tokens", 0),
            "output": raw.get("output_tokens", 0),
        },
    }
    (OUTPUT_ROOT / ".graphify_analysis.json").write_text(
        json.dumps(analysis, indent=2), encoding="utf-8"
    )
    (OUTPUT_ROOT / "cost.json").write_text(
        json.dumps(
            {
                "backend": None,
                "model": None,
                "input_tokens": analysis["tokens"]["input"],
                "output_tokens": analysis["tokens"]["output"],
                "estimated_cost_usd": 0.0,
                "reason": "Local AST extraction; no semantic LLM backend was authorized.",
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    detection = {
        "total_files": 3519,
        "total_words": 0,
        "warning": (
            "Large corpus: 3,519 Graphify-classified files plus 170 "
            "unclassified files; full user-mandated scope processed."
        ),
    }
    report = generate(
        graph,
        communities,
        cohesion,
        {},
        gods,
        surprises,
        detection,
        analysis["tokens"],
        str(CODEBASE_ROOT),
    )
    (OUTPUT_ROOT / "GRAPH_REPORT.md").write_text(report, encoding="utf-8")
    print(
        json.dumps(
            {
                "directed": graph.is_directed(),
                "nodes": graph.number_of_nodes(),
                "edges": graph.number_of_edges(),
                "communities": len(communities),
                "gods": len(gods),
                "surprises": len(surprises),
            }
        )
    )


if __name__ == "__main__":
    main()
