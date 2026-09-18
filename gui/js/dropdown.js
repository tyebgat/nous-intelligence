// ── Custom dropdowns (Voice Technitos style, rounded) ──
// Enhances every native <select> into a custom trigger + listbox menu while
// keeping the native element as the value store, so all existing settings
// code (reads of .value, "change" listeners, .value = assignments) keeps
// working unchanged.
(function () {
  'use strict';

  var CHEVRON_HTML =
    '<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2.5"' +
    ' stroke-linecap="round" stroke-linejoin="round"><polyline points="6 9 12 15 18 9"/></svg>';
  var CHECK_HTML =
    '<svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="3"' +
    ' stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>';

  var nativeValueDesc = (function () {
    try {
      return Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype, 'value');
    } catch (e) {
      return null;
    }
  })();

  function itemFrom(opt) {
    var item = document.createElement('li');
    item.className = 'dropdown__item';
    item.setAttribute('role', 'option');
    item.dataset.value = opt.value;
    var text = document.createElement('span');
    text.textContent = opt.textContent || opt.value;
    var check = document.createElement('span');
    check.className = 'dropdown__check';
    check.innerHTML = CHECK_HTML;
    item.append(text, check);
    return item;
  }

  function buildMenu(select, menu) {
    menu.replaceChildren();
    Array.prototype.forEach.call(select.children, function (child) {
      if (child.tagName === 'OPTGROUP') {
        var label = document.createElement('li');
        label.className = 'dropdown__group';
        label.textContent = child.label || '';
        menu.appendChild(label);
        Array.prototype.forEach.call(child.children, function (opt) {
          menu.appendChild(itemFrom(opt));
        });
      } else if (child.tagName === 'OPTION') {
        menu.appendChild(itemFrom(child));
      }
    });
  }

  function syncFromNative(select, wrapper) {
    var valueEl = wrapper.querySelector('.dropdown__value');
    var opt = select.options[select.selectedIndex];
    if (valueEl && opt) valueEl.textContent = opt.textContent || opt.value;
    var menu = wrapper.querySelector('.dropdown__menu');
    if (!menu) return;
    var current = select.value;
    menu.querySelectorAll('.dropdown__item').forEach(function (item) {
      var selected = item.dataset.value === current;
      item.setAttribute('aria-selected', String(selected));
      item.classList.toggle('selected', selected);
    });
  }

  function closeMenu(wrapper) {
    wrapper.classList.remove('open');
    var t = wrapper.querySelector('.dropdown__trigger');
    if (t) t.setAttribute('aria-expanded', 'false');
  }

  function closeAllMenus() {
    document.querySelectorAll('.dropdown.open').forEach(closeMenu);
  }

  function openMenu(wrapper) {
    closeAllMenus();
    wrapper.classList.add('open');
    var t = wrapper.querySelector('.dropdown__trigger');
    if (t) t.setAttribute('aria-expanded', 'true');
  }

  function enhance(select) {
    if (!select || select.tagName !== 'SELECT') return;
    if (select.dataset.enhanced) return;
    select.dataset.enhanced = '1';

    var wrapper = document.createElement('div');
    wrapper.className = 'dropdown';
    select.parentNode.insertBefore(wrapper, select);
    wrapper.appendChild(select);
    select.classList.add('dropdown__native');

    var trigger = document.createElement('button');
    trigger.type = 'button';
    trigger.className = 'dropdown__trigger';
    trigger.setAttribute('aria-haspopup', 'listbox');
    trigger.setAttribute('aria-expanded', 'false');

    var valueEl = document.createElement('span');
    valueEl.className = 'dropdown__value';
    var chevron = document.createElement('span');
    chevron.className = 'dropdown__chevron';
    chevron.innerHTML = CHEVRON_HTML;
    trigger.append(valueEl, chevron);

    var menu = document.createElement('ul');
    menu.className = 'dropdown__menu';
    menu.setAttribute('role', 'listbox');

    wrapper.append(trigger, menu);

    buildMenu(select, menu);
    syncFromNative(select, wrapper);

    trigger.addEventListener('click', function (e) {
      e.stopPropagation();
      if (wrapper.classList.contains('open')) closeMenu(wrapper);
      else openMenu(wrapper);
    });

    menu.addEventListener('click', function (e) {
      var item = e.target.closest('.dropdown__item');
      if (!item) return;
      if (nativeValueDesc) {
        nativeValueDesc.set.call(select, item.dataset.value);
      } else {
        select.value = item.dataset.value;
      }
      syncFromNative(select, wrapper);
      select.dispatchEvent(new Event('change', { bubbles: true }));
      closeMenu(wrapper);
    });

    if (nativeValueDesc) {
      Object.defineProperty(select, 'value', {
        configurable: true,
        enumerable: true,
        get: function () {
          return nativeValueDesc.get.call(this);
        },
        set: function (v) {
          nativeValueDesc.set.call(this, v);
          syncFromNative(this, wrapper);
        }
      });
    }

    // Rebuild the menu when options change dynamically (audio device list).
    var observer = new MutationObserver(function () {
      buildMenu(select, menu);
      syncFromNative(select, wrapper);
    });
    observer.observe(select, { childList: true, subtree: true });
  }

  function enhanceAll() {
    document.querySelectorAll('select:not([data-enhanced])').forEach(enhance);
  }

  document.addEventListener('click', function (e) {
    var dd = e.target.closest('.dropdown');
    document.querySelectorAll('.dropdown.open').forEach(function (w) {
      if (!dd || dd !== w) closeMenu(w);
    });
  });

  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape') closeAllMenus();
  });

  window.addEventListener('blur', closeAllMenus);

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', enhanceAll);
  } else {
    enhanceAll();
  }
})();