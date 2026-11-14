/* Restore display preferences before the stylesheet paints. */
(() => {
  'use strict';
  try {
    const root = document.documentElement;
    if (localStorage.getItem('riceshift.sidebar') === 'collapsed') root.classList.add('sidebar-collapsed');
    const size = Number(localStorage.getItem('riceshift.textSize'));
    if ([90, 100, 125, 150, 200].includes(size)) {
      root.style.fontSize = size + '%';
      root.toggleAttribute('data-large-text', size >= 150);
      root.dataset.textSize = String(size);
    }
    const current = new URL(location.href);
    const storedLanguage = localStorage.getItem('riceshift.language');
    if (!current.searchParams.has('lang') && storedLanguage === 'en') {
      const method = document.querySelector('meta[name="riceshift-request-method"]')?.content;
      if (method === 'POST') {
        // Use the rendered language link so a legacy POST keeps its form values.
        document.addEventListener('DOMContentLoaded', () => {
          const translated = document.querySelector('.language-switch a[lang="en"]');
          if (translated) location.replace(translated.href);
        }, { once: true });
      } else {
        current.searchParams.set('lang', 'en');
        location.replace(current.href);
      }
    }
  } catch (error) { /* All pages remain usable when storage is unavailable. */ }
})();
