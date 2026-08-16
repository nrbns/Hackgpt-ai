"""Risk register domain service + deterministic risk scoring."""

from __future__ import annotations

from typing import Any

from app.enterprise import (
    create_risk,
    delete_risk,
    get_risk,
    list_risks,
    update_risk,
)

__all__ = [
    "create_risk",
    "delete_risk",
    "get_risk",
    "list_risks",
    "update_risk",
    "compute_risk_score",
    "explain_risk_score",
]

_CRITICALITY = {"critical": 1.0, "high": 0.85, "medium": 0.65, "low": 0.4, "info": 0.2}


def compute_risk_score(
    *,
    cvss: float | None = None,
    exploitability: float | None = None,
    exposure: float | None = None,
    asset_criticality: str | None = None,
    threat_intel: float | None = None,
    confidence: float | None = None,
) -> dict[str, Any]:
    """Deterministic 0–100 risk score. AI should explain this, not invent it.

    Inputs are normalized to 0–1 (CVSS /10). Missing factors use neutral defaults
    so scores stay reproducible across runs.
    """
    cvss_n = max(0.0, min(1.0, (float(cvss) if cvss is not None else 5.0) / 10.0))
    exploit_n = max(0.0, min(1.0, float(exploitability) if exploitability is not None else 0.5))
    exposure_n = max(0.0, min(1.0, float(exposure) if exposure is not None else 0.5))
    crit_n = _CRITICALITY.get((asset_criticality or "medium").lower(), 0.65)
    intel_n = max(0.0, min(1.0, float(threat_intel) if threat_intel is not None else 0.4))
    conf_n = max(0.0, min(1.0, float(confidence) if confidence is not None else 0.7))

    # Weighted blend — documented weights for auditability
    weights = {
        "cvss": 0.35,
        "exploitability": 0.20,
        "exposure": 0.15,
        "asset_criticality": 0.15,
        "threat_intel": 0.10,
        "confidence": 0.05,
    }
    raw = (
        weights["cvss"] * cvss_n
        + weights["exploitability"] * exploit_n
        + weights["exposure"] * exposure_n
        + weights["asset_criticality"] * crit_n
        + weights["threat_intel"] * intel_n
        + weights["confidence"] * conf_n
    )
    score = round(raw * 100, 1)
    factors = {
        "cvss": round(cvss_n, 3),
        "exploitability": round(exploit_n, 3),
        "exposure": round(exposure_n, 3),
        "asset_criticality": round(crit_n, 3),
        "threat_intel": round(intel_n, 3),
        "confidence": round(conf_n, 3),
    }
    return {
        "score": score,
        "band": _band(score),
        "weights": weights,
        "factors": factors,
        "formula": "weighted_sum(cvss,exploitability,exposure,criticality,intel,confidence)*100",
    }


def explain_risk_score(result: dict[str, Any]) -> str:
    """Human-readable explanation of a compute_risk_score() result."""
    factors = result.get("factors") or {}
    weights = result.get("weights") or {}
    parts = [
        f"{name}={factors.get(name)}×{weights.get(name)}"
        for name in ("cvss", "exploitability", "exposure", "asset_criticality", "threat_intel", "confidence")
        if name in factors
    ]
    return (
        f"Risk score {result.get('score')} ({result.get('band')}): "
        + " + ".join(parts)
        + f". Formula: {result.get('formula')}."
    )


def _band(score: float) -> str:
    if score >= 85:
        return "critical"
    if score >= 70:
        return "high"
    if score >= 45:
        return "medium"
    if score >= 25:
        return "low"
    return "info"
