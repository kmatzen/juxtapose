/**
 * Test setup and helper functions
 */

// Mock window.DEV_MODE
global.window = {
    DEV_MODE: false,
    TUTORIAL_MODE: false,
    tutorialCompleted: false,
    triggerFormValidation: jest.fn()
};

// Mock console methods to avoid cluttering test output
global.console = {
    ...console,
    log: jest.fn(),
    debug: jest.fn(),
    info: jest.fn(),
    warn: jest.fn(),
    error: jest.fn()
};

// Helper to create a mock DOM element
global.createMockElement = (type, attributes = {}) => {
    const element = document.createElement(type);
    Object.keys(attributes).forEach(key => {
        if (key === 'innerHTML') {
            element.innerHTML = attributes[key];
        } else {
            element.setAttribute(key, attributes[key]);
        }
    });
    return element;
};

// Helper to create mock form data
global.createMockFormData = () => ({
    better_image: 'A',
    image_confidence: '3',
    better_mask_match: 'B',
    mask_confidence: '4',
    better_identity_match: 'A',
    identity_confidence: '5',
    better_prompt_match: 'Equal',
    prompt_confidence: '2'
});

