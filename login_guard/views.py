from django.contrib.auth.views import LoginView

from .forms import GuardedAuthenticationForm


class GuardedLoginView(LoginView):
    template_name = "login.html"
    authentication_form = GuardedAuthenticationForm

    def form_valid(self, form):
        response = super().form_valid(form)
        # A fresh password sign-in lets this browser turn on Face ID right away
        # without typing the password again (owner request 23/11/2026).
        from passkeys.services import mark_password_login

        mark_password_login(self.request)
        return response
