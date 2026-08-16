# AI Usage Log

Evidence for the assignment's AI Tool Usage criterion (60%).
Every AI interaction during this build, and what I verified.

---

## [Day 0] Environment setup
**Tool:** none
**What I did:** venv, dependencies, git, Ollama + llama3.2
**Verified by:** python -c "import pandas, sklearn, rich" -> ok
                 Ollama responding at localhost:11434
                 
## [Day 1] Data generator (aider + Groq llama-3.3-70b)
**Prompt:** schema, operating envelopes, 1-3 channel corruption, injected
NaNs and duplicate rows.
**Verified by:** python check_data.py

**Three defects found by verification, not code review:**
1. 8/41 rows labelled abnormal breached no threshold - would have created
   guaranteed false negatives and capped recall at ~80%
2. AI produced a syntax error (duplicated loop header) on a 3-part edit -
   caught with `python -c "import ast; ast.parse(...)"` before running
3. Root cause: Gaussian noise was applied AFTER corrupting a channel, pulling
   boundary values back into the normal band

**Fix:** corrupted channels now drawn from ranges with a safety margin and
excluded from noise. Added a validate() invariant that raises at generation
time, so this class of bug cannot silently return.
**Result:** rows with NO breach: 0

## [Day 2] Preprocessing - took over from the agent
**Attempts:** 3 agent iterations, 3 different runtime errors:
  1. interpolate() on string 'label' column -> TypeError
  2. set_index('timestamp') on a slice that no longer had it -> KeyError
  3. StandardScaler fed the label column -> ValueError
**Decision:** wrote it manually. The model kept mis-ordering the column
selection, and describing the fix a third time was slower than writing it.
**Lesson:** agentic loops are productive for scoped, additive changes; they
degrade on edits with ordering dependencies across several lines. Knowing when
to take over is part of using the tool well.

## [Day 3] LLM Backend package generated with llm offline fallback mechanism and llm online actionable insights 
**Run 2 (same rows, different output - LLM confirmed non-deterministic):**
  - multi-breach row 1: correct, covered both faults
  - row 2 (temp LOW + vibration high): "Cooling system malfunction" - factually
    wrong direction, and vibration ignored
  - row 3 (three breaches): "Anomalous sensor reading detected / investigate
    possible causes" - named none of the three faults
**Conclusion:** llama3.2 is unreliable for diagnostic completeness and can
invert the fault direction. The deterministic KB never does either. This is
the empirical basis for keeping detection deterministic and using the LLM only
for phrasing.

## [Day 4] Imputation manufactured false positives
**Finding:** rule-only flags 35 rows against 33 true anomalies. The 2 extra
rows are labelled normal in the source data but breach thresholds AFTER
cleaning.
**Cause:** time-interpolation across a missing value adjacent to an abnormal
row produces an imputed value outside the normal band - a reading that never
actually occurred.
**Not fixed, deliberately:** it is a real property of interpolation, and the
alternative  is what the streaming path would use anyway.
**Implication:** preprocessing choices can create anomalies. Cleaning is not
a neutral step.