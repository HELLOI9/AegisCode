# AegisCode — unified entry points for grading.
#
#   make test   → full automated test suite (unit + loop + governance + service…)
#   make demo   → the three deterministic mechanism demos (MockLLM, zero-network)
#
# Both run against the project's Python; see README for the venv / install steps.
# `make demo` exits non-zero if ANY demo's contract check fails (never swallows a
# failure), so CI can gate on it directly.
PY ?= python

.PHONY: test demo demo-guardrail demo-feedback demo-approval

test:
	pytest -q

demo:
	$(PY) -m demos.run_demos

# Individual mechanism demos (optional; `make demo` runs all three).
demo-guardrail:
	$(PY) -m demos.run_demos --only guardrail

demo-feedback:
	$(PY) -m demos.run_demos --only feedback

demo-approval:
	$(PY) -m demos.run_demos --only approval
