from aegiscode.llm.base import LLMClient
from aegiscode.llm.openai_adapter import _real_post

class AnthropicAdapter(LLMClient):
    def __init__(self, model, api_key, http_post=_real_post):
        self.model, self.api_key, self._post = model, api_key, http_post
    def complete(self, messages):
        system = "\n".join(m["content"] for m in messages if m["role"] == "system")
        convo = [m for m in messages if m["role"] != "system"]
        r = self._post("https://api.anthropic.com/v1/messages",
            {"x-api-key": self.api_key, "anthropic-version": "2023-06-01"},
            {"model": self.model, "max_tokens": 4096, "system": system, "messages": convo})
        return "".join(b["text"] for b in r["content"] if b.get("type") == "text")
