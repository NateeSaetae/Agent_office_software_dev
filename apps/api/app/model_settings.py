"""Per-agent model selection validated against the live Codex catalog."""
from __future__ import annotations
from .agents import AGENTS


def agent_settings(store, agent_id: str) -> dict:
    if agent_id not in {a["id"] for a in AGENTS}:
        raise KeyError(agent_id)
    try:
        saved = store.get("agent_settings", agent_id)
    except KeyError:
        saved = {}
    return {"model": saved.get("model"), "reasoning": saved.get("reasoning")}


def validate_selection(catalog: list[dict], model: str | None, reasoning: str | None) -> dict:
    if model is None:
        if reasoning is not None:
            raise ValueError("Choose an explicit model before selecting reasoning")
        return {"model": None, "reasoning": None}
    selected = next((m for m in catalog if m["model"] == model), None)
    if selected is None:
        raise ValueError("Model is not available in the current account catalog. Refresh models and choose again.")
    if reasoning is not None and reasoning not in {r["value"] for r in selected["reasoning_efforts"]}:
        raise ValueError("Reasoning effort is not supported by the selected model")
    return {"model": model, "reasoning": reasoning}
