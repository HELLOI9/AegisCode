"use strict";
// AegisCode native WebUI — vanilla JS, no imports, no build step.
// Consumes the 8 REST endpoints served by the same FastAPI app.

(function () {
  const TERMINAL = ["COMPLETED", "FAILED", "CANCELLED"];
  const POLL_MS = 1500;

  let taskId = null;
  let lastEventId = 0; // watermark: highest event_id rendered
  let pollTimer = null;

  // --- DOM handles -------------------------------------------------------
  const $ = (id) => document.getElementById(id);
  const startForm = $("start-form");
  const startBtn = $("start-btn");
  const taskIdLabel = $("task-id-label");
  const stateSection = $("state-section");
  const stateBanner = $("state-banner");
  const stateDetail = $("state-detail");
  const approvalsSection = $("approvals-section");
  const approvalsList = $("approvals-list");
  const eventsSection = $("events-section");
  const eventsList = $("events-list");
  const auditSection = $("audit-section");
  const verifyBtn = $("verify-btn");
  const chainValid = $("chain-valid");
  const credStatus = $("cred-status");

  // --- small helpers -----------------------------------------------------
  async function getJSON(url) {
    const r = await fetch(url);
    if (!r.ok) throw new Error("HTTP " + r.status + " for " + url);
    return r.json();
  }

  async function postJSON(url, body) {
    const r = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body || {}),
    });
    if (!r.ok) throw new Error("HTTP " + r.status + " for " + url);
    return r.json();
  }

  function el(tag, cls, text) {
    const n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text != null) n.textContent = text;
    return n;
  }

  function parsePayload(raw) {
    if (raw == null) return {};
    if (typeof raw === "object") return raw;
    try {
      return JSON.parse(raw);
    } catch (e) {
      return { _raw: String(raw) };
    }
  }

  // --- rendering ---------------------------------------------------------
  function renderState(task) {
    const state = (task.state || "").toUpperCase();
    stateSection.classList.remove("hidden");
    stateBanner.textContent = state || "—";
    stateBanner.className = "banner " + state.toLowerCase();
    const bits = [];
    if (task.termination_reason) bits.push("reason: " + task.termination_reason);
    if (task.step_count != null) bits.push("steps: " + task.step_count);
    stateDetail.textContent = bits.join("  ·  ");
  }

  function renderDiff(container, payload) {
    // Show a file diff if the event payload carries one.
    const diffText = payload.diff || payload.file_diff || null;
    if (!diffText) return;
    const box = el("div", "diff");
    const path = payload.path || payload.file || payload.file_path;
    if (path) box.appendChild(el("div", "step", path));
    String(diffText)
      .split("\n")
      .forEach((line) => {
        let cls = "";
        if (line.startsWith("+")) cls = "add";
        else if (line.startsWith("-")) cls = "del";
        box.appendChild(el("div", cls, line));
      });
    container.appendChild(box);
  }

  function renderEvent(ev) {
    const payload = parsePayload(ev.payload_json);
    const node = el("div", "event");
    const head = el("div");
    head.appendChild(el("span", "type", ev.event_type || "EVENT"));
    head.appendChild(el("span", "step", "#" + ev.event_id + " · step " + ev.step_index));
    node.appendChild(head);

    const pre = el("pre");
    pre.textContent = JSON.stringify(payload, null, 2);
    node.appendChild(pre);

    renderDiff(node, payload);

    eventsList.appendChild(node);
  }

  function renderApprovals(rows) {
    const pending = (rows || []).filter((a) => (a.state || "").toUpperCase() === "PENDING");
    if (pending.length === 0) {
      approvalsSection.classList.add("hidden");
      approvalsList.innerHTML = "";
      return;
    }
    approvalsSection.classList.remove("hidden");
    approvalsList.innerHTML = "";
    pending.forEach((a) => {
      const box = el("div", "approval");
      box.appendChild(el("div", "type", a.reason || "Approval required"));
      if (a.risk_explanation) box.appendChild(el("div", "muted", a.risk_explanation));
      const snap = parsePayload(a.action_snapshot_json);
      const pre = el("pre");
      pre.textContent = JSON.stringify(snap, null, 2);
      box.appendChild(pre);

      const buttons = el("div", "buttons");
      const approve = el("button", "approve", "Approve");
      const reject = el("button", "reject", "Reject");
      approve.onclick = () => decide(a.approval_id, true);
      reject.onclick = () => decide(a.approval_id, false);
      buttons.appendChild(approve);
      buttons.appendChild(reject);
      box.appendChild(buttons);
      approvalsList.appendChild(box);
    });
  }

  async function decide(approvalId, approved) {
    try {
      await postJSON("/approvals/" + approvalId + "/decision", { approved: approved });
    } catch (e) {
      /* transient; next poll re-renders */
    }
    poll();
  }

  // --- polling loop ------------------------------------------------------
  async function poll() {
    if (!taskId) return;
    try {
      const events = await getJSON("/tasks/" + taskId + "/events?since=" + lastEventId);
      events.forEach((ev) => {
        renderEvent(ev);
        if (ev.event_id > lastEventId) lastEventId = ev.event_id;
      });

      const approvals = await getJSON("/tasks/" + taskId + "/approvals");
      renderApprovals(approvals);

      const task = await getJSON("/tasks/" + taskId);
      renderState(task);

      if (TERMINAL.indexOf((task.state || "").toUpperCase()) !== -1) {
        stopPolling();
      }
    } catch (e) {
      /* keep polling; a later cycle recovers */
    }
  }

  function startPolling() {
    stopPolling();
    poll();
    pollTimer = setInterval(poll, POLL_MS);
  }

  function stopPolling() {
    if (pollTimer !== null) {
      clearInterval(pollTimer);
      pollTimer = null;
    }
  }

  // --- audit -------------------------------------------------------------
  async function verifyChain() {
    if (!taskId) return;
    chainValid.textContent = "checking…";
    try {
      const audit = await getJSON("/tasks/" + taskId + "/audit");
      chainValid.textContent = "chain_valid: " + String(audit.chain_valid);
    } catch (e) {
      chainValid.textContent = "chain check failed";
    }
  }

  // --- credential status indicator --------------------------------------
  async function loadCredentialStatus() {
    try {
      const s = await getJSON("/credentials/status");
      if (s.configured) {
        credStatus.textContent = "credentials: " + (s.masked || "configured");
        credStatus.classList.add("configured");
      } else {
        credStatus.textContent = "credentials: not configured";
      }
    } catch (e) {
      credStatus.textContent = "credentials: unknown";
    }
  }

  // --- start handler -----------------------------------------------------
  startForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    const workspace = $("workspace").value.trim();
    const description = $("description").value.trim();
    if (!workspace || !description) return;

    startBtn.disabled = true;
    eventsList.innerHTML = "";
    approvalsList.innerHTML = "";
    lastEventId = 0;
    try {
      const res = await postJSON("/tasks", { workspace: workspace, description: description });
      taskId = res.task_id;
      taskIdLabel.textContent = "task: " + taskId;
      eventsSection.classList.remove("hidden");
      auditSection.classList.remove("hidden");
      chainValid.textContent = "";
      startPolling();
    } catch (err) {
      taskIdLabel.textContent = "failed to start: " + err.message;
    } finally {
      startBtn.disabled = false;
    }
  });

  verifyBtn.addEventListener("click", verifyChain);

  loadCredentialStatus();
})();
