"""A thin provider layer: one tool-calling conversation and one structured-JSON call, for
OpenAI (Responses API) and Anthropic (Messages API). Nothing else."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass

# USD per 1M tokens (input, output), standard tier. Checked 2026-10-15 on
# developers.openai.com/api/docs/pricing. Unknown models just show no cost.
PRICES = {
    "gpt-6-luna": (0.10, 0.50),
    "gpt-6.1-sol": (2.00, 10.00),
    "gpt-6-sol": (2.00, 10.00),
    "gpt-5.4-mini": (0.75, 4.50),
}


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: dict
    raw_arguments: str


@dataclass
class Turn:
    text: str
    tool_calls: list[ToolCall]
    usage: dict
    reasoning_summary: str = ""


@dataclass
class Usage:
    input_tokens: int = 0
    output_tokens: int = 0
    calls: int = 0

    def add(self, u: dict) -> None:
        self.input_tokens += u.get("input_tokens", 0)
        self.output_tokens += u.get("output_tokens", 0)
        self.calls += 1

    def as_dict(self) -> dict:
        return {"input_tokens": self.input_tokens, "output_tokens": self.output_tokens, "calls": self.calls}


def cost_usd(model: str, usage: dict) -> float | None:
    if model not in PRICES:
        return None
    pin, pout = PRICES[model]
    return (usage["input_tokens"] * pin + usage["output_tokens"] * pout) / 1e6


def _parse_args(raw: str) -> dict:
    try:
        value = json.loads(raw or "{}")
        return value if isinstance(value, dict) else {"_raw": raw}
    except json.JSONDecodeError:
        return {"_raw": raw}


# --------------------------------------------------------------------------- OpenAI


class OpenAIProvider:
    name = "openai"

    def __init__(self, model: str, reasoning_effort: str | None = None):
        from openai import OpenAI

        self.client = OpenAI()
        self.model = model
        self.reasoning_effort = reasoning_effort

    def _reasoning(self, summary: bool) -> dict:
        r = {}
        if self.reasoning_effort:
            r["effort"] = self.reasoning_effort
        if summary:
            r["summary"] = "auto"
        return r

    def conversation(self, system: str, user_message: str, tools: list[dict]) -> "OpenAIConversation":
        return OpenAIConversation(self, system, user_message, tools)

    def json(self, system: str, user: str, schema: dict, name: str) -> tuple[dict, dict]:
        kwargs = dict(model=self.model, instructions=system, input=user, store=False,
                      text={"format": {"type": "json_schema", "name": name, "strict": True, "schema": schema}})
        if self.reasoning_effort:
            kwargs["reasoning"] = self._reasoning(False)
        r = self.client.responses.create(**kwargs)
        return json.loads(r.output_text), _openai_usage(r)


def _openai_usage(r) -> dict:
    u = r.usage
    return {"input_tokens": u.input_tokens, "output_tokens": u.output_tokens}


class OpenAIConversation:
    def __init__(self, provider: OpenAIProvider, system: str, user_message: str, tools: list[dict]):
        self.p = provider
        self.system = system
        self.tools = [{"type": "function", "name": t["name"], "description": t["description"],
                       "parameters": t["parameters"], "strict": True} for t in tools]
        self.input: list = [{"role": "user", "content": user_message}]

    def step(self) -> Turn:
        r = self.p.client.responses.create(
            model=self.p.model, instructions=self.system, input=self.input, tools=self.tools,
            store=False, include=["reasoning.encrypted_content"], reasoning=self.p._reasoning(True),
        )
        calls, texts, summaries = [], [], []
        for item in r.output:
            # Feed every output item back so the model keeps its own reasoning across turns.
            self.input.append(item.model_dump(exclude_none=True))
            if item.type == "function_call":
                calls.append(ToolCall(item.call_id, item.name, _parse_args(item.arguments), item.arguments))
            elif item.type == "message":
                texts += [c.text for c in item.content if getattr(c, "type", "") == "output_text"]
            elif item.type == "reasoning":
                summaries += [s.text for s in (item.summary or [])]
        return Turn("\n".join(texts).strip(), calls, _openai_usage(r), "\n".join(summaries).strip())

    def add_tool_results(self, results: list[tuple[str, dict]]) -> None:
        for call_id, output in results:
            self.input.append({"type": "function_call_output", "call_id": call_id,
                               "output": json.dumps(output, ensure_ascii=False)})


# ------------------------------------------------------------------------ Anthropic


class AnthropicProvider:
    name = "anthropic"

    def __init__(self, model: str, max_tokens: int = 4096):
        import anthropic

        self.client = anthropic.Anthropic()
        self.model = model
        self.max_tokens = max_tokens

    def conversation(self, system: str, user_message: str, tools: list[dict]) -> "AnthropicConversation":
        return AnthropicConversation(self, system, user_message, tools)

    def json(self, system: str, user: str, schema: dict, name: str) -> tuple[dict, dict]:
        # Forced tool use is Anthropic's way to get schema-shaped output.
        r = self.client.messages.create(
            model=self.model, max_tokens=self.max_tokens, system=system,
            messages=[{"role": "user", "content": user}],
            tools=[{"name": name, "description": "Return the result.", "input_schema": schema}],
            tool_choice={"type": "tool", "name": name},
        )
        block = next(b for b in r.content if b.type == "tool_use")
        return dict(block.input), _anthropic_usage(r)


def _anthropic_usage(r) -> dict:
    return {"input_tokens": r.usage.input_tokens, "output_tokens": r.usage.output_tokens}


class AnthropicConversation:
    def __init__(self, provider: AnthropicProvider, system: str, user_message: str, tools: list[dict]):
        self.p = provider
        self.system = system
        self.tools = [{"name": t["name"], "description": t["description"], "input_schema": t["parameters"]}
                      for t in tools]
        self.messages: list = [{"role": "user", "content": user_message}]

    def step(self) -> Turn:
        r = self.p.client.messages.create(model=self.p.model, max_tokens=self.p.max_tokens,
                                          system=self.system, messages=self.messages, tools=self.tools)
        self.messages.append({"role": "assistant", "content": [b.model_dump(exclude_none=True) for b in r.content]})
        texts = [b.text for b in r.content if b.type == "text"]
        calls = [ToolCall(b.id, b.name, dict(b.input), json.dumps(b.input, ensure_ascii=False))
                 for b in r.content if b.type == "tool_use"]
        return Turn("\n".join(texts).strip(), calls, _anthropic_usage(r))

    def add_tool_results(self, results: list[tuple[str, dict]]) -> None:
        self.messages.append({"role": "user", "content": [
            {"type": "tool_result", "tool_use_id": call_id, "content": json.dumps(output, ensure_ascii=False)}
            for call_id, output in results
        ]})


# --------------------------------------------------------------------------- config


@dataclass
class Config:
    agent_provider: str = "openai"
    agent_model: str = "gpt-6-luna"
    eval_provider: str = "openai"
    eval_model: str = "gpt-6-luna"
    reasoning_effort: str | None = None

    @classmethod
    def from_env(cls) -> "Config":
        return cls(
            agent_provider=os.getenv("SVD_PROVIDER", "openai"),
            agent_model=os.getenv("SVD_MODEL", "gpt-6-luna"),
            eval_provider=os.getenv("SVD_EVAL_PROVIDER", os.getenv("SVD_PROVIDER", "openai")),
            eval_model=os.getenv("SVD_EVAL_MODEL", "gpt-6-luna"),
            reasoning_effort=os.getenv("SVD_REASONING_EFFORT") or None,
        )


def make_provider(provider: str, model: str, reasoning_effort: str | None = None):
    if provider == "openai":
        return OpenAIProvider(model, reasoning_effort)
    if provider == "anthropic":
        return AnthropicProvider(model)
    raise ValueError(f"unknown provider {provider!r} (use openai or anthropic)")
