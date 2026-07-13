from aegiscode.llm.base import LLMClient

def _real_post(url, headers, json):
    import urllib.request, json as _j
    req = urllib.request.Request(url, data=_j.dumps(json).encode(),
        headers={**headers, "Content-Type":"application/json"})
    with urllib.request.urlopen(req) as r:
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
