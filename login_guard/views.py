from django.contrib.auth.views import LoginView

from .forms import GuardedAuthenticationForm


class GuardedLoginView(LoginView):
    template_name = "login.html"
    authentication_form = GuardedAuthenticationForm
