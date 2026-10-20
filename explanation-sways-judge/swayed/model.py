"""Two back ends with one call: `complete(model, context, effort)`.

    LLMX_BACKEND=siwc     the author's ChatGPT-subscription client, found through
                          SIWC_CLIENT_PATH (not part of this repo)
    LLMX_BACKEND=openai   a standard OPENAI_API_KEY client, for anyone rerunning live

Both return {"text", "usage", "model", "seconds"}. On failure they raise ModelError with a short
code only; error bodies are never stored or printed.
"""

import os
import sys
import time


class ModelError(Exception):
    def __init__(self, code):
        super().__init__(code)
        self.code = code


def backend():
    return os.getenv("LLMX_BACKEND", "openai")


def complete(model, context, effort, timeout=120):
    started = time.time()
    if backend() == "siwc":
        out = _siwc(model, context, effort, timeout)
    elif backend() == "openai":
        out = _openai(model, context, effort, timeout)
    else:
        raise ModelError(f"unknown_backend:{backend()}")
    out["seconds"] = round(time.time() - started, 2)
    return out


_siwc_providers = {}


def _siwc(model, context, effort, timeout):
    path = os.getenv("SIWC_CLIENT_PATH")
    if not path:
        raise ModelError("siwc_client_path_not_set")
    if path not in sys.path:
        sys.path.insert(0, path)
    from harness_demo.provider import ProviderError
    from harness_demo.siwc import SiwcProvider

    provider = _siwc_providers.get(effort)
    if provider is None:
        provider = _siwc_providers[effort] = SiwcProvider(reasoning_effort=effort)
    try:
        r = provider.step(model, context, [], timeout)
    except ProviderError as e:
        raise ModelError(str(e.code)) from None
    except TimeoutError:
        raise ModelError("timeout") from None
    return {"text": r.get("text") or "", "usage": _counts(r.get("usage") or {}),
            "model": r.get("model") or model}


def _counts(u):
    """Token counts only; the client's per-message attribution is dropped."""
    return {"input_tokens": u.get("input_tokens"), "output_tokens": u.get("output_tokens"),
            "reasoning_tokens": (u.get("output_tokens_details") or {}).get("reasoning_tokens"),
            "cached_tokens": (u.get("input_tokens_details") or {}).get("cached_tokens")}


def _openai(model, context, effort, timeout):
    from openai import OpenAI, OpenAIError

    system = "\n\n".join(m["content"] for m in context if m["role"] == "developer")
    turns = [m for m in context if m["role"] != "developer"]
    try:
        r = OpenAI(timeout=timeout).responses.create(
            model=model, instructions=system, input=turns, store=False,
            reasoning={"effort": effort})
    except OpenAIError as e:
        raise ModelError(type(e).__name__) from None
    return {"text": r.output_text or "", "model": r.model,
            "usage": _counts(r.usage.model_dump())}
