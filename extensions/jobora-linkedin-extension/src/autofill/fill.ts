/**
 * Low-level, React-safe form-filling primitives.
 *
 * LinkedIn (and most modern ATS forms) are React apps. Setting `el.value = x`
 * directly does NOT update React's internal state — React overrides the value
 * setter on the element instance. We must call the *prototype's* native setter
 * and then dispatch `input`/`change` so React's synthetic-event system picks it
 * up. This is the well-known "set native value" trick.
 *
 * Nothing here submits a form — it only fills fields. The submit decision always
 * stays with the user.
 */

type Fillable = HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement;

/** Set a value on an input/textarea/select so React registers the change. */
export function setNativeValue(el: Fillable, value: string): void {
  const proto = Object.getPrototypeOf(el);
  const protoSetter = Object.getOwnPropertyDescriptor(proto, 'value')?.set;
  const ownSetter = Object.getOwnPropertyDescriptor(el, 'value')?.set;

  if (protoSetter && ownSetter && ownSetter !== protoSetter) {
    protoSetter.call(el, value);
  } else if (protoSetter) {
    protoSetter.call(el, value);
  } else {
    (el as { value: string }).value = value;
  }
  el.dispatchEvent(new Event('input', { bubbles: true }));
  el.dispatchEvent(new Event('change', { bubbles: true }));
}

/** Select an <option> in a <select> by exact-or-fuzzy text or value. */
export function selectOption(select: HTMLSelectElement, wanted: string): boolean {
  const w = wanted.trim().toLowerCase();
  const opts = Array.from(select.options);
  // Exact value/text, then substring.
  const match =
    opts.find(o => o.value.trim().toLowerCase() === w || o.text.trim().toLowerCase() === w) ||
    opts.find(o => o.text.trim().toLowerCase().includes(w) && o.value !== '');
  if (!match) return false;
  setNativeValue(select, match.value);
  return true;
}

/** Click a radio/checkbox by its visible label text within a group container. */
export function clickChoice(container: Element, wantedLabel: string): boolean {
  const w = wantedLabel.trim().toLowerCase();
  const inputs = Array.from(
    container.querySelectorAll<HTMLInputElement>('input[type="radio"], input[type="checkbox"]'),
  );
  for (const input of inputs) {
    const label = labelTextFor(input).toLowerCase();
    if (label === w || label.startsWith(w)) {
      if (!input.checked) input.click();
      return true;
    }
  }
  return false;
}

/** True if an element is visible (fill only what the user can see). */
export function isVisible(el: Element): boolean {
  const r = (el as HTMLElement).getBoundingClientRect();
  if (r.width === 0 && r.height === 0) return false;
  const s = getComputedStyle(el as HTMLElement);
  return s.display !== 'none' && s.visibility !== 'hidden' && s.opacity !== '0';
}

/**
 * Best-effort visible label for a form control. Tries, in order:
 *   <label for>, wrapping <label>, aria-label, aria-labelledby, <legend>,
 *   the nearest preceding text node.
 */
export function labelTextFor(el: Element): string {
  const id = el.getAttribute('id');
  if (id) {
    const forLabel = el.ownerDocument.querySelector(`label[for="${CSS.escape(id)}"]`);
    if (forLabel?.textContent) return clean(forLabel.textContent);
  }
  const wrapping = el.closest('label');
  if (wrapping?.textContent) return clean(wrapping.textContent);

  const aria = el.getAttribute('aria-label');
  if (aria) return clean(aria);

  const labelledby = el.getAttribute('aria-labelledby');
  if (labelledby) {
    const parts = labelledby.split(/\s+/)
      .map(x => el.ownerDocument.getElementById(x)?.textContent ?? '')
      .join(' ');
    if (parts.trim()) return clean(parts);
  }

  // Radio/checkbox groups: the question is usually a <legend> or a heading in
  // the enclosing fieldset / grouping div.
  const fieldset = el.closest('fieldset');
  const legend = fieldset?.querySelector('legend');
  if (legend?.textContent) return clean(legend.textContent);

  // Fallback: walk up a couple of levels and grab the first meaningful text.
  let node: Element | null = el.parentElement;
  for (let i = 0; node && i < 4; i++, node = node.parentElement) {
    const label = node.querySelector('label, legend, .fb-dash-form-element__label, [class*="label"]');
    if (label?.textContent && !label.contains(el)) return clean(label.textContent);
  }
  return '';
}

function clean(s: string): string {
  return dedupeRepeat(s.replace(/\s+/g, ' ').replace(/\*/g, '').trim());
}

/**
 * Collapse an immediately-repeated label. LinkedIn often renders a visible
 * label plus a screen-reader copy of the same text, so `textContent` yields
 * "CityCity" or "City City". Return the single unit when the string is exactly
 * its first half repeated.
 */
function dedupeRepeat(s: string): string {
  if (!s) return s;
  // "CityCity" — no separator.
  for (let n = 1; n <= s.length / 2; n++) {
    if (s.length % n === 0 && s.slice(0, n).repeat(s.length / n) === s) return s.slice(0, n);
  }
  // "City City" — word-repeated.
  const words = s.split(' ');
  if (words.length % 2 === 0) {
    const half = words.length / 2;
    if (words.slice(0, half).join(' ') === words.slice(half).join(' ')) {
      return words.slice(0, half).join(' ');
    }
  }
  return s;
}
