/* Presentation only. Navigation and motion never touch report data or APIs. */
(() => {
  const menu = document.querySelector('.wl-menu');
  const navigation = document.querySelector('.wl-nav');
  if (menu && navigation) {
    const close = () => { menu.setAttribute('aria-expanded', 'false'); navigation.classList.remove('is-open'); };
    menu.addEventListener('click', () => {
      const open = menu.getAttribute('aria-expanded') !== 'true';
      menu.setAttribute('aria-expanded', String(open)); navigation.classList.toggle('is-open', open);
    });
    navigation.addEventListener('click', event => { if (event.target.closest('a')) close(); });
    document.addEventListener('keydown', event => { if (event.key === 'Escape' && navigation.classList.contains('is-open')) { close(); menu.focus(); } });
  }
  if (window.matchMedia('(prefers-reduced-motion: reduce)').matches || !('IntersectionObserver' in window)) return;
  const observer = new IntersectionObserver(entries => {
    for (const entry of entries) if (entry.isIntersecting) {
      entry.target.classList.add('is-revealed'); observer.unobserve(entry.target);
    }
  }, { threshold: 0.12 });
  // Content stays visible by default, including when JS or observers fail.
  for (const section of document.querySelectorAll('[data-reveal]')) observer.observe(section);
})();
