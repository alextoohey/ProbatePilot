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

DEFAULT_ARIZE_COLLECTOR_ENDPOINT = "https://otlp.arize.com/v1/traces"
DEFAULT_ARIZE_PROJECT_NAME = "clearpath-estate-agent"
DEFAULT_SERVICE_NAME = "clearpath-estate-agent"


class _NoopSpan:
    def set_attribute(self, key: str, value: object) -> None:
        return None

    def record_exception(self, exc: Exception) -> None:
        return None


try:
    from opentelemetry.sdk.resources import Resource
except ImportError:  # pragma: no cover - optional local dependency
    Resource = None

try:
    from openinference.instrumentation.anthropic import AnthropicInstrumentor
except ImportError:  # pragma: no cover - optional local dependency
    AnthropicInstrumentor = None

try:
    from arize.otel import register as arize_register
    from arize.otel import set_routing_context as arize_set_routing_context
except ImportError:  # pragma: no cover - optional local dependency
    arize_register = None
    arize_set_routing_context = None


def get_tracing_status() -> dict[str, object]:
    return {
        "initialized": _INITIALIZED,
        "enabled": _TRACING_ENABLED,
        "anthropicInstrumented": _ANTHROPIC_INSTRUMENTED,
        "collectorEndpoint": _collector_endpoint(),
        "projectName": _project_name(),
        "spaceIdConfigured": bool(os.getenv("ARIZE_SPACE_ID")),
        "provider": "arize_ax",
    }


def init_tracing() -> None:
    """Initialize Arize AX tracing when configured."""
    global _INITIALIZED, _TRACING_ENABLED, _TRACER, _ANTHROPIC_INSTRUMENTED
    if _INITIALIZED:
        return

    _INITIALIZED = True

    if Resource is None or arize_register is None:
        LOGGER.info("Arize tracing unavailable: required tracing dependencies are not installed.")
        return

    api_key = os.getenv("ARIZE_API_KEY")
    space_id = os.getenv("ARIZE_SPACE_ID")
    project_name = os.getenv("ARIZE_PROJECT_NAME")
    if not api_key or not space_id or not project_name:
        missing = [
            name
            for name, value in (
                ("ARIZE_API_KEY", api_key),
                ("ARIZE_SPACE_ID", space_id),
                ("ARIZE_PROJECT_NAME", project_name),
            )
            if not value
        ]
        LOGGER.info("Arize tracing disabled: missing required env vars: %s", ", ".join(missing))
        return

    if arize_set_routing_context is None:
        LOGGER.info("Arize tracing disabled: arize.otel.set_routing_context is unavailable.")
        return

    collector_endpoint = _collector_endpoint()
    service_name = os.getenv("OTEL_SERVICE_NAME", DEFAULT_SERVICE_NAME)
    deployment_environment = os.getenv("APP_ENV", "development")

    try:
        provider = arize_register(
            endpoint=collector_endpoint,
            project_name=project_name,
            batch=True,
            auto_instrument=False,
            verbose=False,
            api_key=api_key
        )
        arize_set_routing_context(space_id=space_id, project_name=project_name)
        _TRACER = provider.get_tracer("clearpath-estate.agent")
        _TRACING_ENABLED = True
    except Exception:  # pragma: no cover - defensive
        LOGGER.exception("Failed to initialize Arize AX tracing.")
        return

    if AnthropicInstrumentor is not None:
        try:
            AnthropicInstrumentor().instrument()
            _ANTHROPIC_INSTRUMENTED = True
        except Exception:  # pragma: no cover - defensive
            LOGGER.exception("Failed to instrument Anthropic client for Arize tracing.")
    else:
        LOGGER.info("Anthropic instrumentor unavailable; Claude calls will use manual spans only.")


def init_phoenix() -> None:
    """Compatibility alias for older imports."""
    init_tracing()


@contextmanager
def span(name: str, **attributes: object) -> Iterator[Any]:
    """Create a tracing span when Arize is configured, else fall back to a no-op."""
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
    return os.getenv("ARIZE_COLLECTOR_ENDPOINT", DEFAULT_ARIZE_COLLECTOR_ENDPOINT)


def _project_name() -> str:
    return os.getenv("ARIZE_PROJECT_NAME", DEFAULT_ARIZE_PROJECT_NAME)
