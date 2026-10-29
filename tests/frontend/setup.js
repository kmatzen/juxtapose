// Do not swap `window` for a plain object here: script.js binds listeners to the real window at require time.

// script.js reads these at load time, so a tutorial-mode suite sets TUTORIAL_MODE before requiring it.
window.TUTORIAL_MODE = false;
window.tutorialCompleted = false;

// jsdom ships no IntersectionObserver; script.js only uses it to watch sections.
window.IntersectionObserver = class {
    observe() {}
    unobserve() {}
    disconnect() {}
};

global.console = {
    ...console,
    log: jest.fn(),
    debug: jest.fn(),
    info: jest.fn(),
    warn: jest.fn(),
    error: jest.fn(),
};
