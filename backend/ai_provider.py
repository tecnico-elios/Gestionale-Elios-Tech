"""F20 (26/02/2026) — Astrazione AIProvider per l'Assistente AI.

Provider di default: Groq (free tier, OpenAI-compatible API).
Configurabile via env vars — server-side only, key MAI esposta al frontend.

Cambio provider: settare AI_PROVIDER=groq|openai|... + AI_API_KEY + AI_MODEL.
NON usa EMERGENT_LLM_KEY per rispettare la richiesta esplicita dell'utente.
"""
from __future__ import annotations

import os
import json
import logging
import asyncio
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)


class AIProviderError(Exception):
    """Errore normalizzato dal provider (rate limit, quota, invalid key, timeout, offline)."""
    def __init__(self, kind: str, message: str, retryable: bool = False):
        super().__init__(message)
        self.kind = kind  # invalid_key | rate_limit | quota | timeout | offline | http_error | invalid_model
        self.retryable = retryable


class AIProvider:
    """Interfaccia base. Ogni provider implementa `chat(messages, tools)`."""
    name: str = "base"
    model: str = ""

    async def chat(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        temperature: float = 0.2,
        max_tokens: int = 1024,
    ) -> Dict[str, Any]:
        raise NotImplementedError


class GroqProvider(AIProvider):
    """Groq — OpenAI-compatible API. Free tier con rate limit generoso.
    Documentazione: https://console.groq.com/docs — tool/function calling supportato
    da modelli openai/gpt-oss-120b, llama-3.1-70b-versatile, mixtral-8x7b-32768.
    """
    BASE_URL = "https://api.groq.com/openai/v1/chat/completions"

    def __init__(self, api_key: str, model: str):
        if not api_key:
            raise AIProviderError("invalid_key", "AI_API_KEY non configurata")
        if not model:
            raise AIProviderError("invalid_model", "AI_MODEL non configurato")
        self.api_key = api_key
        self.model = model
        self.name = "groq"

    async def chat(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        temperature: float = 0.2,
        max_tokens: int = 1024,
    ) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        resp = None
        # I rate limit Groq possono essere molto brevi. Riproviamo automaticamente
        # senza costringere l'utente a riscrivere il messaggio nella chat.
        for attempt in range(3):
            try:
                async with httpx.AsyncClient(timeout=35.0) as client:
                    resp = await client.post(self.BASE_URL, headers=headers, json=payload)
            except httpx.TimeoutException:
                if attempt < 2:
                    await asyncio.sleep(1.2 * (attempt + 1))
                    continue
                raise AIProviderError("timeout", "Servizio AI temporaneamente lento. Riprova tra qualche secondo.", retryable=True)
            except httpx.RequestError as e:
                if attempt < 2:
                    await asyncio.sleep(1.0 * (attempt + 1))
                    continue
                raise AIProviderError("offline", f"Servizio AI non raggiungibile: {type(e).__name__}", retryable=True)
            if resp.status_code != 429:
                break
            if attempt < 2:
                retry_after = resp.headers.get("retry-after")
                try:
                    delay = max(0.8, min(float(retry_after), 5.0)) if retry_after else 1.4 * (attempt + 1)
                except Exception:
                    delay = 1.4 * (attempt + 1)
                logger.warning("Groq rate limit: retry %s/2 tra %.1fs", attempt + 1, delay)
                await asyncio.sleep(delay)
                continue
        if resp is None:
            raise AIProviderError("offline", "Servizio AI non raggiungibile", retryable=True)
        if resp.status_code == 401:
            raise AIProviderError("invalid_key", "AI API key non valida")
        if resp.status_code == 429:
            raise AIProviderError("rate_limit", "Servizio AI temporaneamente occupato. Riprova tra qualche secondo.", retryable=True)
        if resp.status_code == 402 or resp.status_code == 403:
            raise AIProviderError("quota", "Quota provider esaurita")
        if resp.status_code >= 400:
            # NON loggare il body completo (potrebbe contenere echo della key). Log solo status + estratto.
            body_preview = resp.text[:200] if resp.text else ""
            logger.error(f"Groq HTTP {resp.status_code}: {body_preview}")
            
            try:
                detail = (resp.json().get("error") or {}).get("message") or ""
            except Exception:
                detail = ""
            if resp.status_code == 413:
                raise AIProviderError("context_too_large", "Richiesta AI troppo grande. Il gestionale ha ridotto automaticamente il contesto: riprova la stessa domanda.", retryable=True)
            if resp.status_code == 404 and detail:
                raise AIProviderError("invalid_model", f"Modello AI non disponibile: {detail[:180]}")
            raise AIProviderError("http_error", f"Errore provider ({resp.status_code})" + (f": {detail[:180]}" if detail else ""))
        data = resp.json()
        try:
            choice = data["choices"][0]
            msg = choice["message"]
            return {
                "content": msg.get("content") or "",
                "tool_calls": msg.get("tool_calls") or [],
                "finish_reason": choice.get("finish_reason"),
                "usage": data.get("usage") or {},
            }
        except (KeyError, IndexError, TypeError) as e:
            raise AIProviderError("http_error", f"Risposta provider non valida: {e}")


def create_ai_provider(provider_name: str, api_key: str, model: str) -> AIProvider:
    """Factory esplicita: usata dalle impostazioni salvate nel database."""
    provider_name = (provider_name or "groq").strip().lower()
    api_key = (api_key or "").strip()
    model = (model or "").strip()
    if provider_name == "groq":
        return GroqProvider(api_key=api_key, model=model or "openai/gpt-oss-120b")
    raise AIProviderError("invalid_model", f"Provider AI '{provider_name}' non supportato")


def get_ai_provider() -> AIProvider:
    """Retro-compat: configurazione via env."""
    return create_ai_provider(
        os.environ.get("AI_PROVIDER") or "groq",
        os.environ.get("AI_API_KEY") or "",
        os.environ.get("AI_MODEL") or "openai/gpt-oss-120b",
    )
