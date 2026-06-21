from __future__ import annotations

import json
import logging
import os
from contextlib import contextmanager
from typing import Any, Iterator


LOGGER = logging.getLogger(__name__)
_INITIALIZED = False
_TRACING_ENABLED = False
_TRACER: Any | None = None
_ANTHROPIC_INSTRUMENTED = False
_OPENAI_INSTRUMENTED = False

DEFAULT_PHOENIX_COLLECTOR_ENDPOINT = "http://localhost:6006/v1/traces"
DEFAULT_PHOENIX_PROJECT_NAME = "executor-ai-agent"


class _NoopSpan:
    def set_attribute(self, key: str, value: object) -> None:
        return None

    def record_exception(self, exc: Exception) -> None:
        return None


try:
    from phoenix.otel import register as phoenix_register
except ImportError:  # pragma: no cover - optional local dependency
    phoenix_register = None

try:
    from openinference.instrumentation.anthropic import AnthropicInstrumentor
except ImportError:  # pragma: no cover - optional local dependency
    AnthropicInstrumentor = None

try:
    from openinference.instrumentation.openai import OpenAIInstrumentor
except ImportError:  # pragma: no cover - optional local dependency
    OpenAIInstrumentor = None


def get_tracing_status() -> dict[str, object]:
    return {
        "initialized": _INITIALIZED,
        "enabled": _TRACING_ENABLED,
        "anthropicInstrumented": _ANTHROPIC_INSTRUMENTED,
        "openaiInstrumented": _OPENAI_INSTRUMENTED,
        "collectorEndpoint": _collector_endpoint(),
        "projectName": _project_name(),
        "apiKeyConfigured": bool(os.getenv("PHOENIX_API_KEY")),
        "provider": "phoenix",
    }


def init_tracing() -> None:
    """Initialize Phoenix tracing and instrument the app's LLM SDKs."""
    global _INITIALIZED, _TRACING_ENABLED, _TRACER
    global _ANTHROPIC_INSTRUMENTED, _OPENAI_INSTRUMENTED
    if _INITIALIZED:
        return

    _INITIALIZED = True
    if phoenix_register is None:
        LOGGER.info("Phoenix tracing unavailable: arize-phoenix-otel is not installed.")
        return

    try:
        provider = phoenix_register(
            endpoint=_collector_endpoint(),
            project_name=_project_name(),
            batch=True,
            auto_instrument=False,
            protocol="http/protobuf",
            verbose=False,
        )
        _TRACER = provider.get_tracer("executor-ai.agent")
        _TRACING_ENABLED = True
    except Exception:  # pragma: no cover - defensive
        LOGGER.exception("Failed to initialize Phoenix tracing.")
        return

    _ANTHROPIC_INSTRUMENTED = _instrument(
        AnthropicInstrumentor,
        provider,
        "Anthropic",
    )
    _OPENAI_INSTRUMENTED = _instrument(
        OpenAIInstrumentor,
        provider,
        "OpenAI",
    )


def _instrument(instrumentor_type: Any, provider: Any, provider_name: str) -> bool:
    if instrumentor_type is None:
        LOGGER.info("%s OpenInference instrumentor is not installed.", provider_name)
        return False
    try:
        instrumentor_type().instrument(tracer_provider=provider)
        return True
    except Exception:  # pragma: no cover - defensive
        LOGGER.exception("Failed to instrument %s for Phoenix tracing.", provider_name)
        return False


@contextmanager
def span(name: str, **attributes: object) -> Iterator[Any]:
    """Create a Phoenix span when configured, otherwise use a no-op span."""
    if not _INITIALIZED:
        init_tracing()

    if not _TRACING_ENABLED or _TRACER is None:
        noop_span = _NoopSpan()
        try:
            yield noop_span
        except Exception as exc:
            set_span_error(noop_span, exc)
            raise
        return

    with _TRACER.start_as_current_span(name) as current_span:
        for key, value in attributes.items():
            if value is not None:
                current_span.set_attribute(key, _safe_attribute_value(value))
        try:
            yield current_span
        except Exception as exc:
            set_span_error(current_span, exc)
            raise


def set_span_attribute(current_span: Any, key: str, value: object) -> None:
    if value is not None:
        current_span.set_attribute(key, _safe_attribute_value(value))


def set_span_error(current_span: Any, exc: Exception) -> None:
    current_span.set_attribute("error", True)
    current_span.set_attribute("error.type", exc.__class__.__name__)
    current_span.set_attribute("error.message", str(exc)[:500])
    if hasattr(current_span, "record_exception"):
        current_span.record_exception(exc)


def _safe_attribute_value(value: object) -> object:
    if isinstance(value, str | bool | int | float):
        return value
    try:
        return json.dumps(value, sort_keys=True, default=str)[:4000]
    except TypeError:
        return str(value)[:4000]


def _collector_endpoint() -> str:
    return os.getenv("PHOENIX_COLLECTOR_ENDPOINT", DEFAULT_PHOENIX_COLLECTOR_ENDPOINT)


def _project_name() -> str:
    return os.getenv("PHOENIX_PROJECT_NAME", DEFAULT_PHOENIX_PROJECT_NAME)
