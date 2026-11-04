"""Fixed provider and Free-plan attestation; no custom URLs or paid fallback."""

import os
import re
from dataclasses import dataclass

from django.conf import settings

MODEL = "openai/gpt-oss-120b"
ENDPOINT = "https://api.groq.com/openai/v1/chat/completions"
MAX_OUTPUT_TOKENS = 1024
MAX_PROMPT_BYTES = 6500
MAX_SECONDS = 25
ORG_REQUESTS_DAY = 100
USER_REQUESTS_DAY = 20
ORG_TOKENS_DAY = 100000
USER_TOKENS_DAY = 40000
ORG_REQUESTS_MINUTE = 12
USER_REQUESTS_MINUTE = 6


@dataclass(frozen=True)
class Configuration:
    key: str
    confirmed: bool

    @property
    def ready(self):
        return bool(self.key and self.confirmed)


def configuration():
    # Reading environment does not copy secrets into Django settings/debug output.
    key = os.environ.get("GROQ_API_KEY", "").strip()
    if not re.fullmatch(r"gsk_[A-Za-z0-9_-]{20,180}", key):
        key = ""
    return Configuration(key, os.environ.get("GROQ_FREE_ZDR_CONFIRMED") == "1")


def is_enabled():
    # Used by tests via an override, not by API callers.
    return configuration().ready and not getattr(settings, "GROQ_CHAT_DISABLED", False)
