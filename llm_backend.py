"""
llm_backend.py
==============
Turns a Detection into a human-readable diagnosis and a concrete action.

Backend priority, all free:
    1. Ollama   - local, offline, factory-floor friendly
    2. Groq     - free-tier hosted
    3. Offline  - deterministic maintenance knowledge base

Design point: the LLM never changes a DETECTION. It only phrases the
explanation. Detection stays deterministic and unit-testable, so correctness
never depends on non-reproducible model output.
"""
import json
import os
import urllib.request

# Real maintenance knowledge, keyed on (signal, direction).
_KB = {
    ("temp", "high"): (
        "Overheating: coolant flow restriction, fan degradation, or excessive load.",
        "Verify coolant pump flow and filter; inspect cooling fans; reduce load and recheck in 5 min.",
    ),
    ("temp", "low"): (
        "Under-temperature: sensor fault, incomplete warm-up, or chiller over-cooling.",
        "Confirm the line has reached steady state; validate the sensor against a reference probe.",
    ),
    ("pressure", "high"): (
        "Over-pressure: blocked outlet, stuck relief valve, or downstream restriction.",
        "Inspect relief valve and outlet line; verify no downstream blockage.",
    ),
    ("pressure", "low"): (
        "Under-pressure: leak, pump cavitation, or supply loss.",
        "Leak-check seals and fittings; confirm supply pressure; inspect pump for cavitation.",
    ),
    ("vibration", "high"): (
        "Excess vibration: bearing wear, shaft misalignment, or loosened mounting.",
        "Schedule bearing inspection; check shaft alignment and mounting bolt torque.",
    ),
}

_ML_ONLY = (
    "Multivariate pattern outside the learned normal envelope; no single threshold breached.",
    "Treat as early-warning drift; review correlated channels against the last known-good baseline.",
)

_SYSTEM = (
    "You are a factory equipment reliability engineer. Given one anomalous "
    "sensor reading, reply with STRICT JSON only: "
    '{"diagnosis": str, "action": str}. Each field under 30 words, concrete '
    "and actionable. No extra keys, no prose outside the JSON."
)


class Reasoner:
    def __init__(self, prefer=None, timeout=30.0):
        self.timeout = timeout
        self.backend = prefer or self._detect()

    def _detect(self):
        try:
            # /api/tags is the real health endpoint. The root URL is a web page.
            urllib.request.urlopen("http://localhost:11434/api/tags", timeout=2.0)
            return "ollama"
        except Exception:
            if os.getenv("GROQ_API_KEY"):
                return "groq"
            return "offline"

    def explain(self, detection):
        try:
            if self.backend == "ollama":
                return self._ollama(detection)
            if self.backend == "groq":
                return self._groq(detection)
        except Exception:
            pass  # any failure -> deterministic path
        return self._offline(detection)

    def _describe(self, d):
        b = ", ".join(f"{s} too {dirn} ({v:.2f})" for s, dirn, v in d.breached) or "none"
        return (f"Reading at {d.timestamp}. temp={d.values['temp']:.2f}C, "
                f"pressure={d.values['pressure']:.3f}, vibration={d.values['vibration']:.3f}. "
                f"Breached: {b}. Score {d.score:.2f}, severity {d.severity}.")

    def _ollama(self, d):
        body = json.dumps({
            "model": os.getenv("OLLAMA_MODEL", "llama3.2"),
            "prompt": f"{_SYSTEM}\n\n{self._describe(d)}",
            "stream": False,
            "format": "json",
        }).encode()
        req = urllib.request.Request(
            "http://localhost:11434/api/generate", body,
            {"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=self.timeout) as f:
            return self._coerce(json.loads(json.loads(f.read())["response"]))

    def _groq(self, d):
        body = json.dumps({
            "model": os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile"),
            "messages": [{"role": "system", "content": _SYSTEM},
                         {"role": "user", "content": self._describe(d)}],
            "response_format": {"type": "json_object"},
        }).encode()
        req = urllib.request.Request(
            "https://api.groq.com/openai/v1/chat/completions", body,
            {"Content-Type": "application/json",
             "Authorization": f"Bearer {os.environ['GROQ_API_KEY']}"})
        with urllib.request.urlopen(req, timeout=self.timeout) as f:
            txt = json.loads(f.read())["choices"][0]["message"]["content"]
            return self._coerce(json.loads(txt))

    def _offline(self, d):
        if not d.breached:
            return {"diagnosis": _ML_ONLY[0], "action": _ML_ONLY[1]}
        causes, actions = [], []
        for sig, dirn, _v in d.breached:          # ALL breaches, not just the first
            cause, action = _KB.get((sig, dirn), _ML_ONLY)
            if cause not in causes:
                causes.append(cause)
                actions.append(action)
        return {"diagnosis": " ".join(causes), "action": " ".join(actions)}

    @staticmethod
    def _coerce(obj):
        return {
            "diagnosis": str(obj.get("diagnosis", "")).strip() or "Anomaly detected.",
            "action": str(obj.get("action", "")).strip() or "Inspect the flagged equipment.",
        }