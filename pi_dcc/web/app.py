"""Flask web dashboard for the dust collection system."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from flask import Flask, jsonify, render_template, request

if TYPE_CHECKING:
    from pi_dcc.controller.engine import ControlEngine

logger = logging.getLogger(__name__)

app = Flask(__name__)

# Reference to the control engine (set during initialization)
_engine: ControlEngine | None = None


def init_app(engine: ControlEngine) -> Flask:
    """Initialize the Flask app with a reference to the control engine."""
    global _engine
    _engine = engine
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
