/* Vanilla JavaScript enhancements; all assessment data comes from Flask. */
(() => {
  'use strict';
  const root = document.documentElement;
  const messages = document.getElementById('client-messages').dataset;
  const sidebar = document.getElementById('sidebar');
  const workspace = document.getElementById('workspace');
  const mobilebar = document.querySelector('.mobilebar');
  const menu = document.getElementById('menu-toggle');
  const close = document.getElementById('drawer-close');
  const collapse = document.getElementById('sidebar-toggle');
  const overlay = document.getElementById('overlay');
  const mobile = matchMedia('(max-width: 1023px)');
  let drawerOpen = false;

  const save = (key, value) => {
    try { localStorage.setItem(key, value); } catch (error) { /* Optional persistence. */ }
  };
  save('riceshift.language', root.lang);

  function updateCollapse() {
    const expanded = !root.classList.contains('sidebar-collapsed');
    collapse.setAttribute('aria-expanded', String(expanded));
    collapse.setAttribute('aria-label', expanded ? messages.collapse : messages.expand);
    collapse.querySelector('.toggle-label').textContent = expanded ? messages.collapse : messages.expand;
  }

  function setDrawer(open, restoreFocus = true) {
    drawerOpen = open && mobile.matches;
    sidebar.classList.toggle('open', drawerOpen);
    overlay.classList.toggle('visible', drawerOpen);
    document.body.classList.toggle('menu-open', drawerOpen);
    menu.setAttribute('aria-expanded', String(drawerOpen));
    menu.setAttribute('aria-label', drawerOpen ? messages.closeMenu : messages.openMenu);
    sidebar.inert = mobile.matches && !drawerOpen;
    workspace.inert = drawerOpen;
    mobilebar.inert = drawerOpen;
    if (drawerOpen) {
      sidebar.setAttribute('role', 'dialog');
      sidebar.setAttribute('aria-modal', 'true');
      close.focus();
    } else {
      sidebar.removeAttribute('role');
      sidebar.removeAttribute('aria-modal');
      if (restoreFocus && mobile.matches) menu.focus();
    }
  }
  menu.addEventListener('click', () => setDrawer(!drawerOpen));
  close.addEventListener('click', () => setDrawer(false));
  overlay.addEventListener('click', () => setDrawer(false));
  mobile.addEventListener('change', () => setDrawer(false, false));
  collapse.addEventListener('click', () => {
    const collapsed = root.classList.toggle('sidebar-collapsed');
    save('riceshift.sidebar', collapsed ? 'collapsed' : 'expanded');
    updateCollapse();
  });
  document.addEventListener('keydown', (event) => {
    if (!drawerOpen) return;
    if (event.key === 'Escape') {
      event.preventDefault();
      setDrawer(false);
    } else if (event.key === 'Tab') {
      const controls = [...sidebar.querySelectorAll('a[href],button:not([disabled])')]
        .filter((element) => element.getClientRects().length > 0);
      const first = controls[0];
      const last = controls[controls.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    }
  });
  updateCollapse();
  setDrawer(false, false);

  const sizes = [90, 100, 125, 150, 200];
  const less = document.getElementById('text-less');
  const more = document.getElementById('text-more');
  const sizeOutput = document.getElementById('text-size');

  function setTextSize(size) {
    const value = sizes.includes(size) ? size : 100;
    root.style.fontSize = value + '%';
    root.dataset.textSize = String(value);
    root.toggleAttribute('data-large-text', value >= 150);
    sizeOutput.value = value + '%';
    sizeOutput.textContent = value + '%';
    less.disabled = value === sizes[0];
    more.disabled = value === sizes[sizes.length - 1];
    save('riceshift.textSize', String(value));
  }
  less.addEventListener('click', () => {
    const position = sizes.indexOf(Number(root.dataset.textSize));
    setTextSize(sizes[Math.max(0, position - 1)]);
  });
  more.addEventListener('click', () => {
    const position = sizes.indexOf(Number(root.dataset.textSize));
    setTextSize(sizes[Math.min(sizes.length - 1, position + 1)]);
  });
  document.getElementById('text-reset').addEventListener('click', () => setTextSize(100));
  setTextSize(Number(root.dataset.textSize) || 100);

  // Native selects stay keyboard accessible. A wrapped echo keeps their whole
  // selected label readable when text is enlarged beyond the control's width.
  document.querySelectorAll('select').forEach((select) => {
    const current = document.createElement('span');
    current.className = 'select-current';
    current.setAttribute('aria-hidden', 'true');
    select.after(current);
    const update = () => { current.textContent = select.selectedOptions[0]?.textContent || ''; };
    select.addEventListener('change', update);
    update();
  });

  const form = document.getElementById('farm-form');
  if (!form) return;
  const ph = document.getElementById('soil-ph');
  const accepted = {
    season: ['Dong_Xuan', 'He_Thu', 'Thu_Dong'],
    scenario: ['normal', 'low_rainfall'],
    salinity: ['yes', 'no', 'unknown'],
    goal: ['save_water', 'protect_soil', 'keep_practice']
  };
  form.noValidate = true;
  function validate() {
    const raw = ph.value.trim();
    ph.setCustomValidity(raw && (!/^[0-9]+([.,][0-9]+)?$/.test(raw) || Number(raw.replace(',', '.')) > 14) ? messages.errorPh : '');
    Object.entries(accepted).forEach(([name, values]) => {
      const control = form.elements.namedItem(name);
      control.setCustomValidity(values.includes(control.value) ? '' : messages.invalidChoice);
    });
    form.querySelectorAll('input[type=radio]').forEach((control) => {
      control.setCustomValidity(control.validity.valueMissing ? messages.requiredChoice : '');
    });
  }
  form.addEventListener('submit', (event) => {
    ph.value = ph.value.trim();
    validate();
    const invalid = [...form.querySelectorAll('input,select')].find((control) => !control.checkValidity());
    if (!invalid) return;
    event.preventDefault();
    const disclosure = invalid.closest('details');
    if (disclosure) disclosure.open = true;
    invalid.focus();
    invalid.reportValidity();
  });
  form.addEventListener('input', validate);
  form.addEventListener('change', validate);

  function syncNavigation() {
    const values = new FormData(form);
    const keys = ['season','scenario','drainage','irrigation','salinity','soil_ph','goal','calendar'];
    const homePath = new URL(form.action).pathname;
    document.querySelectorAll('a[href]').forEach((link) => {
      const url = new URL(link.href, location.href);
      if (url.origin !== location.origin || url.pathname !== homePath || !url.searchParams.has('view')) return;
      keys.forEach((key) => {
        if (values.has(key) || key === 'calendar') url.searchParams.set(key, values.get(key) || '');
      });
      link.href = url.href;
    });
    const current = new URL(location.href);
    keys.forEach((key) => {
      if (values.has(key) || key === 'calendar') current.searchParams.set(key, values.get(key) || '');
    });
    current.searchParams.set('view', 'farm');
    current.searchParams.set('lang', root.lang);
    try { history.replaceState(null, '', current); } catch (error) { /* Links retain the state. */ }
  }
  form.addEventListener('input', syncNavigation);
  form.addEventListener('change', syncNavigation);
})();
