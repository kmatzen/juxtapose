export type LoadedImage = { ok: true } | { ok: false };

/** Preload so a tile is committed only once its bytes decode. crossOrigin is load-bearing: a non-CORS image taints the canvas the mask overlays read from. */
export function preloadImage(url: string): Promise<LoadedImage> {
    return new Promise((resolve) => {
        const image = new Image();
        image.crossOrigin = 'anonymous';
        image.onload = () => resolve({ ok: true });
        image.onerror = () => resolve({ ok: false });
        image.src = url;
    });
}
