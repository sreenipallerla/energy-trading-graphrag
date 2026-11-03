"""Swappable LLM and embedding providers. Pick with LLM_PROVIDER=ollama (default) or azure.

Ollama runs on your machine (free). Azure uses an Azure OpenAI deployment (Foundry). The rest of the code only sees
the two small interfaces below, so switching provider changes no other file.
"""
from __future__ import annotations

import os
from typing import Protocol

import httpx


class LLM(Protocol):
    name: str

    def chat(self, system: str, user: str, temperature: float = 0.0) -> str: ...


class Embedder(Protocol):
    name: str

    def embed(self, texts: list[str]) -> list[list[float]]: ...


class OllamaLLM:
    def __init__(self, host: str | None = None, model: str | None = None):
        self.host = (host or os.getenv("OLLAMA_HOST", "http://localhost:11434")).rstrip("/")
        self.model = model or os.getenv("OLLAMA_CHAT_MODEL", "qwen2.5:7b")
        self.name = f"ollama:{self.model}"

    def chat(self, system: str, user: str, temperature: float = 0.0) -> str:
        r = httpx.post(f"{self.host}/api/chat", timeout=300, json={
            "model": self.model, "stream": False, "options": {"temperature": temperature},
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]})
        r.raise_for_status()
        return r.json()["message"]["content"]


class OllamaEmbedder:
    def __init__(self, host: str | None = None, model: str | None = None):
        self.host = (host or os.getenv("OLLAMA_HOST", "http://localhost:11434")).rstrip("/")
        self.model = model or os.getenv("OLLAMA_EMBED_MODEL", "nomic-embed-text")
        self.name = f"ollama:{self.model}"

    def embed(self, texts: list[str]) -> list[list[float]]:
        r = httpx.post(f"{self.host}/api/embed", timeout=300, json={"model": self.model, "input": texts})
        r.raise_for_status()
        return r.json()["embeddings"]


def _azure_client():
    """Azure OpenAI client. Uses AZURE_OPENAI_API_KEY if set, else Entra ID (DefaultAzureCredential)."""
    from openai import AzureOpenAI

    endpoint = os.environ["AZURE_OPENAI_ENDPOINT"]
    version = os.getenv("AZURE_OPENAI_API_VERSION", "2024-10-21")
    key = os.getenv("AZURE_OPENAI_API_KEY")
    if key:
        return AzureOpenAI(azure_endpoint=endpoint, api_key=key, api_version=version)
    from azure.identity import DefaultAzureCredential, get_bearer_token_provider

    token = get_bearer_token_provider(DefaultAzureCredential(), "https://cognitiveservices.azure.com/.default")
    return AzureOpenAI(azure_endpoint=endpoint, azure_ad_token_provider=token, api_version=version)


class AzureLLM:
    def __init__(self, deployment: str | None = None):
        self.deployment = deployment or os.getenv("AZURE_CHAT_DEPLOYMENT", "chat")
        self.name = f"azure:{self.deployment}"
        self.client = _azure_client()

    def chat(self, system: str, user: str, temperature: float = 0.0) -> str:
        r = self.client.chat.completions.create(
            model=self.deployment, temperature=temperature,
            messages=[{"role": "system", "content": system}, {"role": "user", "content": user}])
        return r.choices[0].message.content or ""


class AzureEmbedder:
    def __init__(self, deployment: str | None = None):
        self.deployment = deployment or os.getenv("AZURE_EMBED_DEPLOYMENT", "embed")
        self.name = f"azure:{self.deployment}"
        self.client = _azure_client()

    def embed(self, texts: list[str]) -> list[list[float]]:
        r = self.client.embeddings.create(model=self.deployment, input=texts)
        return [d.embedding for d in r.data]


def make_llm(provider: str | None = None) -> LLM:
    p = (provider or os.getenv("LLM_PROVIDER", "ollama")).lower()
    if p == "ollama":
        return OllamaLLM()
    if p == "azure":
        return AzureLLM()
    raise ValueError(f"unknown LLM_PROVIDER {p!r} (use ollama or azure)")


def make_embedder(provider: str | None = None) -> Embedder:
    p = (provider or os.getenv("EMBED_PROVIDER", os.getenv("LLM_PROVIDER", "ollama"))).lower()
    if p == "ollama":
        return OllamaEmbedder()
    if p == "azure":
        return AzureEmbedder()
    raise ValueError(f"unknown EMBED_PROVIDER {p!r} (use ollama or azure)")
