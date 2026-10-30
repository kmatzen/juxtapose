export type ImageLoader = {
    requested: string[];
    fail: (...substrings: string[]) => void;
    loadAll: () => void;
};

function install(loader: ImageLoader, fire: (img: FakeImage) => void): void {
    class FakeImage {
        onload: (() => void) | null = null;
        onerror: (() => void) | null = null;
        crossOrigin: string | null = null;
        width = 100;
        height = 100;
        naturalWidth = 100;
        naturalHeight = 100;
        complete = true;
        #src = '';

        get src(): string {
            return this.#src;
        }

        set src(value: string) {
            this.#src = value;
            loader.requested.push(value);
            Promise.resolve().then(() => fire(this));
        }
    }
    globalThis.Image = FakeImage as unknown as typeof Image;
    window.Image = FakeImage as unknown as typeof Image;
}

/** Eager by default; `manual` holds decode so a test can look at the page while images are in flight. */
export function imageLoader({ manual = false }: { manual?: boolean } = {}): ImageLoader {
    const loader: ImageLoader = { requested: [], fail: () => {}, loadAll: () => {} };
    const failing: string[] = [];
    const pending: FakeImage[] = [];

    const fire = (img: FakeImage): void => {
        if (failing.some((match) => img.src.includes(match))) img.onerror?.();
        else img.onload?.();
    };

    install(loader, (img) => {
        if (manual) pending.push(img);
        else fire(img);
    });

    loader.fail = (...substrings) => void failing.push(...substrings);
    loader.loadAll = () => pending.splice(0).forEach(fire);
    return loader;
}

type FakeImage = { src: string; onload: (() => void) | null; onerror: (() => void) | null };
