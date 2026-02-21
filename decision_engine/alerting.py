"""Alert generation based on scored objects and severity thresholds.

Maps risk scores to severity levels, determines who to notify, and produces
actionable plain-text guidance for staff/security/authorities.
"""

from __future__ import annotations

from decision_engine.config import ALERT_NOTIFY_MAP, SEVERITY_THRESHOLDS
from decision_engine.models import Alert, NotifyTarget, ScoredObject, Severity


def _severity_for_score(score: float) -> Severity:
    for threshold, sev in SEVERITY_THRESHOLDS:
        if score >= threshold:
            return Severity(sev)
    return Severity.LOW


_NEXT_STEPS: dict[str, dict[str, str]] = {
    "weapon": {
        "HIGH": "Dispatch armed security immediately. Keep drone tracking the individual. Do NOT engage.",
        "CRITICAL": "Alert authorities. Evacuate nearby zones. Maintain drone visual lock.",
    },
    "weapon?": {
        "HIGH": "Dispatch security to verify. Zoom in for confirmation. Keep distance.",
        "CRITICAL": "Treat as confirmed weapon until verified. Alert authorities.",
    },
    "fight": {
        "HIGH": "Dispatch security to intervene. Track all involved individuals.",
        "MEDIUM": "Monitor closely. Zoom in for documentation. Alert event staff.",
    },
    "medical_emergency": {
        "HIGH": "Dispatch medical team. Keep area clear for responders.",
        "MEDIUM": "Alert event staff. Monitor for deterioration.",
    },
    "fire": {
        "HIGH": "Alert fire department. Begin evacuation protocols. Ascend drone for overview.",
        "CRITICAL": "Emergency evacuation. Alert all authorities. Ascend to safe altitude.",
    },
    "unattended_bag": {
        "HIGH": "Dispatch bomb squad / security. Clear surrounding area.",
        "MEDIUM": "Send event staff to investigate. Keep drone hovering over the item.",
    },
    "crowd_cluster": {
        "HIGH": "Potential crush — alert security for crowd control. Gain altitude for overview.",
        "MEDIUM": "Monitor crowd density. Alert event staff if density increases.",
    },
    "stage_rush": {
        "CRITICAL": "Individual rushing stage — alert VIP detail immediately. Drone track and zoom.",
        "HIGH": "Possible stage approach — dispatch security to intercept. Maintain visual lock.",
    },
    "perimeter_breach": {
        "CRITICAL": "Active perimeter breach — alert all security teams. Drone reposition to track.",
        "HIGH": "Breach detected — dispatch nearest security unit. Zoom in for identification.",
        "MEDIUM": "Possible perimeter violation — send staff to verify. Monitor with drone.",
    },
    "rooftop_figure": {
        "CRITICAL": "Figure on rooftop with possible weapon — alert counter-sniper team and authorities.",
        "HIGH": "Person detected at elevated position — dispatch security to investigate. Drone zoom for ID.",
    },
    "suspicious_person": {
        "HIGH": "Suspicious individual near secured area — dispatch plainclothes security. Track with drone.",
        "MEDIUM": "Monitor individual closely. Zoom in for behavioral confirmation.",
    },
    "rushing_individual": {
        "CRITICAL": "Individual rushing toward VIP/stage — alert protective detail immediately.",
        "HIGH": "Person running in secured zone — dispatch security. Drone track for direction of travel.",
    },
    "unauthorized_vehicle": {
        "CRITICAL": "Unauthorized vehicle approaching secured perimeter — alert authorities. Possible VBIED.",
        "HIGH": "Unknown vehicle near event — dispatch security to intercept. Ascend for plate capture.",
    },
    "unauthorized_drone": {
        "HIGH": "Unknown drone in airspace — alert FAA liaison and security. Attempt visual ID.",
        "MEDIUM": "Possible drone detected — zoom in for confirmation. Log position and heading.",
    },
    "barricade_breach": {
        "HIGH": "Barricade breach — dispatch security to seal gap. Track individuals who entered.",
        "MEDIUM": "Barricade pressure detected — alert crowd management team.",
    },
    "vip_threat": {
        "CRITICAL": "Direct threat to VIP detected — alert protective detail. Evacuate if needed.",
        "HIGH": "Potential threat near VIP — dispatch advance security. Drone maintain overwatch.",
    },
    "protest_group": {
        "HIGH": "Protest group turning aggressive — alert riot response. Gain altitude for overview.",
        "MEDIUM": "Protest group active — monitor for escalation. Track group movement.",
    },
    "confrontation": {
        "HIGH": "Physical confrontation in progress — dispatch security. Track all involved parties.",
        "MEDIUM": "Verbal altercation detected — monitor for escalation. Zoom in for documentation.",
    },
}

_DEFAULT_NEXT_STEPS: dict[str, str] = {
    "CRITICAL": "Dispatch security and alert authorities immediately. Maintain drone visual.",
    "HIGH": "Dispatch security to investigate. Continue drone monitoring.",
    "MEDIUM": "Alert event staff to check. Zoom in for confirmation.",
    "LOW": "Log and continue monitoring.",
}


def _get_next_steps(label: str, severity: Severity) -> str:
    label_key = label.lower().strip()
    if label_key in _NEXT_STEPS:
        steps = _NEXT_STEPS[label_key]
        if severity.value in steps:
            return steps[severity.value]
    return _DEFAULT_NEXT_STEPS.get(severity.value, "Continue monitoring.")


def generate_alerts(scored_objects: list[ScoredObject]) -> list[Alert]:
    """Generate an alert for every object at MEDIUM severity or above."""
    alerts: list[Alert] = []

    for so in scored_objects:
        severity = _severity_for_score(so.risk_score)
        if severity == Severity.LOW:
            continue

        notify_keys = ALERT_NOTIFY_MAP.get(severity.value, ["event_staff"])
        notify = [NotifyTarget(k) for k in notify_keys]

        label = so.object.label
        confidence_pct = f"{so.object.confidence:.0%}"

        keyword_info = ""
        if so.matched_keywords:
            keyword_info = f" [matches operator watchlist: {', '.join(so.matched_keywords)}]"

        reason = (
            f"Detected '{label}' (confidence {confidence_pct}, risk score {so.risk_score})"
            f"{keyword_info}"
        )

        next_steps = _get_next_steps(label, severity)

        alerts.append(Alert(
            severity=severity,
            notify=notify,
            object_id=so.object.object_id,
            reason=reason,
            next_steps=next_steps,
        ))

    alerts.sort(key=lambda a: ["CRITICAL", "HIGH", "MEDIUM", "LOW"].index(a.severity.value))
    return alerts
