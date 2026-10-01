(function () {
  'use strict';

  // CSRF для POST-форм без скрытого поля
  window.UYUT_CSRF = window.UYUT_CSRF || null;

  document.addEventListener('submit', function (event) {
    const form = event.target;
    if (!(form instanceof HTMLFormElement)) return;

    const message = form.dataset.confirm;
    if (message && !window.confirm(message)) {
      event.preventDefault();
      return;
    }

    if (form.method && form.method.toLowerCase() === 'post' &&
        !form.querySelector('input[name="_csrf_token"]') &&
        window.UYUT_CSRF) {
      const input = document.createElement('input');
      input.type = 'hidden';
      input.name = '_csrf_token';
      input.value = window.UYUT_CSRF;
      form.appendChild(input);
    }
  });

  document.addEventListener('click', function (event) {
    const button = event.target.closest('[data-dismiss-parent]');
    if (button) button.parentElement.remove();

    const confirmEl = event.target.closest('[data-confirm-click]');
    if (confirmEl && confirmEl.dataset.confirmClick) {
      if (!window.confirm(confirmEl.dataset.confirmClick)) {
        event.preventDefault();
        event.stopPropagation();
      }
    }
  });

  document.addEventListener('change', function (event) {
    if (event.target.matches('[data-submit-on-change]') && event.target.form) {
      event.target.form.requestSubmit();
    }
  });
})();
