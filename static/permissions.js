(() => {
  const root = document.getElementById('function-permissions');
  if (!root) return;
  const dependencies = JSON.parse(document.getElementById('permission-dependencies').textContent);
  const boxes = [...root.querySelectorAll('input[name=function_permissions]')];
  const byKey = Object.fromEntries(boxes.map(box => [box.value, box]));
  function update(changed) {
    if (changed.checked) {
      for (const key of dependencies[changed.value] || []) byKey[key].checked = true;
    } else {
      for (const box of boxes) if ((dependencies[box.value] || []).includes(changed.value)) box.checked = false;
    }
    document.getElementById('permission-count').textContent = boxes.filter(box => box.checked).length + ' quyền đang chọn';
  }
  boxes.forEach(box => box.addEventListener('change', () => update(box)));
  document.getElementById('clear-function-permissions')?.addEventListener('click', () => {
    boxes.filter(box => !box.disabled).forEach(box => box.checked = false);
    document.getElementById('permission-count').textContent = '0 quyền đang chọn';
  });
})();
