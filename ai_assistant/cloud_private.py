import base64
import hashlib
import json
import time

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings
from django.utils.crypto import salted_hmac


def cipher():
    key = hashlib.sha256(
        b"dhd-groq-private-v1:" + settings.SECRET_KEY.encode()
    ).digest()
    return Fernet(base64.urlsafe_b64encode(key))


def seal(value):
    return cipher().encrypt(json.dumps(value, ensure_ascii=False).encode()).decode()


def unseal(value):
    try:
        return json.loads(cipher().decrypt(value.encode(), ttl=600))
    except (InvalidToken, ValueError, AttributeError, TypeError):
        raise ValueError(
            "Cuộc trò chuyện đã hết hạn. Hãy bắt đầu cuộc trao đổi mới."
        ) from None


def session_scope(request):
    return salted_hmac(
        "groq-chat-session-v1",
        str(request.session.session_key) + request.user.get_session_auth_hash(),
    ).hexdigest()


def read_history(token, user_id, scope):
    if not isinstance(token, str) or len(token) > 18000:
        raise ValueError("Ngữ cảnh hội thoại không hợp lệ.")
    if not token:
        return []
    data = unseal(token)
    if (
        data.get("user") != user_id
        or data.get("session") != scope
        or time.time() - data.get("at", 0) > 600
    ):
        raise ValueError(
            "Cuộc trò chuyện không thuộc phiên đăng nhập hiện tại hoặc đã hết hạn."
        )
    return data["messages"]


def history_token(messages, user_id, scope):
    # Only a few recent turns, no business facts or permanent conversation store.
    messages = messages[-6:]
    while messages and len(json.dumps(messages, ensure_ascii=False).encode()) > 4500:
        messages = messages[2:]
    return seal(
        {"user": user_id, "session": scope, "at": time.time(), "messages": messages}
    )
