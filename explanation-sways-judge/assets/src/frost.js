// Small line icons used by the images: <span data-icon="arrow"></span> gets the arrow.
const ICON = {
  arrow: '<svg viewBox="0 0 24 24"><path d="M7 17L17 7M9 7h8v8"/></svg>',
};
document.querySelectorAll("[data-icon]").forEach(el => { el.innerHTML = ICON[el.dataset.icon] || ""; });
