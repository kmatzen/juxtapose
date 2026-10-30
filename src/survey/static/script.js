// Configuration Constants
const CONFIG = {
    // Touch interaction
    TAP_THRESHOLD_PX: 10,          // Max movement distance to count as tap (not scroll)

    // Timing
    AUTO_FILL_DELAY_MS: 500,        // Delay before auto-filling forms in dev mode
    IMAGE_PRELOAD_DELAY_MS: 100     // Delay before auto-filling survey in dev mode
};

// A module script runs after this classic one parses, so the seam is read on first use, not here.
// The jsdom suites have no seam and get the CJS build of the same module.
let coreModule = null;
function core() {
    if (!coreModule) {
        const mounted = typeof window !== 'undefined' && window.__JX__ ? window.__JX__.core : null;
        coreModule = mounted || (typeof require === 'function' ? require('../../../frontend/.cjs/study-state.cjs') : null);
    }
    if (!coreModule) {
        throw new Error('study-state is not loaded: run npm run build');
    }
    return coreModule;
}

// State management
let surveyConfig = null;   // Full config from /api/config
let demographicsData = null;
let currentImageIndex = 0;
let currentImageData = null;
let totalImagePairs = 30;

let devMode = false;
let pairStartTime = null;  // Track when user starts viewing current pair

// Initialize
document.addEventListener('DOMContentLoaded', async function() {
    await checkDevMode();
    collectDeviceInfo();
    await checkDemographicsSubmitted();
    setupEventListeners();
});

// Recalculate heights only on orientation change or significant resize
let resizeTimeout;
let lastWidth = window.innerWidth;
let lastOrientation = window.innerWidth > window.innerHeight ? 'landscape' : 'portrait';

window.addEventListener('resize', () => {
    clearTimeout(resizeTimeout);
    resizeTimeout = setTimeout(() => {
        if (questionSections.length === 0) return;
        
        const currentWidth = window.innerWidth;
        const currentHeight = window.innerHeight;
        const currentOrientation = currentWidth > currentHeight ? 'landscape' : 'portrait';
        
        // Only recalculate if orientation changed or significant width change (not height!)
        // Height changes from mobile chrome hiding/showing should be ignored
        const widthChange = Math.abs(currentWidth - lastWidth);
        const orientationChanged = currentOrientation !== lastOrientation;
        
        if (orientationChanged || widthChange > 100) {
            lastWidth = currentWidth;
            lastOrientation = currentOrientation;
            setQuestionsHeight();
        }
    }, 250);
});

async function checkDevMode() {
    try {
        const response = await fetch('/api/config');
        surveyConfig = await response.json();
        devMode = surveyConfig.dev_mode;

        if (devMode) {
            console.log('DEV MODE ENABLED - Forms will be auto-filled');
            // Add a visible indicator
            const indicator = document.createElement('div');
            indicator.style.cssText = 'position: fixed; top: 10px; right: 10px; background: #ff6b6b; color: white; padding: 10px 15px; border-radius: 5px; z-index: 10000; font-weight: bold; box-shadow: 0 2px 5px rgba(0,0,0,0.2);';
            indicator.textContent = 'DEV MODE';
            document.body.appendChild(indicator);
        }
    } catch (error) {
        console.error('Error checking dev mode:', error);
    }
}

async function checkDemographicsSubmitted() {
    try {
        const response = await fetch('/api/check_demographics');
        const data = await response.json();
        
        if (data.submitted) {
            // Demographics already submitted - skip to survey section
            const demographicsSection = document.getElementById('demographics-section');
            const surveySection = document.getElementById('survey-section');
            
            if (demographicsSection && surveySection) {
                demographicsSection.classList.remove('active');
                surveySection.classList.add('active');
                
                // Show survey progress bar
                document.getElementById('survey-progress').style.display = 'block';
                
                // The server already left finished trials out of this session's list.
                await loadImagePair(0);
            }
        }
    } catch (error) {
        console.error('Error checking demographics:', error);
    }
}

function collectDeviceInfo() {
    const ua = navigator.userAgent;
    const { browser, browserVersion } = core().detectBrowser(ua);
    const os = core().detectOs(ua, navigator.maxTouchPoints);
    
    const info = {
        browser: browser,
        browser_version: browserVersion,
        os: os,
        screen_width: screen.width,
        screen_height: screen.height,
        pixel_ratio: window.devicePixelRatio || 1,
        color_depth: screen.colorDepth,
        viewport_width: window.innerWidth,
        viewport_height: window.innerHeight
    };
    
    // Display info to user (only if elements exist - they're only on demographics page).
    // What gets POSTed is collected by frontend/src/lib/device-info.ts at boot.
    const browserElement = document.getElementById('user-browser');
    const osElement = document.getElementById('user-os');
    const screenElement = document.getElementById('user-screen');
    const pixelRatioElement = document.getElementById('user-pixel-ratio');
    const colorElement = document.getElementById('user-color');
    
    if (browserElement) browserElement.textContent = `${browser} ${browserVersion}`;
    if (osElement) osElement.textContent = os;
    if (screenElement) screenElement.textContent = `${screen.width} × ${screen.height}px`;
    if (pixelRatioElement) pixelRatioElement.textContent = `${window.devicePixelRatio || 1}x`;
    if (colorElement) colorElement.textContent = screen.colorDepth;
}

// The component tree loads the stimulus tiles and reports the pair. The conditioning tiles and the
// hover overlays are still script.js (step 6 of the architecture doc), so their state resets here.
document.addEventListener('jx:trial-loaded', (event) => {
    window.__JX__.conditioning.show(event.detail);
    updateQuestionVisibility(event.detail);
});

document.addEventListener('jx:stimulus-settled', (event) => {
    if (event.detail.ok) pairStartTime = Date.now();
});

function setupEventListeners() {
    // The intake form is wired by the component tree; dev auto-fill rides on the same element.
    const demographicsForm = document.getElementById('demographics-form');
    if (demographicsForm && devMode) {
        setTimeout(() => fillDemographicsForm(), CONFIG.AUTO_FILL_DELAY_MS);
    }

    // Survey form submission
    const surveyForm = document.getElementById('survey-form');
    if (surveyForm) {
        surveyForm.addEventListener('submit', handleSurveySubmit);
    } else {
        console.error('Survey form not found during setup');
    }
    
}

function fillDemographicsForm() {
    // Auto-fill demographics form from config
    if (!surveyConfig || !surveyConfig.demographics) return;

    for (const field of surveyConfig.demographics) {
        const el = document.getElementById(field.name);
        if (!el) continue;

        if (field.type === 'email') {
            el.value = 'test@example.com';
        } else if (field.type === 'text' || field.type === 'textarea') {
            el.value = 'test';
        } else if (field.type === 'number') {
            el.value = '0';
        } else if (field.type === 'select') {
            if (field.options && field.options.length) {
                el.value = field.options[0].value;
            }
        } else if (field.type === 'radio') {
            if (field.options && field.options.length) {
                const r = document.querySelector(`input[name="${field.name}"][value="${field.options[0].value}"]`);
                if (r) r.checked = true;
            }
        } else if (field.type === 'checkbox') {
            if (field.options && field.options.length) {
                // Check up to first 3 checkboxes
                field.options.slice(0, 3).forEach(opt => {
                    const c = document.querySelector(`input[name="${field.name}[]"][value="${opt.value}"]`);
                    if (c) c.checked = true;
                });
            }
        }
    }

    // Auto-check consent checkbox if present
    const consent = document.querySelector('input[name="consent"]');
    if (consent) consent.checked = true;
}

function fillSurveyForm() {
    if (!surveyConfig || !surveyConfig.questions) return;

    for (const q of surveyConfig.questions) {
        const section = document.getElementById(`${q.name}-evaluation`);
        if (!section || section.style.display === 'none') continue;

        if (q.type === 'ab_preference') {
            const v = Math.random() < 0.5 ? 'A' : 'B';
            const r = section.querySelector(`input[name="${q.name}_choice"][value="${v}"]`);
            if (r) r.checked = true;
            if (q.confidence) {
                const c = Math.floor(Math.random() * 5) + 1;
                const cr = section.querySelector(`input[name="${q.name}_confidence"][value="${c}"]`);
                if (cr) cr.checked = true;
            }
        } else if (q.type === 'likert') {
            const scale = q.scale || 5;
            const v = Math.floor(Math.random() * scale) + 1;
            const r = section.querySelector(`input[name="${q.name}_value"][value="${v}"]`);
            if (r) r.checked = true;
        } else if (q.type === 'free_text') {
            const ta = section.querySelector(`textarea[name="${q.name}_text"]`);
            if (ta) ta.value = 'test response';
        } else if (q.type === 'multiple_choice') {
            const opts = section.querySelectorAll(`input[name="${q.name}_value"]`);
            if (opts.length) opts[0].checked = true;
        }
    }

    // Trigger form validation to enable submit button
    if (window.triggerFormValidation) {
        window.triggerFormValidation();
    }
}

async function loadImagePair(index) {
    try {
        const response = await fetch(`/api/get_image_pair/${index}`);
        const data = await response.json();

        if (response.ok) {
            currentImageData = data;
            currentImageIndex = index;
            
            // The tiles own the preload, the loading indicators, the form blocking and the
            // image-error banner; conditioning resets ride the same event the tiles fire.
            await window.__JX__.stimulus.show(data);

            const progress = core().progressFrom(data, index);
            document.getElementById('current-question').textContent = progress.current;
            document.getElementById('total-questions').textContent = progress.total;
            totalImagePairs = progress.total;
            
            // Update instruction text with actual number of pairs (only on first load)
            if (index === 0) {
                const pairWord = data.total_pairs === 1 ? 'pair' : 'pairs';
                document.getElementById('total-pairs-text').textContent = 
                    `You will see ${data.total_pairs} image ${pairWord} in total.`;
            }
            
            document.getElementById('progress-bar-fill').style.width = progress.percent + '%';
            
            // Reset form
            document.getElementById('survey-form').reset();
            
            // Disable submit button until questions are answered
            const submitBtn = document.getElementById('submit-btn');
            if (submitBtn) {
                submitBtn.disabled = true;
            }
            
            // Reinitialize progressive questions for new image pair
            // Reset to first question
            currentQuestionIndex = 0;
            
            initializeProgressiveQuestions();
            
            // Reset scroll position to the first question
            const questionsContainer = document.querySelector('.questions-container');
            if (questionsContainer) {
                questionsContainer.scrollTop = 0;
            }
            
            // Auto-fill in dev mode
            if (devMode) {
                setTimeout(() => fillSurveyForm(), CONFIG.IMAGE_PRELOAD_DELAY_MS);
            }
            
        } else {
            if (response.status === 404) {
                // Nothing owed on this session; the index route serves the thank-you screen.
                window.location.href = '/';
                return;
            }
            showError('Failed to load image pair. Please refresh the page.');
            console.error('Error:', data.error);
        }
    } catch (error) {
        showError('Network error. Please check your connection.');
        console.error('Error:', error);
    }
}

async function handleSurveySubmit(event) {
    event.preventDefault();

    // If in tutorial mode, mark tutorial complete and redirect to real survey
    if (window.__JX__ && window.__JX__.tutorial) {
        // Mark tutorial as complete in session
        try {
            await fetch('/api/complete_tutorial', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': getCSRFToken()
                }
            });
        } catch (error) {
            // Marking the tutorial complete is best-effort; the redirect is the point.
        }
        
        // Redirect to real survey
        window.location.href = '/';
        return;
    }

    const formData = new FormData(event.target);
    const surveyResponse = Object.fromEntries(formData.entries());

    // Calculate time spent on this pair (in seconds)
    const timeSpent = pairStartTime ? (Date.now() - pairStartTime) / 1000 : null;

    // Section visibility is a DOM fact here; the rules that made it so live in the core.
    const visibleNames = (surveyConfig ? surveyConfig.questions : [])
        .filter(q => {
            const section = document.getElementById(`${q.name}-evaluation`);
            return section && section.style.display !== 'none';
        })
        .map(q => q.name);

    const responses = core().buildResponses(
        surveyConfig ? surveyConfig.questions : [], surveyResponse, visibleNames);
    const completeResponse = core().buildSubmission(currentImageData, responses, timeSpent);
    
    try {
        const response = await fetch('/api/submit_survey', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCSRFToken()
            },
            body: JSON.stringify(completeResponse)
        });
        
        const result = await response.json();
        
        if (response.ok && result.success) {
            if (result.completed) {
                // All image pairs completed, redirect to thank you page
                window.location.href = '/';
            } else {
                // Load next image pair
                currentImageIndex++;
                await loadImagePair(currentImageIndex);
                window.scrollTo(0, 0);
            }
        } else {
            showError('Failed to submit response. Please try again.');
            console.error('Error:', result.error);
        }
    } catch (error) {
        showError('Network error. Please check your connection and try again.');
        console.error('Error:', error);
    }
}

function showRetakeModal() {
    // Fail closed: with no components mounted the answer to "overwrite my data?" is no.
    return window.__JX__ ? window.__JX__.retake.ask() : Promise.resolve(false);
}

function updateQuestionVisibility(data) {
    // Show/hide questions based on depends_on and available data
    if (!surveyConfig || !surveyConfig.questions) return;
    for (const q of surveyConfig.questions) {
        const el = document.getElementById(`${q.name}-evaluation`);
        if (!el) continue;
        const visible = core().isSectionVisible(q, data, surveyConfig.inputs || []);
        el.style.display = visible ? 'block' : 'none';
        if (!visible) {
            el.querySelectorAll('input[required]').forEach(i => i.removeAttribute('required'));
        }
    }
}

// The components own this UI (frontend/src/components); the seam is seam.ts. Without it the
// message is logged, never shown: a page with no component tree cannot ask the participant to retry.
function showError(message) {
    if (!window.__JX__) {
        console.error('Unshown message:', message);
        return;
    }
    window.__JX__.banner.show(message);
}

function openLightbox(src, caption) {
    if (!window.__JX__) {
        console.error('Lightbox is not mounted');
        return;
    }
    window.__JX__.lightbox.open(src, caption);
}

// ==================================================================
// PROGRESSIVE QUESTION FLOW
// ==================================================================

let currentQuestionIndex = 0;
let questionSections = [];

function initializeProgressiveQuestions() {
    // Get all evaluation sections (4 total: image quality, prompt, mask, identity)
    questionSections = Array.from(document.querySelectorAll('.questions-container .evaluation-section'));
    
    if (questionSections.length === 0) return;
    
    // Show all questions at once
    questionSections.forEach(section => section.classList.add('active'));
    currentQuestionIndex = 0;
    
    // Dynamically size the questions section to fit one full question
    setQuestionsHeight();
    
    // Set up navigation buttons
    const prevBtn = document.getElementById('prev-question-btn');
    const nextBtn = document.getElementById('next-question-btn');
    
    prevBtn.addEventListener('click', () => navigateQuestion(-1));
    nextBtn.addEventListener('click', () => navigateQuestion(1));
    
    // Update initial button states
    updateNavigationButtons();
    
    // Track scroll position to update progress indicator
    setupScrollTracking();
    
    // Set up validation for submit button
    setupSubmitValidation();
    
    // Set up auto-advance when question group is complete
    setupAutoAdvance();
}

function measureLayout() {
    const container = document.querySelector('.container');
    const progressContainer = document.querySelector('.progress-container');
    const visualSection = document.querySelector('.visual-content-section');
    const promptBox = visualSection?.querySelector('.prompt-box');
    const sectionTitles = visualSection?.querySelectorAll('.section-title');
    const conditioningSections = visualSection?.querySelectorAll('.conditioning-section');
    
    const vh = window.innerHeight;
    const vw = window.innerWidth;
    const isLandscape = vw > vh;
    const isMobile = vw <= 768;
    const isMobileLandscape = isMobile && isLandscape;
    
    // Measure container padding
    const cStyle = getComputedStyle(container);
    const mainContainerPaddingTop = parseFloat(cStyle.paddingTop);
    const mainContainerPaddingBottom = parseFloat(cStyle.paddingBottom);
    
    // Measure visual section margins
    const vStyle = getComputedStyle(visualSection);
    const visualMarginTop = parseFloat(vStyle.marginTop);
    const visualMarginBottom = parseFloat(vStyle.marginBottom);
    
    // Measure progress height
    const progressHeight = progressContainer.offsetHeight;
    
    // Measure prompt and headers for visual section
    let promptHeight = promptBox ? promptBox.offsetHeight : 0;
    let titlesHeight = 0;
    if (sectionTitles) sectionTitles.forEach(t => titlesHeight += t.offsetHeight);
    
    let conditioningMargins = 0;
    if (conditioningSections && conditioningSections.length > 0) {
        const csStyle = getComputedStyle(conditioningSections[0]);
        conditioningMargins = parseFloat(csStyle.marginTop) + parseFloat(csStyle.marginBottom);
    }
    
    return {
        vh, vw, isLandscape, isMobile, isMobileLandscape,
        visualSection,
        mainContainerPaddingTop, mainContainerPaddingBottom,
        visualMarginTop, visualMarginBottom, progressHeight,
        promptHeight, titlesHeight, conditioningMargins
    };
}

function setQuestionsHeight() {
    if (questionSections.length === 0) return;
    
    const questionsSection = document.querySelector('.questions-section');
    if (!questionsSection) return;
    
    // Measure the height of ONE question
    const firstQuestion = questionSections[0];
    if (!firstQuestion) return;
    
    const oneQuestionHeight = firstQuestion.offsetHeight;
    
    // Set max-height to 150% of one question
    const finalHeight = Math.floor(oneQuestionHeight * 1.5);
    questionsSection.style.height = 'auto';
    questionsSection.style.maxHeight = `${finalHeight}px`;
    
    // Get measurements for visual section
    const m = measureLayout();
    if (!m) return;
    
    // Calculate space left for visual
    const mainContainerPadding = m.mainContainerPaddingTop + m.mainContainerPaddingBottom;
    const visualMargins = m.visualMarginTop + m.visualMarginBottom;
    const overhead = m.progressHeight + mainContainerPadding + visualMargins;
    const availableVisualHeight = m.vh - finalHeight - overhead;
    
    // Update cached viewport
    lastWidth = m.vw;
    lastOrientation = m.isLandscape ? 'landscape' : 'portrait';
    
    scaleVisualContent(availableVisualHeight, m);
}

function scaleVisualContent(availableHeight, m) {
    // Visual section now flows naturally without height constraints
    const visualSection = m.visualSection;
    
    if (visualSection) {
        visualSection.style.maxHeight = 'none';
        visualSection.style.minHeight = 'auto';
    }
    
    // Calculate space for images based on viewport
    const promptAndHeaderSpace = m.promptHeight + m.titlesHeight + m.conditioningMargins + 40;
    const availableImageSpace = m.vh * 0.5; // Use 50% of viewport for images
    const maxImageHeight = Math.floor(availableImageSpace * 0.8);
    
    // Apply to tile images (generated images and mask in three-tile-grid)
    const tileImages = m.visualSection.querySelectorAll('.tile-image');
    tileImages.forEach(img => {
        img.style.maxHeight = `${Math.max(maxImageHeight, 200)}px`;
        img.style.width = 'auto';
        img.style.height = 'auto';
        img.style.objectFit = 'contain';
    });
    
    // Apply to identity images
    const smallImageHeight = Math.floor(availableImageSpace / 3);
    const identityImages = m.visualSection.querySelectorAll('.identity-image, .identity-stacked-image');
    
    identityImages.forEach(img => {
        img.style.maxHeight = `${smallImageHeight}px`;
        img.style.minWidth = '50px';
        img.style.minHeight = '50px';
        img.style.width = 'auto';
        img.style.objectFit = 'contain';
    });
}

function navigateQuestion(direction) {
    const newIndex = currentQuestionIndex + direction;
    
    if (newIndex >= 0 && newIndex < questionSections.length) {
        currentQuestionIndex = newIndex;
        
        // Scroll within the questions container
        const container = document.querySelector('.questions-container');
        const targetSection = questionSections[newIndex];
        const containerRect = container.getBoundingClientRect();
        const sectionRect = targetSection.getBoundingClientRect();
        
        // Calculate scroll position relative to container
        const scrollOffset = sectionRect.top - containerRect.top + container.scrollTop;
        
        container.scrollTo({
            top: scrollOffset,
            behavior: 'smooth'
        });
        
        updateNavigationButtons();
    }
}

function updateNavigationButtons() {
    const prevBtn = document.getElementById('prev-question-btn');
    const nextBtn = document.getElementById('next-question-btn');
    
    // Disable prev button on first question
    prevBtn.disabled = (currentQuestionIndex === 0);
    
    // Disable next button on last question
    nextBtn.disabled = (currentQuestionIndex === questionSections.length - 1);
}

function setupScrollTracking() {
    // Update navigation buttons when user scrolls within questions container
    const container = document.querySelector('.questions-container');
    
    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting && entry.intersectionRatio > 0.3) {
                const index = questionSections.indexOf(entry.target);
                if (index !== -1) {
                    currentQuestionIndex = index;
                    updateNavigationButtons();
                }
            }
        });
    }, {
        root: container, // Observe within the container, not the viewport
        threshold: [0.3],
        rootMargin: '-50px 0px -50px 0px'
    });
    
    questionSections.forEach(section => observer.observe(section));
}

// Auto-advance removed - user scrolls through all visible questions

function isQuestionGroupComplete(questionIndex) {
    const section = questionSections[questionIndex];
    if (!section) return false;
    // A text-only section has nothing to answer, so it counts as complete.
    return core().isFormComplete(
        Array.from(section.querySelectorAll('input[type="radio"]')).map(radio => ({
            name: radio.name, checked: radio.checked, hidden: false,
        })),
        true);
}

function isInHiddenSection(el) {
    const section = el.closest('.evaluation-section');
    return !!section && section.style.display === 'none';
}

function setupSubmitValidation() {
    const submitBtn = document.getElementById('submit-btn');
    const surveyForm = document.getElementById('survey-form');
    
    if (!submitBtn || !surveyForm) return;
    
    // Function to check if all questions are answered
    function validateForm() {
        const allAnswered = core().isFormComplete(
            Array.from(surveyForm.querySelectorAll('input[type="radio"]')).map(radio => ({
                name: radio.name,
                checked: radio.checked,
                hidden: isInHiddenSection(radio),
            })));

        // Enable/disable submit button
        // In tutorial mode, keep disabled until tutorial is complete
        if (tutorialBlocksSubmit()) {
            submitBtn.disabled = true;
            submitBtn.title = 'Complete the tutorial first';
        } else {
            submitBtn.disabled = !allAnswered;
            submitBtn.title = '';
        }
        
        return allAnswered;
    }
    
    // Make validateForm globally accessible for tutorial mode
    window.triggerFormValidation = validateForm;
    document.addEventListener('jx:tutorial-complete', () => validateForm());
    
    // Listen for changes on all radio inputs
    surveyForm.addEventListener('change', (e) => {
        if (e.target.type === 'radio') {
            validateForm();
        }
    });
    
    // Initial validation
    validateForm();
}

function setupAutoAdvance() {
    // Listen for radio button changes and auto-advance when question group is complete
    questionSections.forEach((section, index) => {
        const inputs = section.querySelectorAll('input[type="radio"]');
        
        inputs.forEach(input => {
            input.addEventListener('change', () => {
                // Check if this question group is complete
                if (isQuestionGroupComplete(index)) {
                    // Small delay to let user see their selection
                    setTimeout(() => {
                        // If we're still on this question
                        if (currentQuestionIndex === index) {
                            if (index < questionSections.length - 1) {
                                // Advance to next question
                                navigateQuestion(1);
                            } else {
                                // Last question - scroll to reveal submit button
                                const submitBtn = document.getElementById('submit-btn');
                                if (submitBtn) {
                                    submitBtn.scrollIntoView({ behavior: 'smooth', block: 'center' });
                                }
                            }
                        }
                    }, 500);
                }
            });
        });
    });
}

// Initialize progressive questions when survey section loads
// This is now handled in loadImagePair() to avoid MutationObserver overhead

// ==================================================================
// HELPER FUNCTIONS
// ==================================================================

// The walkthrough lives in the component tree; it is what gates Submit, and it finishes
// asynchronously, so completion arrives as a DOM event the form re-validates against.
function tutorialBlocksSubmit() {
    const tutorial = window.__JX__ && window.__JX__.tutorial;
    return !!tutorial && !tutorial.isComplete();
}

function getCSRFToken() {
    // Try to get CSRF token from meta tag (if it exists)
    const metaTag = document.querySelector('meta[name="csrf-token"]');
    if (metaTag) {
        return metaTag.content;
    }
    // Try cookie
    const cookies = document.cookie.split(';');
    for (let cookie of cookies) {
        const [name, value] = cookie.trim().split('=');
        if (name === 'csrf_token') {
            return decodeURIComponent(value);
        }
    }
    return '';
}

// The browser loads this as a plain script; tests require() it so coverage sees the real code.
if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
        checkDemographicsSubmitted,
        checkDevMode,
        collectDeviceInfo,
        getCSRFToken,
        initializeProgressiveQuestions,
        isQuestionGroupComplete,
        showRetakeModal,
        loadImagePair,
        navigateQuestion,
        setupEventListeners,
        setupSubmitValidation,
        updateQuestionVisibility,
    };
}
