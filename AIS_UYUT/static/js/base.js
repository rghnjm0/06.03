(function() {
            'use strict';

            // Автоскрытие алертов через 5 секунд
            const alerts = document.querySelectorAll('.alert');
            alerts.forEach(alert => {
                setTimeout(() => {
                    const bsAlert = bootstrap.Alert.getOrCreateInstance(alert);
                    if (bsAlert) bsAlert.close();
                }, 5000);
            });

            // Добавление класса при скролле для навбара
            const navbar = document.querySelector('.navbar');
            window.addEventListener('scroll', () => {
                if (window.scrollY > 50) {
                    navbar.style.background = 'rgba(251, 248, 242, 0.97)';
                    navbar.style.boxShadow = '0 8px 24px rgba(75, 55, 44, 0.08)';
                } else {
                    navbar.style.background = 'rgba(251, 248, 242, 0.94)';
                    navbar.style.boxShadow = '0 4px 22px rgba(75, 55, 44, 0.06)';
                }
            });

            // Плавный скролл для якорных ссылок
            document.querySelectorAll('a[href^="#"]').forEach(anchor => {
                anchor.addEventListener('click', function(e) {
                    const href = this.getAttribute('href');
                    if (href === '#') return;

                    const target = document.querySelector(href);
                    if (target) {
                        e.preventDefault();
                        target.scrollIntoView({
                            behavior: 'smooth',
                            block: 'start'
                        });
                    }
                });
            });

            // Активация всех тултипов
            const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
            tooltipTriggerList.map(function (tooltipTriggerEl) {
                return new bootstrap.Tooltip(tooltipTriggerEl);
            });

            // Активация всех поповеров
            const popoverTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="popover"]'));
            popoverTriggerList.map(function (popoverTriggerEl) {
                return new bootstrap.Popover(popoverTriggerEl);
            });
        })();


// Confirm / CSRF / UI helpers (CSP-friendly, no user data in JS string literals)
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
  const el = event.target.closest('[data-confirm-click], [data-dismiss-parent], [data-uppercase-previous], [data-toggle-faq]');
  if (!el) return;
  if (el.dataset.confirmClick && !window.confirm(el.dataset.confirmClick)) {
    event.preventDefault();
    event.stopPropagation();
  }
  if (el.hasAttribute('data-dismiss-parent')) el.parentElement.remove();
  if (el.hasAttribute('data-uppercase-previous')) {
    const input = el.previousElementSibling;
    if (input) input.value = input.value.toUpperCase();
  }
  if (el.hasAttribute('data-toggle-faq')) el.classList.toggle('active');
});

document.addEventListener('change', function (event) {
  if (event.target.matches('[data-submit-on-change]') && event.target.form) {
    event.target.form.requestSubmit();
  }
});
