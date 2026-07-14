def summarize_pytest(raw: str) -> str:
    lines = raw.splitlines()
    failed = [l for l in lines if "FAILED" in l or l.strip().startswith("E ")]
    tail = lines[-20:]
    return "\n".join(dict.fromkeys(failed + tail))
