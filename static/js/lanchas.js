/* lanchas.js */
(function () {
  'use strict';

  const app = document.getElementById('la-app');
  if (!app) return;

  /* ── Favoritos (recorridos guardados localmente en el dispositivo) ── */
  const FAV_KEY = 'la-favoritos';

  function escapeHtml(str) {
    return String(str).replace(/[&<>"']/g, c => ({
      '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
    }[c]));
  }

  function getFavoritos() {
    try {
      const raw = localStorage.getItem(FAV_KEY);
      return raw ? JSON.parse(raw) : [];
    } catch (e) {
      return [];
    }
  }

  function setFavoritos(lista) {
    localStorage.setItem(FAV_KEY, JSON.stringify(lista));
  }

  // Pide al service worker que guarde estas páginas para verlas sin conexión,
  // aunque el dispositivo no las haya abierto todavía (ver core/views/sw.py).
  // Los href guardados son relativos a esta página (ej. "?via=..."), no al
  // service worker (que vive en /sw.js) - hay que resolverlos acá antes de
  // mandarlos, si no el SW los interpreta relativos a su propia URL.
  function precachearOffline(hrefs) {
    if (!('serviceWorker' in navigator) || !hrefs.length) return;
    const urls = hrefs.map(h => new URL(h, window.location.href).toString());
    navigator.serviceWorker.ready.then(reg => {
      if (reg.active) {
        reg.active.postMessage({ type: 'CACHE_URLS', urls });
      }
    });
  }

  function esFavorito(slug) {
    return getFavoritos().some(f => f.slug === slug);
  }

  const favRow = document.getElementById('la-fav-row');
  const favToggle = document.getElementById('la-fav-toggle');

  function moverFavorito(slug, dir) {
    const lista = getFavoritos();
    const idx = lista.findIndex(f => f.slug === slug);
    const destino = idx + dir;
    if (idx < 0 || destino < 0 || destino >= lista.length) return;
    [lista[idx], lista[destino]] = [lista[destino], lista[idx]];
    setFavoritos(lista);
    renderFavoritos();
  }

  function renderFavoritos() {
    if (!favRow) return;
    const lista = getFavoritos();
    if (!lista.length) {
      favRow.hidden = true;
      favRow.innerHTML = '';
      return;
    }
    favRow.hidden = false;
    favRow.innerHTML = '<span class="la-fav-row-label">★ Favoritos</span>' + lista.map((f, i) => `
      <div class="la-fav-chip${i === 0 ? ' is-default' : ''}"${i === 0 ? ' title="Se abre por defecto al entrar"' : ''}>
        ${i > 0 ? `<button type="button" class="la-fav-move" data-slug="${f.slug}" data-dir="-1" aria-label="Mover antes" title="Mover antes">‹</button>` : ''}
        <a href="${f.href}">${escapeHtml(f.nombre)}</a>
        ${i < lista.length - 1 ? `<button type="button" class="la-fav-move" data-slug="${f.slug}" data-dir="1" aria-label="Mover después" title="Mover después">›</button>` : ''}
        <button type="button" class="la-fav-remove" data-slug="${f.slug}" aria-label="Quitar favorito" title="Quitar favorito">✕</button>
      </div>
    `).join('');
  }

  function syncFavToggle() {
    if (!favToggle) return;
    const activo = esFavorito(favToggle.dataset.slug);
    favToggle.textContent = activo ? '★' : '☆';
    favToggle.classList.toggle('is-active', activo);
  }

  renderFavoritos();
  syncFavToggle();
  precachearOffline(getFavoritos().map(f => f.href));

  if (favToggle) {
    favToggle.addEventListener('click', () => {
      const slug = favToggle.dataset.slug;
      const lista = getFavoritos();
      const idx = lista.findIndex(f => f.slug === slug);
      if (idx >= 0) {
        lista.splice(idx, 1);
      } else {
        lista.push({ slug, nombre: favToggle.dataset.nombre, href: favToggle.dataset.href });
        precachearOffline([favToggle.dataset.href]);
      }
      setFavoritos(lista);
      syncFavToggle();
      renderFavoritos();
    });
  }

  if (favRow) {
    favRow.addEventListener('click', e => {
      const moveBtn = e.target.closest('.la-fav-move');
      if (moveBtn) {
        e.preventDefault();
        moverFavorito(moveBtn.dataset.slug, parseInt(moveBtn.dataset.dir, 10));
        return;
      }
      const btn = e.target.closest('.la-fav-remove');
      if (!btn) return;
      e.preventDefault();
      setFavoritos(getFavoritos().filter(f => f.slug !== btn.dataset.slug));
      renderFavoritos();
      if (favToggle && favToggle.dataset.slug === btn.dataset.slug) syncFavToggle();
    });
  }

  /* ── Theme toggle ── */
  const THEME_KEY = 'la-theme';
  const saved = localStorage.getItem(THEME_KEY);
  if (saved === 'night') {
    app.dataset.theme = 'night';
    syncThemeUI('night');
  }

  function syncThemeUI(theme) {
    const seg = document.getElementById('la-theme-seg');
    if (seg) {
      seg.querySelectorAll('.la-theme-btn').forEach(b => {
        b.classList.toggle('is-active', b.dataset.themeVal === theme);
      });
    }
    const btn = document.getElementById('la-theme-icon-btn');
    if (btn) btn.textContent = theme === 'night' ? '◑' : '◐';
    const meta = document.getElementById('la-theme-meta');
    if (meta) meta.content = theme === 'night' ? '#14100C' : '#F5EEE0';
  }

  function setTheme(theme) {
    app.dataset.theme = theme;
    localStorage.setItem(THEME_KEY, theme);
    syncThemeUI(theme);
  }

  const segEl = document.getElementById('la-theme-seg');
  if (segEl) {
    segEl.addEventListener('click', e => {
      const btn = e.target.closest('.la-theme-btn');
      if (btn) setTheme(btn.dataset.themeVal);
    });
  }
  const iconBtnEl = document.getElementById('la-theme-icon-btn');
  if (iconBtnEl) {
    iconBtnEl.addEventListener('click', () => {
      setTheme(app.dataset.theme === 'night' ? 'day' : 'night');
    });
  }

  /* ── Filter chips ── */
  const filterRow = document.getElementById('la-filter-row');
  const tableBody = document.getElementById('la-table-body');
  const mobileList = document.getElementById('la-mobile-list');
  const semanaTable = document.getElementById('la-semana-table');

  if (filterRow) {
    filterRow.addEventListener('click', e => {
      const btn = e.target.closest('.la-filter-btn');
      if (!btn) return;
      filterRow.querySelectorAll('.la-filter-btn').forEach(b => b.classList.remove('is-active'));
      btn.classList.add('is-active');
      filterRows(btn.dataset.empresa);
    });
  }

  function filterRows(empresa) {
    const all = empresa === 'all';
    [tableBody, mobileList, semanaTable].forEach(container => {
      if (!container) return;
      container.querySelectorAll('[data-empresa]').forEach(row => {
        row.style.display = (all || row.dataset.empresa === empresa) ? '' : 'none';
      });
    });
  }

  // Si se entró desde una línea del sidebar, el servidor ya marca ese chip
  // como activo - aplicar el filtro correspondiente a las filas también,
  // no solo el estilo del botón.
  if (filterRow) {
    const activo = filterRow.querySelector('.la-filter-btn.is-active');
    if (activo && activo.dataset.empresa !== 'all') {
      filterRows(activo.dataset.empresa);
    }
  }

  /* ── Search: filtra el recorrido del sidebar (buscar tramo o destino),
     no las filas de la tabla de horarios ── */
  const searchInput = document.getElementById('la-search');
  const searchClearBtn = document.getElementById('la-search-clear');
  const lineasAccordion = document.getElementById('la-lineas-accordion');
  const lineaDrops = document.querySelectorAll('.la-linea-drop');
  // En mobile/tablet // LÍNEAS arranca colapsado detrás de este <details> -
  // si hay una búsqueda activa hay que abrirlo, si no el resultado filtrado
  // queda escondido adentro sin que se pueda elegir.
  const sidebarToggle = document.getElementById('la-sidebar-toggle');

  function aplicarFiltroBusqueda() {
    const q = searchInput.value.toLowerCase().trim();
    lineaDrops.forEach(details => {
      let hayMatch = false;
      details.querySelectorAll('.la-station-item--sub').forEach(link => {
        const coincide = !q || link.textContent.toLowerCase().includes(q);
        link.style.display = coincide ? '' : 'none';
        if (coincide && q) hayMatch = true;
      });
      // Con búsqueda: solo abiertas las que tienen resultado. Sin
      // búsqueda (se borró/limpió): todas cerradas de nuevo.
      details.open = q ? hayMatch : false;
    });
    if (sidebarToggle) sidebarToggle.open = !!q;
    if (searchClearBtn) searchClearBtn.style.display = q ? 'inline-flex' : 'none';
  }

  if (searchInput && lineaDrops.length) {
    searchInput.addEventListener('input', aplicarFiltroBusqueda);
    // Si venimos de un click en un resultado filtrado (?buscar=... en la
    // URL), el input ya trae ese valor server-side - aplicar el filtro de
    // una para no mostrar todo abierto hasta el próximo tipeo.
    if (searchInput.value.trim()) aplicarFiltroBusqueda();
  }

  if (searchClearBtn && searchInput) {
    searchClearBtn.addEventListener('click', () => {
      searchInput.value = '';
      aplicarFiltroBusqueda();
      searchInput.focus();
    });
  }

  // Mientras haya una búsqueda activa, un click en cualquier link interno
  // (un resultado del recorrido filtrado, o cambiar de tab Hoy/Semana) se
  // lleva la búsqueda puesta en la URL - si no, al recargar la página el
  // input queda vacío y el acordeón "se abre todo" (pierde el filtro).
  const contenedoresConBusqueda = [
    lineasAccordion,
    document.querySelector('.la-vista-tabs'),
    document.querySelector('.la-chips-row'),
  ].filter(Boolean);

  if (contenedoresConBusqueda.length && searchInput) {
    contenedoresConBusqueda.forEach(contenedor => {
      contenedor.addEventListener('click', e => {
        const link = e.target.closest('a');
        const q = searchInput.value.trim();
        if (!link || !q) return;
        e.preventDefault();
        const url = new URL(link.href, window.location.href);
        url.searchParams.set('buscar', q);
        window.location.href = url.toString();
      });
    });
  }

  /* ── Ficha técnica: lightbox de capturas del pipeline ── */
  const lightbox = document.getElementById('la-lightbox');
  const lightboxImg = document.getElementById('la-lightbox-img');
  const lightboxClose = lightbox?.querySelector('.la-lightbox-close');
  const shotTriggers = document.querySelectorAll('.la-shot-btn');

  if (lightbox && lightboxImg && shotTriggers.length) {
    const openLightbox = (src, alt) => {
      lightboxImg.src = src;
      lightboxImg.alt = alt || '';
      lightbox.hidden = false;
    };
    const closeLightbox = () => {
      lightbox.hidden = true;
      lightboxImg.src = '';
    };

    shotTriggers.forEach(trigger => {
      trigger.addEventListener('click', () => {
        openLightbox(trigger.dataset.lightboxSrc, trigger.dataset.lightboxAlt);
      });
    });

    lightboxClose?.addEventListener('click', closeLightbox);

    lightbox.addEventListener('click', e => {
      if (e.target === lightbox) closeLightbox();
    });

    document.addEventListener('keydown', e => {
      if (e.key === 'Escape' && !lightbox.hidden) closeLightbox();
    });
  }

})();
