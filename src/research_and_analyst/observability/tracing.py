"""
Observability wiring for LangSmith and Langfuse.

LangSmith traces are picked up automatically by LangChain/LangGraph once the
relevant environment variables are set — `configure_langsmith()` just
validates that they are present and logs whether tracing is active, so a
missing key fails loudly in logs rather than silently producing no traces.

Langfuse requires an explicit callback handler to be passed into each
graph/chain invocation's `config={"callbacks": [...]}`. `get_langfuse_handler()`
builds that handler once and reuses it; if Langfuse isn't configured, it
returns None so callers can skip it without branching everywhere.
"""

import os
import logging

log = logging.getLogger(__name__)

_langfuse_handler = None
_langfuse_checked = False


def configure_langsmith() -> bool:
    """
    Validate LangSmith environment configuration.

    Required env vars (standard LangChain names):
        LANGCHAIN_TRACING_V2=true
        LANGCHAIN_API_KEY=...
        LANGCHAIN_PROJECT=research-report-generator   (optional, defaults set by LangChain)

    Returns:
        bool: True if LangSmith tracing is active.
    """
    tracing_enabled = os.getenv("LANGCHAIN_TRACING_V2", "false").lower() == "true"
    api_key = os.getenv("LANGCHAIN_API_KEY")

    if tracing_enabled and not api_key:
        log.warning(
            "LANGCHAIN_TRACING_V2 is set but LANGCHAIN_API_KEY is missing — "
            "LangSmith tracing will fail silently. Set LANGCHAIN_API_KEY."
        )
        return False

    if tracing_enabled and api_key:
        project = os.getenv("LANGCHAIN_PROJECT", "default")
        log.info("LangSmith tracing enabled | project=%s", project)
        return True

    log.info("LangSmith tracing disabled (LANGCHAIN_TRACING_V2 not set to true)")
    return False


def get_langfuse_handler():
    """
    Build (once) and return a Langfuse CallbackHandler, or None if Langfuse
    is not configured / not installed.

    Required env vars:
        LANGFUSE_PUBLIC_KEY
        LANGFUSE_SECRET_KEY
        LANGFUSE_HOST (optional, defaults to Langfuse cloud)
    """
    global _langfuse_handler, _langfuse_checked

    if _langfuse_checked:
        return _langfuse_handler

    _langfuse_checked = True

    public_key = os.getenv("LANGFUSE_PUBLIC_KEY")
    secret_key = os.getenv("LANGFUSE_SECRET_KEY")

    if not public_key or not secret_key:
        log.info("Langfuse not configured (missing LANGFUSE_PUBLIC_KEY/SECRET_KEY) — skipping")
        return None

    try:
        from langfuse.callback import CallbackHandler

        _langfuse_handler = CallbackHandler(
            public_key=public_key,
            secret_key=secret_key,
            host=os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com"),
        )
        log.info("Langfuse tracing enabled | host=%s", os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com"))
    except ImportError:
        log.warning("langfuse package not installed — run `pip install langfuse` to enable Langfuse tracing")
        _langfuse_handler = None
    except Exception as e:
        log.error("Failed to initialise Langfuse handler | error=%s", str(e), exc_info=True)
        _langfuse_handler = None

    return _langfuse_handler


def get_tracing_callbacks() -> list:
    """
    Convenience helper: returns the list of callback handlers to pass into
    `graph.stream(..., config={"callbacks": get_tracing_callbacks()})`.

    LangSmith doesn't need a callback object (it's picked up globally via
    env vars), so this only returns the Langfuse handler when available.
    """
    handler = get_langfuse_handler()
    return [handler] if handler else []
