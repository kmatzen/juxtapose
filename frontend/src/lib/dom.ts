// Deliberately small: a component needing more DOM plumbing is doing rendering the template should own.

export type Attrs = Record<string, string | number | boolean | null | undefined>;

export type Disposable = { dispose(): void };

export function el<K extends keyof HTMLElementTagNameMap>(
    tag: K,
    attrs: Attrs = {},
    ...children: (Node | string)[]
): HTMLElementTagNameMap[K] {
    const node = document.createElement(tag);
    for (const [name, value] of Object.entries(attrs)) {
        if (value === null || value === undefined || value === false) continue;
        node.setAttribute(name, value === true ? '' : String(value));
    }
    node.append(...children);
    return node;
}

export function qa<T extends Element>(root: ParentNode, selector: string): T[] {
    return Array.from(root.querySelectorAll<T>(selector));
}

// jsdom has no CSS.escape, and ids here are config slugs: escape the few characters that can appear.
const escapeId = (id: string): string => id.replace(/[^\w-]/g, (c) => `\\${c}`);

export function byId<T extends HTMLElement = HTMLElement>(root: ParentNode, id: string): T | null {
    return root.querySelector<T>(`#${escapeId(id)}`);
}

// Fails at mount, not at first render, when template and component disagree about an id.
export function need<T extends HTMLElement = HTMLElement>(
    root: ParentNode,
    selector: string,
): T {
    const found = root.querySelector<T>(selector);
    if (!found) throw new Error(`missing element: ${selector}`);
    return found;
}

// Hands back the detach so a component can bank cleanups for dispose().
export function on(
    node: EventTarget,
    type: string,
    handler: (event: Event) => void,
    options?: AddEventListenerOptions,
): () => void {
    node.addEventListener(type, handler, options);
    return () => node.removeEventListener(type, handler, options);
}

export function toggleClass(node: Element, name: string, on: boolean): void {
    node.classList.toggle(name, on);
}

export function empty(node: Element): void {
    node.replaceChildren();
}

/** Escape text destined for an innerHTML assignment. */
export function escapeHtml(value: string): string {
    return value
        .replaceAll('&', '&amp;')
        .replaceAll('<', '&lt;')
        .replaceAll('>', '&gt;')
        .replaceAll('"', '&quot;')
        .replaceAll("'", '&#39;');
}
