# aegiscode/memory/context_builder.py
def summarize_step(step) -> str:
    return (f"[step tool={step.get('tool')} "
            f"decision={step.get('governance_decision')} "
            f"feedback={step.get('feedback_category')}]")

def _len(msgs): return sum(len(m["content"]) for m in msgs)

def build_context(system_prompt, tool_protocol, task, recent_steps,
                  last_feedback, memories, budget_chars):
    head = [{"role":"system","content": system_prompt + "\n" + tool_protocol},
            {"role":"user","content": f"TASK: {task}"}]
    mem_txt = "\n".join(f"- {m['key']}: {m['value']}" for m in memories)
    tail = []
    if last_feedback: tail.append({"role":"user","content": "FEEDBACK:\n"+last_feedback})   # tier 4 first
    if mem_txt: tail.append({"role":"system","content": "MEMORY:\n"+mem_txt})               # tier 5 after
    # recent steps newest-last; summarize oldest first when over budget
    detailed = [{"role":"assistant","content":
                 f"step {i}: {s.get('tool')} -> {s.get('feedback_category')}\n{s.get('detail','')}"}
                for i, s in enumerate(recent_steps)]
    msgs = head + detailed + tail
    idx = 0
    while _len(msgs) > budget_chars and idx < len(detailed):
        detailed[idx] = {"role":"assistant","content": summarize_step(recent_steps[idx])}
        msgs = head + detailed + tail
        idx += 1
    return msgs
