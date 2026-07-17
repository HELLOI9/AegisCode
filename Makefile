# AegisCode — unified entry points for grading.
#
#   make test   → full automated test suite (unit + loop + governance + service…)
#   make demo   → the three deterministic mechanism demos (MockLLM, zero-network)
#
# Both run against the project's Python; see README for the venv / install steps.
# `make demo` exits non-zero if ANY demo's contract check fails (never swallows a
# failure), so CI can gate on it directly.
PY ?= python

.PHONY: test demo demo-guardrail demo-feedback demo-approval deploy-check e2e-real-llm

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

deploy-check:
ifndef DEPLOY_URL
	$(error DEPLOY_URL is required. Usage: make deploy-check DEPLOY_URL=https://...)
endif
	$(PY) scripts/deploy_check.py $(DEPLOY_URL)

# Human-triggered ONLY — real provider + network + API cost. Never a
# prerequisite of `test`, never run in CI (SPEC Appendix B.7).
e2e-real-llm:
	$(PY) scripts/e2e_real_llm.py
