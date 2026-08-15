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