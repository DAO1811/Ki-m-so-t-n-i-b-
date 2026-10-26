(() => {
  const form = document.querySelector('[data-deviation-analysis]');
  if (!form) return;
  const input = (name) => form.querySelector(`[data-risk-input="${name}"]`);
  const updateRisk = () => {
    const likelihood = Number(input('likelihood')?.value);
    const consequence = Number(input('consequence')?.value);
    const score = likelihood && consequence ? likelihood * consequence : null;
    form.querySelector('[data-risk-score]').textContent = score === null ? 'Chưa đánh giá' : String(score);
    form.querySelector('[data-risk-band]').textContent = score === null ? '' : `Nguy cơ ${score >= 10 ? 'cao' : score >= 5 ? 'trung bình' : 'thấp'}`;
  };
  form.querySelectorAll('[data-risk-input]').forEach((element) => element.addEventListener('change', updateRisk));
  updateRisk();
  const button = form.querySelector('[data-add-why]');
  const total = form.querySelector('[name="whys-TOTAL_FORMS"]');
  button?.addEventListener('click', () => {
    const index = Number(total.value);
    if (!Number.isInteger(index) || index >= 20) { button.disabled = true; return; }
    const template = form.querySelector('[data-why-template]');
    const fragment = template.content.cloneNode(true);
    fragment.querySelectorAll('[name], [id], label[for]').forEach((element) => {
      ['name', 'id', 'for'].forEach((attr) => {
        if (element.hasAttribute(attr)) element.setAttribute(attr, element.getAttribute(attr).replaceAll('__prefix__', String(index)));
      });
    });
    form.querySelector('[data-why-rows]').appendChild(fragment);
    total.value = String(index + 1);
    button.disabled = index + 1 >= 20;
  });
})();
