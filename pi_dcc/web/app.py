"""Flask web dashboard for the dust collection system."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from flask import Flask, jsonify, render_template, request

if TYPE_CHECKING:
    from pi_dcc.controller.engine import ControlEngine
    from pi_dcc.config.schema import AppConfig

logger = logging.getLogger(__name__)

app = Flask(__name__)

# Reference to the control engine (set during initialization)
_engine: ControlEngine | None = None
_config: AppConfig | None = None


def init_app(engine: ControlEngine) -> Flask:
    """Initialize the Flask app with a reference to the control engine."""
    global _engine, _config
    _engine = engine
    _config = engine._config
    return app


@app.route("/")
def dashboard():
    """Render the main dashboard page."""
    return render_template("dashboard.html")


@app.route("/api/status")
def api_status():
    """Return current system status as JSON."""
    if _engine is None:
        return jsonify({"error": "System not initialized"}), 503

    state = _engine.state.to_dict()
    return jsonify(state)


@app.route("/api/filter/reset", methods=["POST"])
def api_filter_reset():
    """Reset the cumulative runtime counter after filter cleaning."""
    if _engine is None:
        return jsonify({"error": "System not initialized"}), 503

    _engine.reset_filter_runtime()
    return jsonify({"status": "ok", "message": "Filter runtime counter reset"})


@app.route("/api/config/reload", methods=["POST"])
def api_config_reload():
    """Reload configuration (placeholder for future implementation)."""
    return jsonify({"status": "error", "message": "Not yet implemented"}), 501


@app.route("/api/network")
def api_network():
    """Return the network topology and tool/trigger mappings for visualization."""
    if _config is None:
        return jsonify({"error": "System not initialized"}), 503

    def serialize_node(node):
        result = {
            "id": node.id,
            "pipe_diameter_inches": node.pipe_diameter_inches,
            "children": [serialize_node(c) for c in node.children],
        }
        if node.blast_gate:
            result["blast_gate"] = {
                "id": node.blast_gate.id,
                "diameter_inches": node.blast_gate.diameter_inches,
            }
        return result

    # Build tool/trigger-to-node mapping
    tool_map = {}
    for tool in _config.tools:
        for nid in tool.node_ids:
            tool_map.setdefault(nid, []).append({"id": tool.id, "name": tool.name, "type": "tool"})
    for trigger in _config.manual_triggers:
        for nid in trigger.node_ids:
            tool_map.setdefault(nid, []).append({"id": trigger.id, "name": trigger.name, "type": "trigger"})

    return jsonify({
        "network": serialize_node(_config.network),
        "tool_map": tool_map,
    })
