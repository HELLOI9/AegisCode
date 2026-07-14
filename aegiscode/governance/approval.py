# aegiscode/governance/approval.py
import hashlib, json, uuid
from dataclasses import dataclass, field
from enum import Enum


class ApprovalState(str, Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"
    SUPERSEDED = "SUPERSEDED"


class SupersededError(RuntimeError): ...


def fingerprint(action) -> str:
    canon = json.dumps({"tool": action.tool, "arguments": action.arguments}, sort_keys=True)
    return hashlib.sha256(canon.encode()).hexdigest()


def validate_resume(approved_fp: str, current_action) -> None:
    if fingerprint(current_action) != approved_fp:
        raise SupersededError("action changed since approval")


@dataclass
class ApprovalRequest:
    approval_id: str
    task_id: str
    step_index: int
    action_snapshot: dict
    action_fingerprint: str
    rule_id: str
    reason: str
    risk_explanation: str
    state: ApprovalState = ApprovalState.PENDING


class ApprovalStore:
    def __init__(self):
        self._reqs: dict[str, ApprovalRequest] = {}
        self._remembered: set[tuple[str, str]] = set()

    def create(self, task_id, step_index, snapshot, fp, rule_id, reason, risk) -> ApprovalRequest:
        req = ApprovalRequest(
            approval_id=str(uuid.uuid4()),
            task_id=task_id,
            step_index=step_index,
            action_snapshot=snapshot,
            action_fingerprint=fp,
            rule_id=rule_id,
            reason=reason,
            risk_explanation=risk,
        )
        self._reqs[req.approval_id] = req
        return req

    def get(self, approval_id: str) -> ApprovalRequest:
        return self._reqs[approval_id]

    def decide(self, approval_id: str, approved: bool) -> ApprovalState:
        self._reqs[approval_id].state = ApprovalState.APPROVED if approved else ApprovalState.REJECTED
        return self._reqs[approval_id].state

    def remember(self, task_id: str, fp: str) -> None:
        self._remembered.add((task_id, fp))

    def check_remembered(self, task_id: str, fp: str) -> bool:
        return (task_id, fp) in self._remembered
