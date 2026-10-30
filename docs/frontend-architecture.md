# Frontend architecture

The survey page is a component tree: typed TypeScript modules, one mount point each, no globals.
`admin.ts` already works this way; this document is the target for the survey page and the ledger
of the migration that gets there.

## Layers

| Layer | Rule | Lives in |
|---|---|---|
| **Model** | Pure functions. No DOM, no `fetch`, no `window`. Every study rule (visibility, response shape, progress, completeness, UA parsing) is here, so it is testable without a browser. | `frontend/src/study-state.ts` |
| **Services** | The only modules that touch `fetch`, `location`, `navigator`, `screen`. A fake implementation is passed in, so components never mock a global. | `frontend/src/lib/` |
| **Components** | Own a slice of DOM: mount into a host, read config through props, publish effects through callbacks, expose `dispose()`. Query inside their host, never `document`. | `frontend/src/components/` |
| **Entry** | Wires services to components, decides which section runs, owns the trial flow. The only module that runs on load. | `frontend/src/survey.ts` |

Dependencies point down: component → service → model. The model imports nothing.

## Component contract

```ts
export type Disposable = { dispose(): void };

export function mountThing(host: HTMLElement, props: ThingProps): Thing & Disposable;
```

- **Host-scoped DOM.** `mountX(host, props)` queries inside `host` only. A component that reaches
  for `document.getElementById` cannot be mounted twice, and cannot be tested in isolation.
- **Props in, effects out.** Config and data arrive as props; anything the component wants to
  happen to the world (navigate, submit, ask the participant) is a callback in `props`.
- **No globals.** No `window.openLightbox`, no `window.TUTORIAL_MODE`, no `window.JX`, no inline
  `onclick` in the template. `index.html` renders structure; behaviour is attached in code.
- **`dispose()` detaches everything** the mount added: listeners, timers, observers, nodes.
- **Text goes through `textContent`.** Data (server rows, participant input, image captions)
  reaches the page via `el()`/`textContent` only; the string-building version needed escaping at
  ~20 call sites and shipped an XSS in the admin table.

## Components

| Component | Owns | Replaces |
|---|---|---|
| `error-banner` | one dismissible banner, auto-hide timer | `showError` |
| `retake-modal` | the retake decision, scroll lock, promise result | `showRetakeModal` |
| `lightbox` | full-size image view, close on backdrop/Esc | `setupImageLightbox`, `window.openLightbox` |
| `tutorial-banner` | step banner, progress ring, highlights, scroll-to | the `window.TUTORIAL_MODE` block |
| `demographics-form` | form submit, retake handshake, device info render | `fillDemographicsForm`, `handleDemographicsSubmit`, `collectDeviceInfo` display |
| `stimulus-view` | prompt, A/B images, preload, loading state, progress bar, timing | `loadImagePair` |
| `conditioning-gallery` | identity tiles (comma list or stacked slice), mask tile | `displayConditioningInputs`, `loadStackedGallery`, `clearConditioningTiles` |
| `mask-overlay` | identity hover/tap overlays on the output images | `processMaskForOverlays`, `createOverlay`, hover/touch handlers |
| `question-sections` | visibility, progressive nav, auto-advance, submit enabling | `initializeProgressiveQuestions` + `setupSubmitValidation` + `setupAutoAdvance` + nav/scroll |
| `layout-metrics` (lib) | height budget, image scaling, orientation changes | `measureLayout`, `setQuestionsHeight`, `scaleVisualContent`, resize handler |
| `trial-runner` (lib) | index, current pair, per-pair timing, submit → next | the `currentImageIndex` / `pairStartTime` / submit flow |
| `session-api` (lib) | typed `fetch` + CSRF | every inline `fetch` and `getCSRFToken` |

### Fidelity contract

This page is a research instrument, so these behaviours are the spec. Each is asserted somewhere:

1. Both A/B images are preloaded with `crossOrigin=anonymous` and only then assigned to `src` —
   the mask canvas needs CORS (`stimulus-view`, playwright).
2. The form is input-blocked while a pair loads, so a participant cannot answer against images
   that are not on screen (`stimulus-view`, playwright).
3. Per-pair timing starts when both images are ready, not at fetch time (`trial-runner`, unit).
4. Conditioning tiles are cleared between trials: a leftover mask paints overlays from pixels the
   current trial does not have (`conditioning-gallery`, component).
5. A comma-separated gallery is N images carrying `data-identity-index`; a lone URL is one stacked
   sheet sliced into squares (`conditioning-gallery`, component).
6. Mask regions match identity colours within tolerance 10 and overlay at mask resolution,
   CSS-scaled (`mask-scan` unit + deterministic screenshot).
7. Layout recomputes on orientation change and >100px width change only, 250ms debounce: mobile
   URL-bar height changes must not rescale the stimuli (`layout-metrics`, unit).
8. Submit enables only when every visible question group is answered; hidden sections are excluded
   (`study-state.isFormComplete` + `question-sections`, component).

## Testing

| Level | Runner | Covers |
|---|---|---|
| Unit | vitest | model, services (fake `fetch`), pure extraction (mask scan, tutorial steps, layout math) |
| Component | vitest + jsdom | one component: mount into a fixture host, interact, assert DOM + callbacks |
| Integration | playwright | the real page against the real Flask fixture server: flow, images, touch, mobile, dashboard |
| Visual | playwright | `docs/screenshots/*.png`, pixel-identical across runs on a quiet runner; the specs assert the A/B and identity placement, so a shifted draw fails the run instead of drifting an image, and PNG bytes can still differ because the encoder's compression varies |

`frontend/test/helpers/` carries the harness: `surveyFixture()` (a DOM mirror of `index.html`),
`mount()` (mount + auto-dispose), `fakeApi()` (routes → responses), `imageLoader()` (eager, manual
or failing image loads), `flush()`.

**One runner.** Jest, `babel-jest`, the babel config, the CommonJS copy of the model and the
9 suites that drove `script.js` were deleted with the file they served. What they covered is
component coverage now, on the code the page actually runs.

## Migration ledger

Strangler: one component per commit, every commit green (`typecheck`, vitest, playwright, pytest),
`script.js` shrinking to nothing.

| # | Step | `script.js` lines |
|---|---|---|
| 1 | harness: `lib/dom`, `session-api`, `device-info`, `tutorial-steps`, test helpers | 1650 |
| 2 | `error-banner`, `retake-modal`, `lightbox` | 1567 |
| 3 | `tutorial-banner` (last inline handler leaves `index.html`) | 1386 |
| 4 | `demographics-form` | 1318 |
| 5 | `stimulus-view` (+ `lib/image-loader`) | 1206 |
| 6 | `conditioning-tiles` (+ mask scan, overlay, stacked slicing in `study-state`) | 783 |
| 7 | `question-flow` (+ `lib/layout`) | 448 |
| 8 | `trial-runner`, `device-panel`, `lib/dev-autofill`; delete `script.js`, jest, babel, the CommonJS shim, `seam.ts` | 0 |

During steps 2–7 the shrinking `script.js` drove the extracted components through one narrow seam,
`window.__JX__`. It was a migration seam, not architecture: typed, documented here, and deleted
with the file that read it. `index.html` now loads one module bundle and nothing else.
