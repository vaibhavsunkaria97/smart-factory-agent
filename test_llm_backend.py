"""
test_llm_backend.py
===================
Tests for the reasoning layer.

This module previously contained the worst defect in the project: the backend
reported `backend: ollama` and returned plausible output while every LLM call
was silently failing, because requests went to the wrong endpoint and a bare
`except: pass` suppressed the exceptions.

These tests target that class of failure directly:

  * the offline reasoner must produce specific guidance for every fault type
  * multi-breach detections must address ALL breaches, not just the first
  * a broken backend must fall back rather than crash
  * `prefer` must be honoured, so the reported backend is the one in use

No network and no LLM are required - the LLM paths are exercised by injecting
failures and fake responses.
"""
import json
from unittest.mock import patch, MagicMock

import pytest

from llm_backend import Reasoner, _KB, _ML_ONLY
from detectors import Detection


# ---------------------------------------------------------------- helpers
def make_detection(breached=None, severity="HIGH", score=0.80,
                   temp=55.0, pressure=1.02, vibration=0.03):
    """Build a Detection without running the whole pipeline."""
    return Detection(
        index=0,
        timestamp="2024-06-03 19:33:00",
        values={"temp": temp, "pressure": pressure, "vibration": vibration},
        breached=breached if breached is not None else [("temp", "high", temp)],
        rule_flag=bool(breached),
        iforest_flag=True,
        score=score,
        severity=severity,
    )


# ================================================================
# 1. The offline reasoner - the deterministic floor
# ================================================================
def test_offline_returns_required_keys():
    """Contract: explain() always returns exactly diagnosis and action."""
    r = Reasoner(prefer="offline")
    out = r.explain(make_detection())
    assert set(out.keys()) == {"diagnosis", "action"}
    assert out["diagnosis"].strip()
    assert out["action"].strip()


@pytest.mark.parametrize("signal,direction", [
    ("temp", "high"), ("temp", "low"),
    ("pressure", "high"), ("pressure", "low"),
    ("vibration", "high"),
])
def test_offline_covers_every_fault_type(signal, direction):
    """Every (signal, direction) pair must have real guidance, not the
    generic ML-only fallback.

    This is the regression test for a real defect: the knowledge base
    originally held only the 'high' directions, so any low-side breach
    silently returned 'anomaly detected / investigate further' - which the
    brief explicitly requires NOT to happen.
    """
    r = Reasoner(prefer="offline")
    det = make_detection(breached=[(signal, direction, 99.0)])
    out = r.explain(det)

    assert (signal, direction) in _KB, f"knowledge base missing {(signal, direction)}"
    assert out["diagnosis"] != _ML_ONLY[0], (
        f"{signal} {direction} fell through to the generic fallback")
    assert out["action"] != _ML_ONLY[1]


def test_offline_multi_breach_addresses_all_breaches():
    """A row breaking three thresholds must get guidance for all three.

    The local model frequently names only one fault on multi-breach rows;
    the deterministic path must not.
    """
    r = Reasoner(prefer="offline")
    det = make_detection(
        breached=[("temp", "low", 38.0),
                  ("pressure", "low", 0.91),
                  ("vibration", "high", 0.12)],
        severity="CRITICAL", score=1.0)
    out = r.explain(det)
    text = (out["diagnosis"] + " " + out["action"]).lower()

    assert "temperature" in text or "temp" in text
    assert "pressure" in text
    assert "vibration" in text or "bearing" in text


def test_offline_ml_only_detection_uses_drift_language():
    """A detection with no threshold breach is early-warning drift, and
    should be described more tentatively than a confirmed breach."""
    r = Reasoner(prefer="offline")
    det = make_detection(breached=[], severity="LOW", score=0.25)
    out = r.explain(det)
    assert out["diagnosis"] == _ML_ONLY[0]
    assert out["action"] == _ML_ONLY[1]


def test_offline_is_deterministic():
    """Same input, same output - every time. This is the property the LLM
    path cannot guarantee, and the reason the offline path is authoritative."""
    r = Reasoner(prefer="offline")
    det = make_detection()
    assert r.explain(det) == r.explain(det) == r.explain(det)


# ================================================================
# 2. Backend selection - report observed state, not intended state
# ================================================================
def test_prefer_is_honoured():
    """If a backend is forced, that is the backend reported."""
    assert Reasoner(prefer="offline").backend == "offline"


def test_autodetect_falls_back_to_offline_without_ollama_or_keys(monkeypatch):
    """No Ollama, no API keys -> offline. The status must say so."""
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    with patch("llm_backend.urllib.request.urlopen", side_effect=OSError("refused")):
        assert Reasoner().backend == "offline"


def test_autodetect_selects_ollama_when_reachable(monkeypatch):
    """Ollama responding on /api/tags means ollama is selected."""
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    with patch("llm_backend.urllib.request.urlopen", return_value=MagicMock()):
        assert Reasoner().backend == "ollama"


def test_autodetect_selects_groq_when_key_present_and_no_ollama(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "gsk_test")
    with patch("llm_backend.urllib.request.urlopen", side_effect=OSError("refused")):
        assert Reasoner().backend == "groq"


# ================================================================
# 3. Graceful degradation - the defect that started all this
# ================================================================
def test_llm_failure_falls_back_instead_of_crashing():
    """A network failure must degrade to the deterministic path, not raise.

    This is the safety property the whole design rests on.
    """
    r = Reasoner(prefer="ollama")
    with patch.object(Reasoner, "_ollama", side_effect=OSError("connection refused")):
        out = r.explain(make_detection())
    assert set(out.keys()) == {"diagnosis", "action"}
    assert out["diagnosis"] == _KB[("temp", "high")][0]   # came from the KB


def test_malformed_llm_json_falls_back():
    """Unparseable output must not propagate a JSON error to the caller."""
    r = Reasoner(prefer="ollama")
    with patch.object(Reasoner, "_ollama",
                      side_effect=json.JSONDecodeError("bad", "doc", 0)):
        out = r.explain(make_detection())
    assert out["diagnosis"] == _KB[("temp", "high")][0]


def test_llm_timeout_falls_back():
    r = Reasoner(prefer="ollama")
    with patch.object(Reasoner, "_ollama", side_effect=TimeoutError):
        out = r.explain(make_detection())
    assert out["action"].strip()


# ================================================================
# 4. LLM output handling
# ================================================================
def test_valid_llm_output_is_used():
    """When the model returns well-formed JSON, that output is returned."""
    r = Reasoner(prefer="ollama")
    fake = {"diagnosis": "Overheating from restricted coolant flow.",
            "action": "Check the coolant pump and inspect the cooling fans."}
    with patch.object(Reasoner, "_ollama", return_value=fake):
        out = r.explain(make_detection())
    assert out["diagnosis"] == fake["diagnosis"]


def test_coerce_fills_missing_keys():
    """Output missing a key must not produce an empty alert."""
    out = Reasoner._coerce({"diagnosis": "Something is wrong."})
    assert out["action"].strip(), "missing action was not defaulted"
    assert set(out.keys()) == {"diagnosis", "action"}


def test_coerce_rejects_empty_strings():
    out = Reasoner._coerce({"diagnosis": "   ", "action": ""})
    assert out["diagnosis"].strip()
    assert out["action"].strip()


def test_llm_never_receives_ability_to_change_detection():
    """Structural guarantee: explain() returns text only.

    The reasoning layer cannot alter score, severity, or whether an alert
    fires. An LLM failure can degrade wording; it can never cause a missed
    fault. This test encodes that as a contract.
    """
    det = make_detection(severity="CRITICAL", score=1.0)
    before = (det.score, det.severity, list(det.breached))

    r = Reasoner(prefer="ollama")
    with patch.object(Reasoner, "_ollama",
                      return_value={"diagnosis": "x", "action": "y"}):
        out = r.explain(det)

    assert (det.score, det.severity, list(det.breached)) == before
    assert set(out.keys()) == {"diagnosis", "action"}


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))