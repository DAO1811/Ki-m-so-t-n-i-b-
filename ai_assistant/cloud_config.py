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
# Groq Free for openai/gpt-oss-120b (console.groq.com/docs/rate-limits, checked
# 14/11/2026): 30 requests/min, 1K requests/day, 8K tokens/min, 200K tokens/day.
# Our caps stay below those so the shared free key is never exhausted.
ORG_REQUESTS_DAY = 200  # one question may use up to 4 provider requests
USER_REQUESTS_DAY = 30
ORG_TOKENS_DAY = 180000
USER_TOKENS_DAY = 60000
ORG_TOKENS_MINUTE = 7000
ORG_REQUESTS_MINUTE = 12
USER_REQUESTS_MINUTE = 6
# Trợ lý AI v2: tool rounds per question and the whole job deadline.
MAX_TOOL_ROUNDS = 3
MAX_TOOL_CALLS = 4
JOB_SECONDS = 40


@dataclass(frozen=True)
class Configuration:
    key: str
    confirmed: bool

    @property
    def ready(self):
        return bool(self.key and self.confirmed)


def staging_blocked():
    # Staging never reaches Groq unless the owner explicitly enables it with a
    # separate staging-only key (STAGING_ALLOW_GROQ=1); staging holds test data.
    return getattr(
        settings, "APP_ENVIRONMENT", "production"
    ) == "staging" and not getattr(settings, "STAGING_ALLOW_GROQ", False)


def configuration():
    if staging_blocked():
        # Staging never sends text to Groq, even if a key was set by mistake.
        return Configuration("", False)
    # Reading environment does not copy secrets into Django settings/debug output.
    key = os.environ.get("GROQ_API_KEY", "").strip()
    if not re.fullmatch(r"gsk_[A-Za-z0-9_-]{20,180}", key):
        key = ""
    return Configuration(key, os.environ.get("GROQ_FREE_ZDR_CONFIRMED") == "1")


def is_enabled():
    # Used by tests via an override, not by API callers.
    return configuration().ready and not getattr(settings, "GROQ_CHAT_DISABLED", False)
