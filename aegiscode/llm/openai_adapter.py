import urllib.request

from aegiscode.llm.base import LLMClient

# Bounded wall-clock timeout (seconds) for a single LLM HTTP round-trip. Without
# this, a hung connection blocks urlopen forever with no escape. Module-level
# constant (adapters have no config handle); shared by OpenAI + Anthropic via
# _real_post. Kept below the loop's wall_clock_timeout_sec so the socket gives up
# before the whole-run bound would.
HTTP_TIMEOUT_SEC = 60

def _real_post(url, headers, json):
    import json as _j
    req = urllib.request.Request(url, data=_j.dumps(json).encode(),
        headers={**headers, "Content-Type":"application/json"})
    with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT_SEC) as r:
        return _j.loads(r.read())

class OpenAIAdapter(LLMClient):
    def __init__(self, model, api_key, base_url=None, http_post=_real_post):
        self.model, self.api_key = model, api_key
        self.base_url = base_url or "https://api.openai.com/v1"
        self._post = http_post
    def complete(self, messages):
        r = self._post(f"{self.base_url}/chat/completions",
            {"Authorization": f"Bearer {self.api_key}"},
            {"model": self.model, "messages": messages})
        return r["choices"][0]["message"]["content"]
