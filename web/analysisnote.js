// Short analysis labels with optional evidence and uncertainty. One hint open at a time.
import { el } from './util.js';
let serial = 0, active = null;

function closeActive() { active?.close(); }
document.addEventListener('pointerdown', (e) => { if (active && !active.root.contains(e.target)) closeActive(); });
document.addEventListener('keydown', (e) => {
  if (e.key === 'Escape' && active) { closeActive(); e.preventDefault(); e.stopPropagation(); }
}, true);
window.addEventListener('resize', closeActive);
document.addEventListener('scroll', (e) => { if (active && !active.detail.contains(e.target)) closeActive(); }, true);

export function analysisNote(brief, explanation, className = 'small') {
  const id = `analysis-detail-${++serial}`;
  const button = el('button', { type: 'button', class: 'analysis-label', 'aria-expanded': 'false',
    'aria-controls': id, 'aria-describedby': id }, brief, el('span', { class: 'analysis-info', 'aria-hidden': 'true' }, ' ⓘ'));
  const detail = el('span', { id, class: 'analysis-detail', role: 'tooltip', popover: 'manual' }, explanation);
  detail.hidden = true;
  const root = el('span', { class: `analysis-note ${className}` }, button, detail);
  let pinned = false;
  const close = () => {
    pinned = false;
    if (detail.isConnected) detail.hidePopover?.();
    detail.hidden = true;
    button.setAttribute('aria-expanded', 'false');
    if (active?.root === root) active = null;
  };
  const show = () => {
    if (active?.root !== root) closeActive();
    active = { root, detail, close };
    detail.hidden = false;
    detail.showPopover?.();
    button.setAttribute('aria-expanded', 'true');
    const rect = button.getBoundingClientRect();
    const vw = document.documentElement.clientWidth, vh = window.innerHeight;
    detail.style.maxWidth = `${Math.max(120, Math.min(360, vw - 24))}px`;
    const width = detail.offsetWidth, height = detail.offsetHeight;
    detail.style.left = `${Math.max(12, Math.min(rect.left, vw - width - 12))}px`;
    detail.style.top = `${rect.bottom + height + 12 < vh ? rect.bottom + 6 : Math.max(8, rect.top - height - 6)}px`;
  };
  root.addEventListener('pointerenter', show);
  root.addEventListener('pointerleave', () => { if (!pinned && !root.contains(document.activeElement)) close(); });
  root.addEventListener('focusin', show);
  root.addEventListener('focusout', (e) => { if (!root.contains(e.relatedTarget)) close(); });
  button.addEventListener('click', () => { pinned = !pinned; if (pinned) show(); else close(); });
  return root;
}
