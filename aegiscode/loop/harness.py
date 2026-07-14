# aegiscode/loop/harness.py
"""HarnessCore: self-written while-loop agent that wires all milestones.

No external agent SDK or framework — just a plain Python while-loop composing:
  LLMClient, parser, Dispatcher, classify, ProgressTracker,
  fingerprint, AuditLog, build_context, decide_termination.
"""
from __future__ import annotations

from aegiscode.protocol.parser import parse_action, ActionParseError
from aegiscode.governance.decision import Decision
from aegiscode.feedback.classifier import classify, ProgressTracker
from aegiscode.governance.approval import fingerprint
from aegiscode.audit.events import EventType
from aegiscode.loop.termination import decide_termination, LoopCounters, TerminationReason
from aegiscode.memory.context_builder import build_context


class HarnessCore:
    """Main loop agent harness.  Call run(task) → TerminationReason."""

    def __init__(
        self,
        llm,
        dispatcher,
        audit,
        config,
        ctx,
        final_verifier,
        approval_resolver=None,
        cancel_check=None,
    ):
        self.llm = llm
        self.dispatcher = dispatcher
        self.audit = audit
        self.config = config
        self.ctx = ctx
        self.final_verifier = final_verifier
        self.approval_resolver = approval_resolver
        # Optional cooperative-cancellation hook: () -> bool. When it returns
        # True at the top of a turn, the loop stops with CANCELLED. This is the
        # seam T26 ApplicationService uses to cancel a running task.
        self.cancel_check = cancel_check

    # ------------------------------------------------------------------ #
    # Public entry point                                                   #
    # ------------------------------------------------------------------ #

    def run(self, task_description: str) -> TerminationReason:
        """Execute the agent loop for *task_description*.

        Returns a TerminationReason once a terminal condition is met.
        """
        c = LoopCounters(step=0, consecutive_failures=0, invalid_actions=0, no_progress_hits=0)
        last_feedback = ""
        recent_steps: list[dict] = []
        tracker = ProgressTracker(window=self.config.limits.no_progress_repeat_limit)
        limits = self.config.limits.model_dump()

        while True:
            # ---- pre-step termination check ----
            reason = decide_termination(c, limits)
            if reason is not None:
                self._audit_term(c, reason)
                return reason

            # ---- cooperative cancellation ----
            if self.cancel_check is not None and self.cancel_check():
                self._audit_term(c, TerminationReason.CANCELLED)
                return TerminationReason.CANCELLED

            # ---- per-turn body (fail-safe: an unexpected exception must
            # never crash the caller; audit INTERNAL_ERROR and stop) ----
            try:
                # ---- build context & call LLM ----
                messages = self._build(task_description, recent_steps, last_feedback)
                try:
                    raw_text = self._complete_with_retry(messages)
                except Exception as exc:  # noqa: BLE001
                    reason = TerminationReason.LLM_ERROR
                    self._audit_term(c, reason)
                    return reason

                # ---- parse action ----
                try:
                    action = parse_action(raw_text)
                except ActionParseError as exc:
                    c = LoopCounters(
                        step=c.step,
                        consecutive_failures=c.consecutive_failures,
                        invalid_actions=c.invalid_actions + 1,
                        no_progress_hits=c.no_progress_hits,
                    )
                    last_feedback = f"PARSE_ERROR: {exc}"
                    self.audit.append(
                        self.ctx.task_id, c.step, EventType.ACTION_PROPOSED,
                        {"raw": raw_text, "error": str(exc)},
                    )
                    self.audit.append(
                        self.ctx.task_id, c.step, EventType.FEEDBACK,
                        {"category": "INVALID_ACTION", "detail": last_feedback},
                    )
                    continue

                # Reset invalid_actions on a successful parse
                c = LoopCounters(
                    step=c.step,
                    consecutive_failures=c.consecutive_failures,
                    invalid_actions=0,
                    no_progress_hits=c.no_progress_hits,
                )

                self.audit.append(
                    self.ctx.task_id, c.step, EventType.ACTION_PROPOSED,
                    {"tool": action.tool, "arguments": action.arguments},
                )

                # ---- dispatch through governance ----
                verdict, result = self.dispatcher.dispatch(action, self.ctx)

                self.audit.append(
                    self.ctx.task_id, c.step, EventType.GOVERNANCE_DECISION,
                    {
                        "tool": action.tool,
                        "decision": verdict.decision.value,
                        "rule": verdict.rule_id,
                        "reason": verdict.reason,
                    },
                )

                # ---- handle REQUIRE_APPROVAL ----
                if verdict.decision == Decision.REQUIRE_APPROVAL:
                    if self.approval_resolver is not None:
                        approved = self.approval_resolver(action, verdict)
                    else:
                        approved = False

                    if approved:
                        result = self.dispatcher.execute_approved(action, self.ctx)
                        self.audit.append(
                            self.ctx.task_id, c.step, EventType.APPROVAL_DECIDED,
                            {"tool": action.tool, "state": "APPROVED"},
                        )
                    else:
                        # Not approved — treat as failure
                        self.audit.append(
                            self.ctx.task_id, c.step, EventType.APPROVAL_DECIDED,
                            {"tool": action.tool, "state": "REJECTED"},
                        )
                        last_feedback = "APPROVAL_REJECTED: action was not approved"
                        c = LoopCounters(
                            step=c.step + 1,
                            consecutive_failures=c.consecutive_failures + 1,
                            invalid_actions=c.invalid_actions,
                            no_progress_hits=c.no_progress_hits,
                        )
                        recent_steps = self._append_step(recent_steps, action, verdict, "APPROVAL_REJECTED", "", limits)
                        continue

                # ---- handle DENY ----
                # The dispatcher already refused to execute the tool. Do NOT emit a
                # TOOL_EXECUTED event (nothing ran); feed back POLICY_DENIED, count it
                # as a consecutive failure, advance the step, and continue (no stop).
                if verdict.decision == Decision.DENY:
                    last_feedback = self._format_feedback("POLICY_DENIED", result)
                    self.audit.append(
                        self.ctx.task_id, c.step, EventType.FEEDBACK,
                        {"category": "POLICY_DENIED", "detail": last_feedback},
                    )
                    c = LoopCounters(
                        step=c.step + 1,
                        consecutive_failures=c.consecutive_failures + 1,
                        invalid_actions=c.invalid_actions,
                        no_progress_hits=c.no_progress_hits,
                    )
                    recent_steps = self._append_step(
                        recent_steps, action, verdict, "POLICY_DENIED",
                        result.summary if result else "", limits,
                    )
                    continue

                # At this point result is not None (ALLOW/ALLOW_WITH_AUDIT produce one)
                assert result is not None  # REQUIRE_APPROVAL without approval was handled above

                self.audit.append(
                    self.ctx.task_id, c.step, EventType.TOOL_EXECUTED,
                    {"tool": action.tool, "status": result.status},
                )

                # ---- finish tool ----
                # Only COMPLETED terminates. If final verification fails, FINISH_REJECTED
                # is a FEEDBACK category (not a return) — the loop continues and may later
                # hit MAX_STEPS / MAX_CONSECUTIVE_FAILURES.
                if action.tool == "finish":
                    if self.final_verifier():
                        self._audit_term(c, TerminationReason.COMPLETED)
                        return TerminationReason.COMPLETED
                    last_feedback = "FINISH_REJECTED: final verification failed"
                    self.audit.append(
                        self.ctx.task_id, c.step, EventType.FEEDBACK,
                        {"category": "FINISH_REJECTED", "detail": last_feedback},
                    )
                    c = LoopCounters(
                        step=c.step + 1,
                        consecutive_failures=c.consecutive_failures + 1,
                        invalid_actions=c.invalid_actions,
                        no_progress_hits=c.no_progress_hits,
                    )
                    continue

                # ---- classify result for feedback ----
                failure_cat = classify(result)

                # ---- progress tracking ----
                fp = fingerprint(action)
                no_progress = tracker.seen(fp)

                if no_progress:
                    c = LoopCounters(
                        step=c.step + 1,
                        consecutive_failures=c.consecutive_failures,
                        invalid_actions=c.invalid_actions,
                        no_progress_hits=c.no_progress_hits + 1,
                    )
                    last_feedback = "NO_PROGRESS: repeated action detected"
                elif failure_cat is not None:
                    c = LoopCounters(
                        step=c.step + 1,
                        consecutive_failures=c.consecutive_failures + 1,
                        invalid_actions=c.invalid_actions,
                        no_progress_hits=c.no_progress_hits,
                    )
                    last_feedback = self._format_feedback(failure_cat, result)
                else:
                    # success
                    c = LoopCounters(
                        step=c.step + 1,
                        consecutive_failures=0,
                        invalid_actions=c.invalid_actions,
                        no_progress_hits=c.no_progress_hits,
                    )
                    last_feedback = ""

                self.audit.append(
                    self.ctx.task_id, c.step, EventType.FEEDBACK,
                    {"category": failure_cat or "SUCCESS", "detail": last_feedback},
                )

                recent_steps = self._append_step(
                    recent_steps, action, verdict, failure_cat, result.summary if result else "", limits
                )
            except Exception:  # noqa: BLE001
                self._audit_term(c, TerminationReason.INTERNAL_ERROR)
                return TerminationReason.INTERNAL_ERROR

    # ------------------------------------------------------------------ #
    # Private helpers                                                      #
    # ------------------------------------------------------------------ #

    def _build(self, task: str, recent_steps: list[dict], last_feedback: str) -> list[dict]:
        """Construct the message list to send to the LLM."""
        return build_context(
            system_prompt="",
            tool_protocol="",
            task=task,
            recent_steps=recent_steps,
            last_feedback=last_feedback,
            # TODO(memory-integration): retrieve project memories and honor
            # is_governance_usable() per row (M3 carry-in) before feeding to context.
            memories=[],
            budget_chars=self.config.memory.context_budget_chars,
        )

    def _complete_with_retry(self, messages: list[dict]) -> str:
        """Call the LLM with up to *llm_max_retries* attempts on transient errors."""
        retries = self.config.limits.llm_max_retries
        last_exc: Exception | None = None
        for attempt in range(retries):
            try:
                return self.llm.complete(messages)
            except Exception as exc:  # noqa: BLE001
                last_exc = exc
        raise RuntimeError(f"LLM failed after {retries} attempts") from last_exc

    def _audit_term(self, c: LoopCounters, reason: TerminationReason) -> None:
        """Append a TERMINATION event to the audit log."""
        self.audit.append(
            self.ctx.task_id,
            c.step,
            EventType.TERMINATION,
            {"reason": reason.value},
        )

    @staticmethod
    def _format_feedback(category: str, result) -> str:
        """Build a human-readable feedback string for the LLM."""
        detail = getattr(result, "detail_for_llm", "") or ""
        if detail:
            return f"{category}: {detail}"
        return f"{category}: {result.summary}"

    @staticmethod
    def _append_step(
        recent_steps: list[dict],
        action,
        verdict,
        failure_cat: str | None,
        summary: str,
        limits: dict,
    ) -> list[dict]:
        """Append a step record, trimming to the last max_steps entries."""
        step_record = {
            "tool": action.tool,
            "governance_decision": verdict.decision.value,
            "feedback_category": failure_cat or "SUCCESS",
            "detail": summary,
        }
        updated = recent_steps + [step_record]
        # Keep only the most recent window (no_progress_repeat_limit is small; use max_steps)
        max_keep = limits.get("max_steps", 25)
        return updated[-max_keep:]
