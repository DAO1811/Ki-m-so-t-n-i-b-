from inventory.access import is_admin

from .services import locked_accounts


def lockout_context(request):
    """Admins see how many real accounts wait to be unlocked."""
    user = getattr(request, "user", None)
    if not is_admin(user):
        return {}
    return {"locked_login_count": len(locked_accounts())}
