# SDD Progress Ledger — AegisCode Milestone 7 (Distribution & Demos)

Branch: worktree-m7-distribution (base: main @ 7d42001, M0-M6 merged)
Chain: T30 Dockerfile ∥ T32 CI (both after infra) ; T31 four mechanism demos (after T23 + governance set).
Baseline: make test = 233 passed.
Impl/review sonnet; final whole-branch review opus. Each task: fresh subagent, strict TDD, two-stage review, Critical-blocks-commit, per-task PLAN+AGENT_LOG+ledger bookkeeping.
Note: PLAN specifies .gitlab-ci.yml (signed-off, decision #23 job name `unit-test`). Repo is GitHub — will add .github/workflows CI mirror as a value-add (noted in PR), keeping .gitlab-ci.yml PLAN-faithful.

## Tasks
Task 30: pending — Dockerfile + .dockerignore + tests/test_docker_build.py (no key baked, runtime CMD aegiscode serve)
Task 31: pending — demos/demo1..4 + tests/demos/test_demos.py + cli.py demo runs all four (§16.4)
Task 32: pending — .gitlab-ci.yml (unit-test + secret-scan + docker-build) + tests/test_ci_config.py

Task 30: complete (commits 1876545..342fa8e, review APPROVED-WITH-CAVEATS→fixed). Dockerfile (python:3.12-slim, editable install, EXPOSE 8000, exec-form CMD serve --host 0.0.0.0 --port 8000) + .dockerignore (excludes .env/.git/.venv/*.pem/*.key/*.db/tests/docs). Key NEVER baked in (runtime -e injection). Review Important: test-theater (assert "aegiscode serve" in df passed on a COMMENT, not CMD) → strengthened to assert exec-form CMD tokens (fails on CMD delete/reorder/shell-form). Strengthened .dockerignore test then caught real gap (committed file lacked *.pem/*.key despite report claim) → added. 237 total, ruff clean.
