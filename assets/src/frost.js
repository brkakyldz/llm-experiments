// Small line icons used by the images: <span data-icon="arrow"></span> gets the arrow.
const ICON = {
  arrow: '<svg viewBox="0 0 24 24"><path d="M7 17L17 7M9 7h8v8"/></svg>',
  record: '<svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="8"/><circle cx="12" cy="12" r="3"/></svg>',
  grade: '<svg viewBox="0 0 24 24"><path d="M4 7l2 2 3-3M4 15l2 2 3-3M12 8h8M12 16h8"/></svg>',
  check: '<svg viewBox="0 0 24 24"><path d="M3 12.5l4 4L15 8M10 15.5l1 1L20 8"/></svg>',
  replay: '<svg viewBox="0 0 24 24"><path d="M4 12a8 8 0 1 0 2.4-5.7M4 4v4h4"/></svg>',
};
document.querySelectorAll("[data-icon]").forEach(el => { el.innerHTML = ICON[el.dataset.icon] || ""; });
