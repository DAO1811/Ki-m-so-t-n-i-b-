(() => {
  const toggle = document.querySelector('.auth-password-toggle');
  const password = document.getElementById(toggle?.getAttribute('aria-controls'));
  if (!toggle || !password) return;
  toggle.hidden = false;
  toggle.addEventListener('click', () => {
    const visible = password.type === 'password';
    password.type = visible ? 'text' : 'password';
    toggle.setAttribute('aria-pressed', String(visible));
    toggle.setAttribute('aria-label', visible ? 'Ẩn mật khẩu' : 'Hiện mật khẩu');
  });
})();
