"""
RAG generation for the Document Intelligence pipeline.

Takes a user question + retrieved context chunks and produces a grounded,
citation-backed answer. Responsibilities:

    1. Connect to an LLM provider (OpenAI, Google Gemini, or OpenRouter) using
       credentials from the root ``.env`` — auto-detected, or passed explicitly
       from the Week 1 sidebar selection.
    2. Enforce a strict grounding system prompt: answer ONLY from the retrieved
       context; if the answer isn't there, reply with the exact fallback line.
    3. generate_rag_response(query, vector_store_results, chat_history):
       assemble the labelled context, inject conversation history, call the LLM.
    4. Return the answer text AND a structured list of citations
       (document name, page number, text snippet) for display under the answer.

All providers are reached through the OpenAI-compatible SDK, so the same code
path serves OpenAI, Gemini (via Google's OpenAI endpoint), and OpenRouter.
"""

from __future__ import annotations

import logging
import os
import re
import time
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

logger = logging.getLogger(__name__)
if not logging.getLogger().handlers and not logger.handlers:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

# --------------------------------------------------------------------------- #
#  Providers (OpenAI-compatible)
# --------------------------------------------------------------------------- #
PROVIDERS: Dict[str, Dict[str, Any]] = {
    "openrouter": {
        "base_url": "https://openrouter.ai/api/v1",
        "env": "OPENROUTER_API_KEY",
        "default_model": "meta-llama/llama-3.3-70b-instruct:free",
    },
    "openai": {
        "base_url": None,
        "env": "OPENAI_API_KEY",
        "default_model": "gpt-4o-mini",
    },
    "google": {
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
        "env": "GOOGLE_API_KEY",
        "default_model": "gemini-2.0-flash",
    },
}

# Accept flexible provider names (e.g. the Week 1 UI labels).
_PROVIDER_ALIASES = {
    "openai": "openai", "open ai": "openai",
    "openrouter": "openrouter", "open router": "openrouter",
    "google": "google", "gemini": "google", "google ai studio": "google",
}

FALLBACK_ANSWER = "I cannot find the answer in the provided documents."

SYSTEM_PROMPT = f"""You are a precise document-analysis assistant. Answer the user's \
question using ONLY the information contained in the CONTEXT section provided in the \
user's message.

Strict rules:
1. Ground every statement solely in the provided context. Do NOT use outside/prior \
knowledge, and do NOT make assumptions or guesses.
2. If the answer cannot be found in the context, reply with EXACTLY this sentence and \
nothing else: "{FALLBACK_ANSWER}"
3. Support your claims by citing the relevant blocks inline using their labels, e.g. \
[Source 1], [Source 2]. Only cite labels that actually appear in the context.
4. Never invent document names, page numbers, quotes, or facts.
5. Be concise, factual, and well-structured.
"""

_MAX_HISTORY_TURNS = 6          # recent messages kept for conversational context
_SNIPPET_CHARS = 240            # citation snippet length


# --------------------------------------------------------------------------- #
#  Helpers
# --------------------------------------------------------------------------- #
def _normalize_provider(provider: Optional[str]) -> Optional[str]:
    if not provider:
        return None
    return _PROVIDER_ALIASES.get(provider.strip().lower())


def _auto_detect_provider() -> Optional[str]:
    """Pick the first provider whose API key is present in the environment.
    Order favours the free tier (OpenRouter) first."""
    for name in ("openrouter", "openai", "google"):
        if os.getenv(PROVIDERS[name]["env"]):
            return name
    return None


def _snippet(text: str, limit: int = _SNIPPET_CHARS) -> str:
    text = " ".join((text or "").split())
    return text if len(text) <= limit else text[:limit].rstrip() + "…"


def _build_context_and_citations(results: List[Dict[str, Any]]):
    """Turn retrieved chunks into a labelled context string + a citation list.

    Returns
    -------
    (context_str, citations) where citations is a list of dicts:
        {"label", "source", "page", "snippet", "score"}  (in label order)
    """
    blocks: List[str] = []
    citations: List[Dict[str, Any]] = []

    for i, hit in enumerate(results, start=1):
        label = f"[Source {i}]"
        meta = hit.get("metadata", {}) or {}
        source = meta.get("source", "unknown")
        page = meta.get("page", "?")
        text = hit.get("text", "") or ""

        chunk = meta.get("chunk", "?")
        blocks.append(f"{label} (document: {source}, page: {page}, chunk: {chunk})\n{text.strip()}")
        citations.append({
            "label": label,
            "source": source,
            "page": page,
            "chunk": chunk,                 # retrieved chunk reference
            "snippet": _snippet(text),
            "score": hit.get("score"),
            "match": hit.get("match"),      # semantic / keyword / fused
        })

    return "\n\n".join(blocks), citations


def _history_messages(chat_history: Optional[List[Dict[str, str]]]) -> List[Dict[str, str]]:
    """Sanitize + trim prior conversation turns for the messages array."""
    if not chat_history:
        return []
    cleaned = []
    for m in chat_history:
        role = (m.get("role") or "").lower()
        content = m.get("content") or ""
        if role in ("user", "assistant") and content.strip():
            cleaned.append({"role": role, "content": content})
    return cleaned[-_MAX_HISTORY_TURNS:]


def _extract_usage(response: Any) -> Optional[Dict[str, int]]:
    """Pull token counts off an OpenAI-compatible response (if the provider reports them)."""
    usage = getattr(response, "usage", None)
    if not usage:
        return None
    def _get(name):
        value = getattr(usage, name, None)
        return int(value) if isinstance(value, (int, float)) else 0
    total = _get("total_tokens")
    prompt_t, completion_t = _get("prompt_tokens"), _get("completion_tokens")
    if not total:
        total = prompt_t + completion_t
    if not (total or prompt_t or completion_t):
        return None
    return {"prompt": prompt_t, "completion": completion_t, "total": total}


def _friendly_error(exc: Exception) -> str:
    err = str(exc)
    low = err.lower()
    if any(t in low for t in ("api_key", "authentication", "401", "invalid_api_key")):
        return "🔑 Invalid or missing API key. Check your provider credentials."
    if any(t in low for t in ("403", "permission_denied", "denied access")):
        return "🚫 Access denied by the provider (project/region restriction). Try OpenRouter."
    if any(t in low for t in ("404", "not found", "no endpoints")):
        return "🚫 Model unavailable for this provider. Pick a different model."
    if any(t in low for t in ("429", "rate limit", "quota")):
        return "⏳ Rate limit / quota reached. Wait a moment or switch model."
    if any(t in low for t in ("connection", "timeout", "network")):
        return "🌐 Connection failed. Check your internet and retry."
    return f"⚠️ Generation failed: {err}"


# --------------------------------------------------------------------------- #
#  Pipeline
# --------------------------------------------------------------------------- #
class RAGPipeline:
    """Grounded RAG answer generator over an OpenAI-compatible provider.

    Parameters
    ----------
    provider, model, api_key, base_url : optional
        Override the LLM connection. If omitted, provider is auto-detected from
        the environment keys and defaults are filled in.
    temperature : float
        Low by default (0.2) to keep answers grounded and deterministic.
    client : optional
        Inject a pre-built OpenAI-compatible client (used for testing).
    """

    def __init__(
        self,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        temperature: float = 0.2,
        client: Any = None,
    ):
        resolved = _normalize_provider(provider) or _auto_detect_provider() or "openrouter"
        cfg = PROVIDERS[resolved]

        self.provider = resolved
        self.model = model or cfg["default_model"]
        self.api_key = api_key or os.getenv(cfg["env"], "")
        self.base_url = base_url if base_url is not None else cfg["base_url"]
        self.temperature = temperature
        self._client = client

    # ----- connection ----------------------------------------------------- #
    @property
    def client(self):
        if self._client is None:
            if not self.api_key:
                raise RuntimeError(
                    f"No API key for provider '{self.provider}'. Set "
                    f"{PROVIDERS[self.provider]['env']} in your .env or pass api_key."
                )
            self._client = OpenAI(api_key=self.api_key, base_url=self.base_url)
        return self._client

    # ----- main entry ----------------------------------------------------- #
    def generate_rag_response(
        self,
        query: str,
        vector_store_results: List[Dict[str, Any]],
        chat_history: Optional[List[Dict[str, str]]] = None,
        persona: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Generate a grounded answer for ``query`` using retrieved chunks.

        Parameters
        ----------
        query : str
            The user's question.
        vector_store_results : list[dict]
            Output of ``VectorStore.search_similar_chunks`` — each item is
            ``{"text", "metadata": {"source", "page", ...}, "score"}``.
        chat_history : list[dict], optional
            Prior turns as ``{"role": "user"|"assistant", "content": str}``.

        Returns
        -------
        dict
            ``{"answer": str,
               "citations": [{"label","source","page","snippet","score","cited"}],
               "provider": str, "model": str, "latency": float, "error": str|None}``

            ``citations`` lists every retrieved chunk shown to the model, with
            ``cited=True`` for the ones the answer actually references inline.
        """
        query = (query or "").strip()
        if not query:
            return self._result(FALLBACK_ANSWER, [], error="Empty query.")

        # No context retrieved -> do not hallucinate, do not spend a call.
        if not vector_store_results:
            logger.info("No context retrieved; returning grounded fallback.")
            return self._result(FALLBACK_ANSWER, [])

        context_str, citations = _build_context_and_citations(vector_store_results)

        user_message = (
            "CONTEXT:\n"
            "----------------------------------------\n"
            f"{context_str}\n"
            "----------------------------------------\n\n"
            f"QUESTION: {query}\n\n"
            "Answer using ONLY the context above. Cite sources inline as [Source N]. "
            f'If the answer is not present, reply exactly: "{FALLBACK_ANSWER}"'
        )

        # Optional persona sets tone/role; the grounding rules always stay authoritative.
        system_content = SYSTEM_PROMPT
        if persona and persona.strip():
            system_content = (
                f"{persona.strip()}\n\n"
                "Regardless of the role/persona above, you MUST always obey these "
                f"strict document-grounding rules:\n{SYSTEM_PROMPT}"
            )

        messages = [{"role": "system", "content": system_content}]
        messages += _history_messages(chat_history)
        messages.append({"role": "user", "content": user_message})

        t0 = time.time()
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=self.temperature,
            )
            # Some providers intermittently return choices=null / an empty list.
            choices = getattr(response, "choices", None)
            if not choices:
                raise RuntimeError("Provider returned no choices (empty response).")
            answer = (choices[0].message.content or "").strip()
            usage = _extract_usage(response)
        except Exception as exc:
            logger.error("LLM generation failed: %s", exc)
            return self._result(_friendly_error(exc), [], error=str(exc),
                                latency=round(time.time() - t0, 2))

        latency = round(time.time() - t0, 2)
        if not answer:
            answer = FALLBACK_ANSWER

        # Mark which sources the answer actually cited inline.
        cited_nums = {int(n) for n in re.findall(r"\[Source\s*(\d+)\]", answer)}
        for idx, cite in enumerate(citations, start=1):
            cite["cited"] = idx in cited_nums

        # If the model returned the pure fallback, nothing was really "used".
        if answer.strip().rstrip(".").lower() == FALLBACK_ANSWER.rstrip(".").lower():
            citations = []

        logger.info("RAG answer generated in %.2fs via %s/%s.", latency, self.provider, self.model)
        return self._result(answer, citations, latency=latency, usage=usage)

    # ----- auxiliary LLM tasks (summary / questions / comparison) --------- #
    def complete(self, prompt: str, system: Optional[str] = None,
                 temperature: float = 0.3, max_tokens: int = 700):
        """One-shot completion for helper features. Returns (text, error, usage)."""
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        try:
            response = self.client.chat.completions.create(
                model=self.model, messages=messages,
                temperature=temperature, max_tokens=max_tokens,
            )
            choices = getattr(response, "choices", None)
            if not choices:
                raise RuntimeError("Provider returned no choices (empty response).")
            return (choices[0].message.content or "").strip(), None, _extract_usage(response)
        except Exception as exc:
            logger.error("complete() failed: %s", exc)
            return "", _friendly_error(exc), None

    # ----- output shaping ------------------------------------------------- #
    def _result(self, answer, citations, error=None, latency=None, usage=None) -> Dict[str, Any]:
        return {
            "answer": answer,
            "citations": citations,
            "provider": self.provider,
            "model": self.model,
            "latency": latency,
            "usage": usage,
            "error": error,
        }


# --------------------------------------------------------------------------- #
#  Module-level convenience wrapper (default pipeline from env)
# --------------------------------------------------------------------------- #
_default_pipeline: Optional[RAGPipeline] = None


def get_pipeline(**kwargs) -> RAGPipeline:
    """Return a shared RAGPipeline. Pass kwargs to (re)configure it."""
    global _default_pipeline
    if _default_pipeline is None or kwargs:
        _default_pipeline = RAGPipeline(**kwargs)
    return _default_pipeline


def generate_rag_response(
    query: str,
    vector_store_results: List[Dict[str, Any]],
    chat_history: Optional[List[Dict[str, str]]] = None,
    persona: Optional[str] = None,
) -> Dict[str, Any]:
    """Grounded RAG answer using the default (env-configured) pipeline."""
    return get_pipeline().generate_rag_response(
        query, vector_store_results, chat_history, persona=persona
    )
