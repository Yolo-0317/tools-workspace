"""Thin wrapper around the official Ollama Python client for Hermes 3 chat."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Iterator

import ollama
from dotenv import load_dotenv

load_dotenv()


@dataclass
class HermesConfig:
    host: str = field(default_factory=lambda: os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434"))
    model: str = field(
        default_factory=lambda: os.getenv("OLLAMA_MODEL", "goonsai/qwen2.5-3B-goonsai-nsfw-100k")
    )
    system: str = field(default_factory=lambda: os.getenv("HERMES_SYSTEM_PROMPT", ""))


class HermesClient:
    def __init__(self, config: HermesConfig | None = None) -> None:
        self.config = config or HermesConfig()
        self._client = ollama.Client(host=self.config.host)
        self._history: list[dict[str, str]] = []

    @property
    def history(self) -> list[dict[str, str]]:
        return list(self._history)

    def reset(self) -> None:
        self._history.clear()

    def _messages(self, user_text: str) -> list[dict[str, str]]:
        messages: list[dict[str, str]] = []
        if self.config.system.strip():
            messages.append({"role": "system", "content": self.config.system.strip()})
        messages.extend(self._history)
        messages.append({"role": "user", "content": user_text})
        return messages

    def chat(
        self,
        user_text: str,
        *,
        stream: bool = False,
        num_predict: int = 1024,
    ) -> str | Iterator[str]:
        messages = self._messages(user_text)
        if stream:
            return self._stream_chat(messages, user_text, num_predict=num_predict)

        response = self._client.chat(
            model=self.config.model,
            messages=messages,
            options={"num_predict": num_predict},
        )
        assistant_text = response["message"]["content"]
        self._history.append({"role": "user", "content": user_text})
        self._history.append({"role": "assistant", "content": assistant_text})
        return assistant_text

    def complete(
        self,
        user_text: str,
        *,
        stream: bool = False,
        num_predict: int = 4096,
    ) -> str | Iterator[str]:
        """One-shot completion without session history (for rewrite / continuation jobs)."""
        messages: list[dict[str, str]] = []
        if self.config.system.strip():
            messages.append({"role": "system", "content": self.config.system.strip()})
        messages.append({"role": "user", "content": user_text})

        if stream:
            return self._stream_once(messages, num_predict=num_predict)

        response = self._client.chat(
            model=self.config.model,
            messages=messages,
            options={"num_predict": num_predict},
        )
        return response["message"]["content"]

    def _stream_once(self, messages: list[dict[str, str]], *, num_predict: int) -> Iterator[str]:
        stream = self._client.chat(
            model=self.config.model,
            messages=messages,
            stream=True,
            options={"num_predict": num_predict},
        )
        for part in stream:
            token = part["message"]["content"]
            if token:
                yield token

    def _stream_chat(
        self,
        messages: list[dict[str, str]],
        user_text: str,
        *,
        num_predict: int,
    ) -> Iterator[str]:
        chunks: list[str] = []
        stream = self._client.chat(
            model=self.config.model,
            messages=messages,
            stream=True,
            options={"num_predict": num_predict},
        )
        for part in stream:
            token = part["message"]["content"]
            if token:
                chunks.append(token)
                yield token
        assistant_text = "".join(chunks)
        self._history.append({"role": "user", "content": user_text})
        self._history.append({"role": "assistant", "content": assistant_text})

    def ping(self) -> bool:
        try:
            models = self._client.list()
            names = {m.model for m in models.models}
            wanted = self.config.model
            if wanted in names:
                return True
            base = wanted.split(":")[0]
            return any(name == base or name.startswith(f"{base}:") for name in names)
        except Exception:
            return False
