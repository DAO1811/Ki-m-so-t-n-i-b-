"""Streaming transport only. No SDK, logging of prompts, redirects or retries."""

import json
import socket
import threading
import time
import urllib.error
import urllib.request
from contextlib import contextmanager
from dataclasses import dataclass

from .cloud_config import ENDPOINT, MAX_OUTPUT_TOKENS, MAX_SECONDS, MODEL, configuration


class ProviderError(Exception):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


@dataclass(frozen=True)
class Chunk:
    text: str = ""
    usage: int | None = None


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args):
        return None


@contextmanager
def deadline_guard(response, deadline):
    # A socket read timeout alone can be prolonged by a trickling incomplete
    # SSE line. Interrupt the underlying socket at the absolute deadline.
    def expire():
        try:
            response.fp.raw._sock.shutdown(socket.SHUT_RDWR)
        except (AttributeError, OSError):
            pass

    timer = threading.Timer(max(0, deadline - time.monotonic()), expire)
    timer.daemon = True
    timer.start()
    try:
        yield
    finally:
        timer.cancel()


def open_stream(messages):
    conf = configuration()
    if not conf.ready:
        raise ProviderError("not_configured")
    body = json.dumps(
        {
            "model": MODEL,
            "messages": messages,
            "stream": True,
            "stream_options": {"include_usage": True},
            "reasoning_effort": "low",
            "include_reasoning": False,
            "max_completion_tokens": MAX_OUTPUT_TOKENS,
        },
        ensure_ascii=False,
    ).encode()
    req = urllib.request.Request(
        ENDPOINT,
        data=body,
        headers={
            "Authorization": "Bearer " + conf.key,
            "Content-Type": "application/json",
            "Accept": "text/event-stream",
        },
    )
    deadline = time.monotonic() + MAX_SECONDS
    size = 0
    try:
        with (
            urllib.request.build_opener(NoRedirect).open(req, timeout=6) as response,
            deadline_guard(response, deadline),
        ):
            if (
                response.status != 200
                or "text/event-stream" not in response.headers.get("Content-Type", "")
            ):
                raise ProviderError("provider_error")
            while True:
                if time.monotonic() > deadline:
                    raise ProviderError("timeout")
                raw = response.readline(65537)
                if not raw:
                    raise ProviderError(
                        "timeout" if time.monotonic() >= deadline else "interrupted"
                    )
                size += len(raw)
                if len(raw) > 65536 or size > 196608:
                    raise ProviderError("provider_error")
                if not raw.startswith(b"data:"):
                    continue
                event = raw[5:].strip()
                if event == b"[DONE]":
                    return
                data = json.loads(event)
                if data.get("error"):
                    raise ProviderError("provider_error")
                # Do not return chain of thought, tool calls, or arbitrary URLs/actions.
                choices = data.get("choices") or []
                text = choices[0].get("delta", {}).get("content") if choices else ""
                if text and not isinstance(text, str):
                    raise ProviderError("provider_error")
                usage_data = data.get("usage")
                if not isinstance(usage_data, dict):
                    metadata = data.get("x_groq")
                    usage_data = (
                        metadata.get("usage") if isinstance(metadata, dict) else None
                    )
                usage = (
                    usage_data.get("total_tokens")
                    if isinstance(usage_data, dict)
                    else None
                )
                yield Chunk(
                    text or "", usage if type(usage) is int and usage >= 0 else None
                )
    except urllib.error.HTTPError as exc:
        code = (
            "provider_limit"
            if exc.code == 429
            else "invalid_key"
            if exc.code in {401, 403}
            else "provider_error"
        )
        exc.close()
        raise ProviderError(code) from None
    except (TimeoutError, socket.timeout):
        raise ProviderError("timeout") from None
    except (
        urllib.error.URLError,
        OSError,
        ValueError,
        AttributeError,
        IndexError,
        TypeError,
    ):
        raise ProviderError(
            "timeout" if time.monotonic() >= deadline else "provider_error"
        ) from None
