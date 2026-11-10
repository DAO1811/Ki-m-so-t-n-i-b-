from .services import available


def passkey_context(request):
    return {"passkeys_available": available()}
