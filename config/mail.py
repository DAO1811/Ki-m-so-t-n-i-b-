import logging

from django.core.mail.backends.base import BaseEmailBackend

logger = logging.getLogger(__name__)


class StagingBlockedEmailBackend(BaseEmailBackend):
    """Drops every message on staging; nothing leaves the test deployment."""

    def send_messages(self, email_messages):
        count = len(list(email_messages or []))
        if count:
            logger.warning("Staging blocked %d outgoing email(s).", count)
        return 0
