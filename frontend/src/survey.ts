// script.js stays a classic script (inline handlers need globals), so the core reaches it on window.
import * as studyState from './study-state';

declare global {
  interface Window {
    JX: typeof studyState;
  }
}

window.JX = studyState;
document.documentElement.dataset.build = 'vite';
