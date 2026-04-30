"""Thin LLM abstraction. Hosted open-source providers, no local install needed.

Supported providers (set VOICEFUL_LLM_PROVIDER):
- huggingface: HF Inference API. Needs HF_TOKEN. Free tier available.
- groq: Groq Cloud (fast Llama 3.x, Mixtral). Needs GROQ_API_KEY. Free tier.
- openrouter: OpenRouter. Needs OPENROUTER_API_KEY. Many open models.
- together: Together AI. Needs TOGETHER_API_KEY.
- anthropic: Anthropic (closed source, alt only). Needs ANTHROPIC_API_KEY.
- dummy: offline stub for tests.
"""
from __future__ import annotations

import json
import logging
import os
import re
import time
import urllib.error
import urllib.request
from typing import Protocol

log = logging.getLogger(__name__)


class LLMClient(Protocol):
    def complete(self, system: str, user: str, max_tokens: int = 1024) -> str: ...


_UA = "voiceful/0.1 (+https://github.com/voiceful)"


def _parse_retry_after(body_text: str, default: float = 8.0) -> float:
    m = re.search(r"try again in (\d+(?:\.\d+)?)s", body_text)
    if m:
        return float(m.group(1)) + 0.5
    return default


def _http_post_json(url: str, headers: dict, body: dict, timeout: int = 120, max_retries: int = 6) -> dict:
    data = json.dumps(body).encode("utf-8")
    last_err = None
    for attempt in range(max_retries):
        req = urllib.request.Request(
            url,
            data=data,
            headers={
                "Content-Type": "application/json",
                "User-Agent": _UA,
                "Accept": "application/json",
                **headers,
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            body_text = e.read().decode("utf-8", errors="ignore")
            last_err = RuntimeError(f"HTTP {e.code} from {url}: {body_text[:500]}")
            if e.code == 429:
                wait = _parse_retry_after(body_text, default=2 ** attempt * 4)
                log.warning("Rate limited (attempt %d/%d). Sleeping %.1fs.", attempt + 1, max_retries, wait)
                time.sleep(wait)
                continue
            if 500 <= e.code < 600 and attempt < max_retries - 1:
                wait = 2 ** attempt
                log.warning("Server error %d (attempt %d/%d). Sleeping %ds.", e.code, attempt + 1, max_retries, wait)
                time.sleep(wait)
                continue
            raise last_err
        except urllib.error.URLError as e:
            last_err = RuntimeError(f"Network error to {url}: {e}")
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)
                continue
            raise last_err
    raise last_err  # type: ignore


class HuggingFaceClient:
    """Hugging Face Inference API. Default model: Mistral 7B Instruct.

    Get a token at https://huggingface.co/settings/tokens (free).
    Set HF_TOKEN env var.
    """

    def __init__(self, token: str, model: str = "mistralai/Mistral-7B-Instruct-v0.3"):
        if not token:
            raise RuntimeError("HF_TOKEN not set. Get one at https://huggingface.co/settings/tokens")
        self.token = token
        self.model = model
        self.url = f"https://api-inference.huggingface.co/models/{model}"

    def complete(self, system: str, user: str, max_tokens: int = 1024) -> str:
        prompt = f"<s>[INST] <<SYS>>\n{system}\n<</SYS>>\n\n{user} [/INST]"
        body = {
            "inputs": prompt,
            "parameters": {
                "max_new_tokens": max_tokens,
                "temperature": 0.8,
                "return_full_text": False,
            },
            "options": {"wait_for_model": True},
        }
        data = _http_post_json(self.url, {"Authorization": f"Bearer {self.token}"}, body)
        if isinstance(data, list) and data and "generated_text" in data[0]:
            return data[0]["generated_text"].strip()
        if isinstance(data, dict) and "generated_text" in data:
            return data["generated_text"].strip()
        raise RuntimeError(f"Unexpected HF response: {str(data)[:500]}")


class GroqClient:
    """Groq Cloud. Very fast, free tier, OpenAI-compatible chat API.

    Get a key at https://console.groq.com (free).
    Set GROQ_API_KEY env var.
    """

    def __init__(self, api_key: str, model: str = "qwen/qwen3-32b"):
        if not api_key:
            raise RuntimeError("GROQ_API_KEY not set. Get one at https://console.groq.com")
        self.api_key = api_key
        self.model = model
        self.url = "https://api.groq.com/openai/v1/chat/completions"

    def complete(self, system: str, user: str, max_tokens: int = 1024) -> str:
        body: dict = {
            "model": self.model,
            "max_tokens": max_tokens,
            "temperature": 0.8,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }
        # Reasoning models (qwen3, gpt-oss) need reasoning hidden so output is just the post.
        if any(tag in self.model.lower() for tag in ("qwen3", "gpt-oss", "oss")):
            body["reasoning_format"] = "hidden"
            body["max_tokens"] = max(max_tokens, 1024)
        data = _http_post_json(self.url, {"Authorization": f"Bearer {self.api_key}"}, body)
        text = data["choices"][0]["message"]["content"].strip()
        text = _strip_think_blocks(text)
        return text


def _strip_think_blocks(text: str) -> str:
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL | re.IGNORECASE).strip()
    text = re.sub(r"<think>.*$", "", text, flags=re.DOTALL | re.IGNORECASE).strip()
    return text


class OpenRouterClient:
    """OpenRouter. OpenAI-compatible. Wide model selection (open + closed).

    Get a key at https://openrouter.ai/keys.
    Set OPENROUTER_API_KEY env var.
    """

    def __init__(self, api_key: str, model: str = "meta-llama/llama-3.1-8b-instruct"):
        if not api_key:
            raise RuntimeError("OPENROUTER_API_KEY not set.")
        self.api_key = api_key
        self.model = model
        self.url = "https://openrouter.ai/api/v1/chat/completions"

    def complete(self, system: str, user: str, max_tokens: int = 1024) -> str:
        body = {
            "model": self.model,
            "max_tokens": max_tokens,
            "temperature": 0.8,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "HTTP-Referer": "https://github.com/voiceful",
            "X-Title": "Voiceful",
        }
        data = _http_post_json(self.url, headers, body)
        return data["choices"][0]["message"]["content"].strip()


class TogetherClient:
    """Together AI. OpenAI-compatible. Set TOGETHER_API_KEY."""

    def __init__(self, api_key: str, model: str = "meta-llama/Llama-3.1-8B-Instruct-Turbo"):
        if not api_key:
            raise RuntimeError("TOGETHER_API_KEY not set.")
        self.api_key = api_key
        self.model = model
        self.url = "https://api.together.xyz/v1/chat/completions"

    def complete(self, system: str, user: str, max_tokens: int = 1024) -> str:
        body = {
            "model": self.model,
            "max_tokens": max_tokens,
            "temperature": 0.8,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }
        data = _http_post_json(self.url, {"Authorization": f"Bearer {self.api_key}"}, body)
        return data["choices"][0]["message"]["content"].strip()


class AnthropicClient:
    def __init__(self, api_key: str, model: str):
        if not api_key:
            raise RuntimeError("ANTHROPIC_API_KEY not set.")
        from anthropic import Anthropic
        self._client = Anthropic(api_key=api_key)
        self.model = model

    def complete(self, system: str, user: str, max_tokens: int = 1024) -> str:
        resp = self._client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        return "".join(b.text for b in resp.content if getattr(b, "type", None) == "text").strip()


class DummyClient:
    def complete(self, system: str, user: str, max_tokens: int = 1024) -> str:
        log.warning("Using DummyClient. Set VOICEFUL_LLM_PROVIDER and a key for real generation.")
        return "shipped a thing today. it works. moving on."


def make_client(config) -> LLMClient:
    """Pick provider from env > config > default huggingface."""
    provider = (
        os.environ.get("VOICEFUL_LLM_PROVIDER")
        or config.raw["llm"].get("provider", "huggingface")
    ).lower()

    llm_cfg = config.raw["llm"]

    if provider == "huggingface":
        token = os.environ.get("HF_TOKEN") or llm_cfg.get("hf_token", "")
        model = os.environ.get("VOICEFUL_HF_MODEL") or llm_cfg.get("hf_model", "mistralai/Mistral-7B-Instruct-v0.3")
        if not token:
            log.warning("No HF_TOKEN set, falling back to DummyClient.")
            return DummyClient()
        return HuggingFaceClient(token=token, model=model)

    if provider == "groq":
        key = os.environ.get("GROQ_API_KEY") or llm_cfg.get("groq_api_key", "")
        model = os.environ.get("VOICEFUL_GROQ_MODEL") or llm_cfg.get("groq_model", "llama-3.1-8b-instant")
        if not key:
            log.warning("No GROQ_API_KEY, falling back to DummyClient.")
            return DummyClient()
        return GroqClient(api_key=key, model=model)

    if provider == "openrouter":
        key = os.environ.get("OPENROUTER_API_KEY") or llm_cfg.get("openrouter_api_key", "")
        model = os.environ.get("VOICEFUL_OPENROUTER_MODEL") or llm_cfg.get("openrouter_model", "meta-llama/llama-3.1-8b-instruct")
        return OpenRouterClient(api_key=key, model=model)

    if provider == "together":
        key = os.environ.get("TOGETHER_API_KEY") or llm_cfg.get("together_api_key", "")
        model = os.environ.get("VOICEFUL_TOGETHER_MODEL") or llm_cfg.get("together_model", "meta-llama/Llama-3.1-8B-Instruct-Turbo")
        return TogetherClient(api_key=key, model=model)

    if provider == "anthropic":
        return AnthropicClient(api_key=config.llm_api_key, model=llm_cfg.get("model", "claude-sonnet-4-5-20250929"))

    if provider == "dummy":
        return DummyClient()

    raise RuntimeError(f"Unknown LLM provider: {provider}")
