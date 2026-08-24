#!/usr/bin/env python3
"""
Agent-UX integration hook — emit event envelopes for workflow visualization.
Graceful degradation if agent-ux unavailable.
"""

import json
import sys
from typing import Optional


def emit_event(event_type: str, phase: str, status: str, delta: dict = None) -> bool:
    """
    Emit event envelope to agent-ux for visualization.

    Args:
        event_type: 'breadcrumb_only' or 'out_of_scope_flag'
        phase: Current phase (Release Planning, Deployment, Monitoring)
        status: in_progress, complete, blocked
        delta: Optional event-specific delta payload

    Returns:
        True if sent successfully, False if unavailable (graceful degradation)
    """
    envelope = {
        "caller": "deployment-ops-plugin",
        "event_type": event_type,
        "phase_state": {
            "phase": phase,
            "status": status
        },
        "delta": delta or {},
        "artifact_path": None
    }

    try:
        # In a real implementation, this would communicate with agent-ux
        # For now, log the event
        print(f"[ux-event] {json.dumps(envelope)}", file=sys.stderr)
        return True
    except Exception as e:
        # Graceful degradation: log once per session, never fail the operation
        print(f"[ux-event-unavailable] agent-ux not available: {e}", file=sys.stderr)
        return False


def phase_started(phase: str) -> None:
    """Signal that a phase (Release Planning, Deployment, Monitoring) is starting."""
    emit_event("breadcrumb_only", phase, "in_progress")


def phase_complete(phase: str) -> None:
    """Signal that a phase completed successfully."""
    emit_event("breadcrumb_only", phase, "complete")


def phase_blocked(phase: str, reason: str) -> None:
    """Signal that a phase is blocked with a reason."""
    emit_event("out_of_scope_flag", phase, "blocked", {"reason": reason})


if __name__ == "__main__":
    # Test: emit a sample event
    phase_started("Release Planning")
