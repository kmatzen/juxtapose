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
            const jx = seam();
            if (jx) jx.questions?.layout();
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
    const jx = seam();
    if (jx) {
        jx.conditioning.show(event.detail);
        jx.questions?.showTrial(event.detail);
    }
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

    const jx = seam();
    if (jx) jx.questions?.validate();
}

// script.js is the layer being deleted: it drives component behaviour through the seam (seam.ts)
// and must stay alive when the bundle is absent, so every call is guarded.
function seam() {
    return window.__JX__ || null;
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
            
            const jx = seam();
            if (jx) jx.questions?.showTrial(data);

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

// ==================================================================
// HELPER FUNCTIONS
// ==================================================================

function tutorialBlocksSubmit() {
    const jx = seam();
    return !!jx && !jx.tutorial.isComplete();
}

function showError(message) {
    const jx = seam();
    if (!jx) {
        console.error('Unshown message:', message);
        return;
    }
    jx.banner.show(message);
}

function openLightbox(src, caption) {
    const jx = seam();
    if (!jx) {
        console.error('Lightbox is not mounted');
        return;
    }
    jx.lightbox.open(src, caption);
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
        showRetakeModal,
        loadImagePair,
        setupEventListeners,
    };
}
