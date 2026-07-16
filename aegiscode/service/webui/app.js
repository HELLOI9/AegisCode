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
    // Show the file-change ("diff") panel when the harness reports which files
    // a tool touched. The harness emits payload.changed_files on TOOL_EXECUTED
    // events (SPEC §13 mandatory diff view; textual snapshot diffs are v2).
    const changed = payload.changed_files;
    if (!Array.isArray(changed) || changed.length === 0) return;
    const box = el("div", "diff");
    box.appendChild(el("div", "step", "changed files (" + changed.length + ")"));
    changed.forEach((path) => {
      // CRITICAL: workspace paths are attacker-influenced. el() sets the value
      // via textContent, so paths are never interpreted as HTML.
      box.appendChild(el("div", "add", String(path)));
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

  // ===================== Preset MockLLM demos ============================
  // Independent poll state from the standard task view above, so a running
  // demo never collides with a manually-started task.
  const DEMO_POLL_MS = 1200;
  let demoRunId = null;
  let demoPollTimer = null;
  let currentDemoId = null;

  const demosSection = $("demos-section");
  const demosList = $("demos-list");
  const demoRun = $("demo-run");

  function shortType(t) {
    if (!t) return "EVENT";
    const s = String(t);
    const i = s.lastIndexOf(".");
    return i >= 0 ? s.slice(i + 1) : s;
  }

  async function loadDemos() {
    let demos;
    try {
      demos = await getJSON("/demos");
    } catch (e) {
      demosList.textContent = "无法加载演示列表 (unavailable): " + e.message;
      return;
    }
    demosList.innerHTML = "";
    demos.forEach((d) => {
      const card = el("div", "demo-card");
      card.appendChild(el("div", "demo-title", d.title || d.id));
      card.appendChild(el("div", "demo-desc muted", d.description || ""));
      if (d.learning_objective) {
        card.appendChild(el("div", "demo-obj muted", "目标 · " + d.learning_objective));
      }
      if (d.interactive_approval) {
        card.appendChild(el("div", "demo-badge", "需人工审批 · interactive approval"));
      }
      const btn = el("button", "demo-run-btn", "运行演示");
      btn.onclick = () => runDemo(d.id, d.title || d.id, btn);
      card.appendChild(btn);
      demosList.appendChild(card);
    });
  }
  function stopDemoPolling() {
    if (demoPollTimer !== null) {
      clearInterval(demoPollTimer);
      demoPollTimer = null;
    }
  }

  async function runDemo(demoId, title, btn) {
    // Disable every card's Run button while a demo is in flight (avoid double-fire).
    demosList.querySelectorAll("button.demo-run-btn").forEach((b) => (b.disabled = true));
    currentDemoId = demoId;
    demoRun.classList.remove("hidden");
    demoRun.innerHTML = "";
    demoRun.appendChild(el("div", "demo-run-title", title));
    const status = el("div", "demo-status");
    status.id = "demo-status";
    demoRun.appendChild(status);
    setDemoStatus("准备中", "prep", "准备中 · preparing");
    try {
      const res = await postJSON("/demos/" + encodeURIComponent(demoId) + "/run", {});
      demoRunId = res.run_id;
    } catch (e) {
      setDemoStatus("失败", "fail", "启动失败 · " + e.message);
      demosList.querySelectorAll("button.demo-run-btn").forEach((b) => (b.disabled = false));
      return;
    }
    // Timeline + approval + acceptance + raw-events containers.
    ["demo-timeline", "demo-approvals", "demo-acceptance", "demo-raw"].forEach((cls) => {
      const box = el("div", cls);
      box.id = cls;
      demoRun.appendChild(box);
    });
    startDemoPolling();
  }

  function startDemoPolling() {
    stopDemoPolling();
    pollDemo();
    demoPollTimer = setInterval(pollDemo, DEMO_POLL_MS);
  }

  function setDemoStatus(label, kind, longText) {
    const status = $("demo-status");
    if (!status) return;
    status.className = "demo-status " + kind;
    status.innerHTML = "";
    // Text + icon (never color alone) for accessibility.
    const icon = el("span", "status-icon");
    const glyph = { prep: "…", run: "⏳", wait: "⏸", ok: "✓", fail: "✗", cancel: "⊘" }[kind] || "•";
    icon.textContent = glyph;
    icon.setAttribute("aria-hidden", "true");
    status.appendChild(icon);
    status.appendChild(el("span", "status-text", longText || label));
    status.setAttribute("role", "status");
  }
  async function pollDemo() {
    if (!demoRunId) return;
    try {
      const run = await getJSON("/demos/runs/" + demoRunId);
      const approvals = await getJSON("/tasks/" + demoRunId + "/approvals");
      const pending = (approvals || []).filter(
        (a) => (a.state || "").toUpperCase() === "PENDING"
      );
      renderDemoTimeline(run.steps || []);
      renderDemoApprovals(pending);
      renderAcceptance(run.acceptance || [], run.state, run.done);
      await renderDemoRawEvents();

      // Status precedence: pending approval > running > terminal verdict.
      if (pending.length > 0) {
        setDemoStatus("等待审批", "wait", "等待审批 · awaiting approval");
      } else if (!run.done) {
        setDemoStatus("运行中", "run", "运行中 · running (round " + (run.steps ? run.steps.length : 0) + ")");
      }
      if (run.done) {
        stopDemoPolling();
        demosList.querySelectorAll("button.demo-run-btn").forEach((b) => (b.disabled = false));
        addRerunButton();
      }
    } catch (e) {
      /* transient; a later cycle recovers */
    }
  }

  function renderDemoTimeline(steps) {
    const box = $("demo-timeline");
    if (!box) return;
    box.innerHTML = "";
    box.appendChild(el("div", "demo-sub", "分步时间线 · step timeline"));
    if (steps.length === 0) {
      box.appendChild(el("div", "muted", "尚无步骤 · no steps yet"));
      return;
    }
    steps.forEach((s, i) => {
      const row = el("div", "step-row");
      row.appendChild(el("span", "step-idx", "#" + (i + 1)));
      if (s.tool) row.appendChild(el("span", "step-tool", String(s.tool)));
      if (s.governance_decision)
        row.appendChild(el("span", "gov-tag", "治理 " + String(s.governance_decision)));
      // Whether the tool actually executed.
      const ran = s.tool_status ? "执行:" + String(s.tool_status) : "工具未执行";
      row.appendChild(el("span", "exec-tag", ran));
      if (s.approval_state)
        row.appendChild(el("span", "appr-tag", "审批 " + String(s.approval_state)));
      if (s.feedback_category)
        row.appendChild(el("span", "fb-tag", "反馈 " + String(s.feedback_category)));
      box.appendChild(row);
    });
  }

  function renderDemoApprovals(pending) {
    const box = $("demo-approvals");
    if (!box) return;
    box.innerHTML = "";
    if (pending.length === 0) return;
    pending.forEach((a) => {
      const card = el("div", "approval");
      card.appendChild(el("div", "type", a.reason || "需要审批 · approval required"));
      if (a.risk_explanation) card.appendChild(el("div", "muted", a.risk_explanation));
      const snap = parsePayload(a.action_snapshot_json);
      const pre = el("pre");
      pre.textContent = JSON.stringify(snap, null, 2);
      card.appendChild(pre);
      const buttons = el("div", "buttons");
      const ok = el("button", "approve", "批准原动作 · Approve");
      const no = el("button", "reject", "拒绝 · Reject");
      ok.onclick = () => decideDemo(a.approval_id, true);
      no.onclick = () => decideDemo(a.approval_id, false);
      buttons.appendChild(ok);
      buttons.appendChild(no);
      card.appendChild(buttons);
      box.appendChild(card);
    });
  }

  async function decideDemo(approvalId, approved) {
    try {
      await postJSON("/approvals/" + approvalId + "/decision", { approved: approved });
    } catch (e) {
      /* transient; next poll re-renders */
    }
    pollDemo();
  }
  function renderAcceptance(acceptance, state, done) {
    const box = $("demo-acceptance");
    if (!box) return;
    box.innerHTML = "";
    box.appendChild(el("div", "demo-sub", "验收摘要 · acceptance"));
    acceptance.forEach((c) => {
      const row = el("div", "acc-row " + (c.passed ? "acc-pass" : "acc-fail"));
      const icon = el("span", "status-icon");
      icon.textContent = c.passed ? "✓" : "✗";
      icon.setAttribute("aria-hidden", "true");
      row.appendChild(icon);
      row.appendChild(el("span", "acc-label", (c.label || c.key) + (c.passed ? " · PASS" : " · FAIL")));
      box.appendChild(row);
    });
    if (!done) return;
    // Success is defined by the scenario's acceptance conditions — the SAME
    // success_conditions `make demo` asserts — never by the harness terminal
    // state. dangerous-action-denial deliberately ends via MAX_STEPS (a
    // non-COMPLETED terminal state) on a fully-passing DENY-only run
    // (max_steps=1), so gating on that terminal state would render a correct
    // run as a failure. A failure still can NEVER be laundered into success:
    // the banner is green ONLY when every acceptance condition passed. A
    // user-initiated CANCELLED (with unmet conditions) is surfaced distinctly.
    const upState = (state || "").toUpperCase();
    const allPass = acceptance.length > 0 && acceptance.every((c) => c.passed === true);
    if (allPass) {
      setDemoStatus("成功", "ok", "演示成功 · all acceptance conditions passed");
    } else if (upState === "CANCELLED") {
      setDemoStatus("已取消", "cancel", "已取消 · cancelled");
    } else {
      const failed = acceptance.filter((c) => !c.passed).map((c) => c.key);
      setDemoStatus("失败", "fail", "演示失败 · failed" + (failed.length ? " (" + failed.join(", ") + ")" : ""));
    }
  }

  async function renderDemoRawEvents() {
    const box = $("demo-raw");
    if (!box) return;
    let events;
    try {
      events = await getJSON("/tasks/" + demoRunId + "/events?since=0");
    } catch (e) {
      return;
    }
    box.innerHTML = "";
    const details = document.createElement("details");
    details.className = "raw-events";
    const summary = document.createElement("summary");
    summary.textContent = "查看结构化事件 · view structured events (" + events.length + ")";
    details.appendChild(summary);
    events.forEach((ev) => {
      const line = el("div", "raw-line");
      line.appendChild(el("span", "type", shortType(ev.event_type)));
      line.appendChild(el("span", "step", "#" + ev.event_id + " · step " + ev.step_index));
      const pre = el("pre");
      pre.textContent = JSON.stringify(parsePayload(ev.payload_json), null, 2);
      line.appendChild(pre);
      details.appendChild(line);
    });
    box.appendChild(details);
  }

  function addRerunButton() {
    if (demoRun.querySelector(".demo-rerun")) return;
    const btn = el("button", "demo-rerun", "重新运行 · Re-run");
    btn.onclick = () => {
      const id = currentDemoId;
      const title = demoRun.querySelector(".demo-run-title");
      runDemo(id, title ? title.textContent : id, btn);
    };
    demoRun.appendChild(btn);
  }

  // --- demo mode UI adaptation -------------------------------------------
  (async function loadUiConfig() {
    try {
      const cfg = await getJSON("/ui-config");
      if (cfg.demo_mode) {
        const wsInput = $("workspace");
        wsInput.value = "demo";
        wsInput.disabled = true;
        wsInput.title = "Demo mode: workspace is fixed to the built-in sample project";
        wsInput.removeAttribute("required");
        // Reveal the preset-demo panel and load the catalog.
        if (demosSection) demosSection.classList.remove("hidden");
        loadDemos();
      }
    } catch (e) { /* non-critical */ }
  })();
})();
