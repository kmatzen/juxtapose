// State management
let demographicsData = null;
let currentImageIndex = 0;
let currentImageData = null;
let totalImagePairs = 30;
let deviceInfo = {};
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
let lastHeight = window.innerHeight;
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
            lastHeight = currentHeight;
            lastOrientation = currentOrientation;
            setQuestionsHeight();
        }
    }, 250);
});

async function checkDevMode() {
    try {
        const response = await fetch('/api/config');
        const config = await response.json();
        devMode = config.dev_mode;
        
        if (devMode) {
            console.log('🔧 DEV MODE ENABLED - Forms will be auto-filled');
            // Add a visible indicator
            const indicator = document.createElement('div');
            indicator.style.cssText = 'position: fixed; top: 10px; right: 10px; background: #ff6b6b; color: white; padding: 10px 15px; border-radius: 5px; z-index: 10000; font-weight: bold; box-shadow: 0 2px 5px rgba(0,0,0,0.2);';
            indicator.textContent = '🔧 DEV MODE';
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
                
                // Resume from where user left off
                // completed_pairs tells us how many pairs are done, so load the next one
                const nextPairIndex = data.completed_pairs || 0;
                await loadImagePair(nextPairIndex);
            }
        }
    } catch (error) {
        console.error('Error checking demographics:', error);
    }
}

function collectDeviceInfo() {
    // Detect browser
    const ua = navigator.userAgent;
    let browser = 'Unknown';
    let browserVersion = '';
    
    if (ua.indexOf('Firefox') > -1) {
        browser = 'Firefox';
        browserVersion = ua.match(/Firefox\/(\d+\.\d+)/)?.[1] || '';
    } else if (ua.indexOf('Chrome') > -1) {
        browser = 'Chrome';
        browserVersion = ua.match(/Chrome\/(\d+\.\d+)/)?.[1] || '';
    } else if (ua.indexOf('Safari') > -1) {
        browser = 'Safari';
        browserVersion = ua.match(/Version\/(\d+\.\d+)/)?.[1] || '';
    } else if (ua.indexOf('Edge') > -1 || ua.indexOf('Edg') > -1) {
        browser = 'Edge';
        browserVersion = ua.match(/Edg\/(\d+\.\d+)/)?.[1] || '';
    }
    
    // Detect OS (check iOS/iPadOS first, as they often report as Mac)
    let os = 'Unknown';
    const isIOS = /iPad|iPhone|iPod/.test(ua) || 
                  (ua.indexOf('Mac') > -1 && navigator.maxTouchPoints > 1);
    
    if (isIOS) os = 'iOS';
    else if (ua.indexOf('Android') > -1) os = 'Android';
    else if (ua.indexOf('Win') > -1) os = 'Windows';
    else if (ua.indexOf('Mac') > -1) os = 'macOS';
    else if (ua.indexOf('Linux') > -1) os = 'Linux';
    
    // Collect device info
    deviceInfo = {
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
    
    // Display info to user (only if elements exist - they're only on demographics page)
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

function setupEventListeners() {
    // Demographics form submission
    const demographicsForm = document.getElementById('demographics-form');
    if (demographicsForm) {
        demographicsForm.addEventListener('submit', handleDemographicsSubmit);
        
        // Auto-fill in dev mode
        if (devMode) {
            setTimeout(() => fillDemographicsForm(), 500);
        }
    }
    
    // Survey form submission
    const surveyForm = document.getElementById('survey-form');
    if (surveyForm) {
        surveyForm.addEventListener('submit', handleSurveySubmit);
    }
    
    // Image lightbox
    setupImageLightbox();
}

function setupImageLightbox() {
    const lightbox = document.getElementById('image-lightbox');
    const lightboxImage = document.getElementById('lightbox-image');
    const lightboxCaption = document.querySelector('.lightbox-caption');
    const closeBtn = document.querySelector('.lightbox-close');
    
    // Function to open lightbox
    window.openLightbox = function(imageSrc, caption) {
        lightboxImage.src = imageSrc;
        lightboxCaption.textContent = caption;
        lightbox.classList.add('show');
    };
    
    // Function to close lightbox
    const closeLightbox = () => {
        lightbox.classList.remove('show');
    };
    
    // Close button
    closeBtn.addEventListener('click', closeLightbox);
    
    // Close on background click
    lightbox.addEventListener('click', (e) => {
        if (e.target === lightbox) {
            closeLightbox();
        }
    });
    
    // Close on Escape key
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && lightbox.classList.contains('show')) {
            closeLightbox();
        }
    });
}

function fillDemographicsForm() {
    // Auto-fill demographics form with test data
    document.getElementById('email').value = 'test@example.com';
    document.getElementById('occupation').value = 'software-engineer';
    document.getElementById('technical-background').value = 'advanced';
    document.getElementById('has-used-image-gen').value = 'extensively';
    
    // Check some checkboxes (they don't have IDs, so use attribute selector)
    const checkboxValues = ['dalle', 'midjourney', 'stable-diffusion'];
    checkboxValues.forEach(value => {
        const checkbox = document.querySelector(`input[name="image_gen_tools[]"][value="${value}"]`);
        if (checkbox) checkbox.checked = true;
    });
    
    document.getElementById('works-on-ai').value = 'yes-industry';
    document.getElementById('ai-usage').value = 'often';
    document.getElementById('works-with-graphics').value = 'professional';
    document.getElementById('ai-familiarity').value = 'advanced';
    
    console.log('✅ Demographics form auto-filled');
}

function fillSurveyForm() {
    // Auto-select random choices
    const betterImage = Math.random() < 0.5 ? 'A' : 'B';
    document.querySelector(`input[name="better_image"][value="${betterImage}"]`).checked = true;
    
    const imageConf = Math.floor(Math.random() * 5) + 1;
    document.querySelector(`input[name="image_confidence"][value="${imageConf}"]`).checked = true;
    
    // Auto-fill prompt evaluation (if enabled)
    const promptMatchElement = document.querySelector(`input[name="better_prompt_match"]`);
    if (promptMatchElement) {
        const betterMatch = Math.random() < 0.5 ? 'A' : 'B';
        document.querySelector(`input[name="better_prompt_match"][value="${betterMatch}"]`).checked = true;
        
        const promptConf = Math.floor(Math.random() * 5) + 1;
        document.querySelector(`input[name="prompt_confidence"][value="${promptConf}"]`).checked = true;
    }
    
    // Auto-fill mask evaluation (always present)
    const betterMask = Math.random() < 0.5 ? 'A' : 'B';
    document.querySelector(`input[name="better_mask_match"][value="${betterMask}"]`).checked = true;
    const maskConf = Math.floor(Math.random() * 5) + 1;
    document.querySelector(`input[name="mask_confidence"][value="${maskConf}"]`).checked = true;
    
    // Auto-fill identity evaluation (always present)
    const betterIdentity = Math.random() < 0.5 ? 'A' : 'B';
    document.querySelector(`input[name="better_identity_match"][value="${betterIdentity}"]`).checked = true;
    const identityConf = Math.floor(Math.random() * 5) + 1;
    document.querySelector(`input[name="identity_confidence"][value="${identityConf}"]`).checked = true;
    
    // Build log message
    let logMsg = `✅ Survey form auto-filled: Image ${betterImage} (conf ${imageConf})`;
    if (promptMatchElement) {
        const betterMatch = document.querySelector(`input[name="better_prompt_match"]:checked`).value;
        const promptConf = document.querySelector(`input[name="prompt_confidence"]:checked`).value;
        logMsg += `, Match ${betterMatch} (conf ${promptConf})`;
    }
    logMsg += `, Mask ${betterMask} (conf ${maskConf}), Identity ${betterIdentity} (conf ${identityConf})`;
    console.log(logMsg);
}

async function handleDemographicsSubmit(event) {
    event.preventDefault();
    
    const formData = new FormData(event.target);
    demographicsData = {};
    
    // Handle regular form fields
    for (const [key, value] of formData.entries()) {
        // Handle checkbox arrays
        if (key.endsWith('[]')) {
            const cleanKey = key.replace('[]', '');
            if (!demographicsData[cleanKey]) {
                demographicsData[cleanKey] = [];
            }
            demographicsData[cleanKey].push(value);
        } else {
            demographicsData[key] = value;
        }
    }
    
    // Convert checkbox arrays to comma-separated strings
    if (Array.isArray(demographicsData.image_gen_tools)) {
        demographicsData.image_gen_tools = demographicsData.image_gen_tools.join(', ');
    } else if (!demographicsData.image_gen_tools) {
        demographicsData.image_gen_tools = 'none';
    }
    
    // Add device info to submission
    demographicsData.device_info = deviceInfo;
    
    try {
        const response = await fetch('/api/submit_demographics', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(demographicsData)
        });
        
        const result = await response.json();
        
        if (response.ok && result.success) {
            // Warn if retaking the survey
            if (result.is_retaking) {
                // Show custom modal and wait for user decision
                const shouldContinue = await showRetakeModal();
                
                if (!shouldContinue) {
                    // Reload page to go back
                    window.location.reload();
                    return;
                }
            }
            
            // Move to survey section
            document.getElementById('demographics-section').classList.remove('active');
            document.getElementById('survey-section').classList.add('active');
            
            // Show survey progress
            document.getElementById('survey-progress').style.display = 'block';
            
            // Load first image pair
            await loadImagePair(0);
            
            // Scroll to top
            window.scrollTo(0, 0);
        } else {
            showError('Failed to submit demographics. Please try again.');
            console.error('Error:', result.error);
        }
    } catch (error) {
        showError('Network error. Please check your connection and try again.');
        console.error('Error:', error);
    }
}

async function loadImagePair(index) {
    try {
        console.log(`Fetching image pair ${index}...`);
        const response = await fetch(`/api/get_image_pair/${index}`);
        const data = await response.json();
        
        console.log('API response:', { ok: response.ok, status: response.status });
        
        if (response.ok) {
            console.log('Image pair data received:', { id: data.id, hasImageA: !!data.image_a_url, hasImageB: !!data.image_b_url });
            currentImageData = data;
            currentImageIndex = index;
            
            // Reset hover handlers flag for new image pair
            hoverHandlersSetup = false;
            binaryMasks = {};
            
            // Remove any existing overlays from previous image pair
            const oldOverlays = document.querySelectorAll('.mask-overlay');
            oldOverlays.forEach(overlay => overlay.remove());
            
            // Update UI
            document.getElementById('prompt-text').textContent = data.prompt;
            
            // Handle identity and mask conditioning
            displayConditioningInputs(data);
            
            const imageA = document.getElementById('image-a');
            const imageB = document.getElementById('image-b');
            
            // Clear previous images and show loading state
            imageA.style.opacity = '0.3';
            imageB.style.opacity = '0.3';
            imageA.src = '';
            imageB.src = '';
            imageA.alt = `Loading ${data.method_a}...`;
            imageB.alt = `Loading ${data.method_b}...`;
            
            // Add loading indicators
            const imageBoxA = imageA.parentElement;
            const imageBoxB = imageB.parentElement;
            
            const loadingA = document.createElement('div');
            loadingA.className = 'loading-indicator';
            loadingA.textContent = 'Loading';
            imageBoxA.appendChild(loadingA);
            
            const loadingB = document.createElement('div');
            loadingB.className = 'loading-indicator';
            loadingB.textContent = 'Loading';
            imageBoxB.appendChild(loadingB);
            
            // Disable form during image loading to prevent submission with wrong images
            const surveyForm = document.getElementById('survey-form');
            surveyForm.style.pointerEvents = 'none';
            surveyForm.style.opacity = '0.5';
            
            // Preload images before showing them
            const imgALoader = new Image();
            const imgBLoader = new Image();
            
            // Enable CORS for canvas access (for hover overlays)
            imgALoader.crossOrigin = 'anonymous';
            imgBLoader.crossOrigin = 'anonymous';
            imageA.crossOrigin = 'anonymous';
            imageB.crossOrigin = 'anonymous';
            
            let aLoaded = false;
            let bLoaded = false;
            let aError = false;
            let bError = false;
            
            const checkBothLoaded = () => {
                if ((aLoaded || aError) && (bLoaded || bError)) {
                    // Remove loading indicators
                    const loadingIndicators = document.querySelectorAll('.loading-indicator');
                    loadingIndicators.forEach(indicator => indicator.remove());
                    
                    if (aError || bError) {
                        // Show error message
                        const errorMsg = `Failed to load images: ${aError ? 'Image A' : ''} ${bError ? 'Image B' : ''}`;
                        showError(errorMsg);
                        imageA.style.opacity = '1';
                        imageB.style.opacity = '1';
                        surveyForm.style.pointerEvents = 'auto';
                        surveyForm.style.opacity = '1';
                    } else {
                        // Both loaded successfully - display them
                        imageA.src = data.image_a_url;
                        imageB.src = data.image_b_url;
                        imageA.alt = `Image generated by ${data.method_a}`;
                        imageB.alt = `Image generated by ${data.method_b}`;
                        imageA.dataset.method = data.method_a;
                        imageB.dataset.method = data.method_b;
                        imageA.dataset.url = data.image_a_url;
                        imageB.dataset.url = data.image_b_url;
                        imageA.style.opacity = '1';
                        imageB.style.opacity = '1';
                        
                        // Re-enable form
                        surveyForm.style.pointerEvents = 'auto';
                        surveyForm.style.opacity = '1';
                        
                        // Start timing for this pair (when images are ready and form is enabled)
                        pairStartTime = Date.now();
                        
                        // Verify images loaded (don't reveal method names to avoid bias)
                        console.log(`✓ Loaded comparison ${data.id} of ${data.total_pairs}`);
                    }
                }
            };
            
            imgALoader.onload = () => {
                console.log('Image A loaded successfully');
                aLoaded = true;
                checkBothLoaded();
            };
            
            imgBLoader.onload = () => {
                console.log('Image B loaded successfully');
                bLoaded = true;
                checkBothLoaded();
            };
            
            imgALoader.onerror = (e) => {
                console.error('Failed to load image A', e);
                aError = true;
                checkBothLoaded();
            };
            
            imgBLoader.onerror = (e) => {
                console.error('Failed to load image B', e);
                bError = true;
                checkBothLoaded();
            };
            
            // Start loading
            console.log('Starting image load...');
            imgALoader.src = data.image_a_url;
            imgBLoader.src = data.image_b_url;
            
            // Add click handlers for lightbox
            imageA.onclick = () => openLightbox(data.image_a_url, 'Image A');
            imageB.onclick = () => openLightbox(data.image_b_url, 'Image B');
            
            // Update progress
            document.getElementById('current-question').textContent = index + 1;
            document.getElementById('total-questions').textContent = data.total_pairs;
            totalImagePairs = data.total_pairs;
            
            // Update instruction text with actual number of pairs (only on first load)
            if (index === 0) {
                const pairWord = data.total_pairs === 1 ? 'pair' : 'pairs';
                document.getElementById('total-pairs-text').textContent = 
                    `You will see ${data.total_pairs} image ${pairWord} in total.`;
            }
            
            const progressPercent = ((index) / data.total_pairs) * 100;
            document.getElementById('progress-bar-fill').style.width = progressPercent + '%';
            
            // Reset form
            document.getElementById('survey-form').reset();
            
            // Disable submit button until questions are answered
            const submitBtn = document.getElementById('submit-btn');
            if (submitBtn) {
                submitBtn.disabled = true;
            }
            
            // Reinitialize progressive questions for new image pair
            setTimeout(() => {
                // Reset to first question
                currentQuestionIndex = 0;
                
                initializeProgressiveQuestions();
                
                // Reset scroll position to the first question
                const questionsContainer = document.querySelector('.questions-container');
                if (questionsContainer) {
                    questionsContainer.scrollTop = 0;
                }
            }, 200);
            
            // Auto-fill in dev mode
            if (devMode) {
                setTimeout(() => fillSurveyForm(), 100);
            }
            
        } else {
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
    
    const formData = new FormData(event.target);
    const surveyResponse = Object.fromEntries(formData.entries());
    
    // Calculate time spent on this pair (in seconds)
    const timeSpent = pairStartTime ? (Date.now() - pairStartTime) / 1000 : null;
    
    // Add the current image data to the response
    const completeResponse = {
        ...surveyResponse,
        image_pair_id: currentImageData.id,
        prompt: currentImageData.prompt,
        method_a: currentImageData.method_a,
        method_b: currentImageData.method_b,
        image_a_url: currentImageData.image_a_url,
        image_b_url: currentImageData.image_b_url,
        identity_urls: currentImageData.identity_urls || null,
        mask_url: currentImageData.mask_url || null,
        was_randomized: currentImageData.was_randomized,
        time_spent: timeSpent,
        image_confidence: parseInt(surveyResponse.image_confidence),
        // Conditionally add prompt fields if present (controlled by ENABLE_PROMPT_QUESTION)
        ...(surveyResponse.better_prompt_match && {
            better_prompt_match: surveyResponse.better_prompt_match,
            prompt_confidence: parseInt(surveyResponse.prompt_confidence)
        }),
        // Conditionally add mask/identity fields if present
        ...(surveyResponse.better_mask_match && {
            better_mask_match: surveyResponse.better_mask_match,
            mask_confidence: parseInt(surveyResponse.mask_confidence)
        }),
        ...(surveyResponse.better_identity_match && {
            better_identity_match: surveyResponse.better_identity_match,
            identity_confidence: parseInt(surveyResponse.identity_confidence)
        })
    };
    
    try {
        const response = await fetch('/api/submit_survey', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
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
    return new Promise((resolve) => {
        const modal = document.getElementById('retake-modal');
        const confirmBtn = document.getElementById('retake-confirm');
        const cancelBtn = document.getElementById('retake-cancel');
        
        // Show modal
        modal.classList.add('show');
        
        // Handle confirm
        const handleConfirm = () => {
            modal.classList.remove('show');
            confirmBtn.removeEventListener('click', handleConfirm);
            cancelBtn.removeEventListener('click', handleCancel);
            resolve(true);
        };
        
        // Handle cancel
        const handleCancel = () => {
            modal.classList.remove('show');
            confirmBtn.removeEventListener('click', handleConfirm);
            cancelBtn.removeEventListener('click', handleCancel);
            resolve(false);
        };
        
        confirmBtn.addEventListener('click', handleConfirm);
        cancelBtn.addEventListener('click', handleCancel);
        
        // Close on background click
        modal.addEventListener('click', (e) => {
            if (e.target === modal) {
                handleCancel();
            }
        });
    });
}

function displayConditioningInputs(data) {
    // Always display conditioning since all pairs have identity and mask
    // Note: Elements are always visible in new layout, no need to toggle display
    const identitySection = document.getElementById('identity-section');
    const identityEval = document.getElementById('identity-evaluation');
    const maskEval = document.getElementById('mask-evaluation');
    
    if (identitySection) identitySection.style.display = 'block';
    if (identityEval) identityEval.style.display = 'block';
    if (maskEval) maskEval.style.display = 'block';
    
    // Display identity images
    // The identity URL points to a single tall image: 512px wide x (512 * N) tall
    // where N is the number of identities stacked vertically
    const identityContainer = document.getElementById('identity-images');
    identityContainer.innerHTML = ''; // Clear previous
    
    const identityUrl = data.identity_urls.trim();
    
    // Load the tall stacked image
    const stackedImg = new Image();
    stackedImg.crossOrigin = 'anonymous'; // For canvas access
    stackedImg.onload = () => {
        const width = 512;
        const height = 512;
        const numIdentities = Math.round(stackedImg.height / height);
        
        // Create a canvas for slicing
        const canvas = document.createElement('canvas');
        canvas.width = width;
        canvas.height = height;
        const ctx = canvas.getContext('2d');
        
        // Slice and display each 512x512 segment horizontally
        for (let i = 0; i < numIdentities; i++) {
            // Clear canvas
            ctx.clearRect(0, 0, width, height);
            
            // Draw the slice from the stacked image
            // sx, sy, sWidth, sHeight, dx, dy, dWidth, dHeight
            ctx.drawImage(stackedImg, 0, i * height, width, height, 0, 0, width, height);
            
            // Convert canvas to image
            const slicedImg = document.createElement('img');
            slicedImg.src = canvas.toDataURL();
            slicedImg.alt = `Identity ${i + 1}`;
            slicedImg.className = 'identity-image';
            // Add color coding data attribute (colors will match spatial mask regions)
            slicedImg.setAttribute('data-identity-index', i);
            slicedImg.onclick = () => openLightbox(slicedImg.src, `Identity Reference ${i + 1}`);
            identityContainer.appendChild(slicedImg);
        }
        
        // Now that identity images are in the DOM, set up hover handlers
        // (but only if binary masks have been processed)
        if (Object.keys(binaryMasks).length > 0) {
            setupIdentityHoverHandlers();
        }
    };
    stackedImg.onerror = () => {
        console.error('Failed to load identity image:', identityUrl);
        identityContainer.innerHTML = '<p style="color: red;">Failed to load identity images</p>';
    };
    stackedImg.src = identityUrl;
    
    // Display mask image
    const maskImg = document.getElementById('mask-image');
    maskImg.crossOrigin = 'anonymous'; // Enable CORS for canvas access
    maskImg.src = data.mask_url;
    maskImg.onclick = () => openLightbox(data.mask_url, 'Spatial Mask');
    
    // Process mask for hover overlays once it loads
    maskImg.onload = () => {
        processMaskForOverlays(maskImg);
    };
}

// Global storage for binary masks extracted from spatial mask
let binaryMasks = {};
let hoverHandlersSetup = false; // Flag to prevent duplicate setup

// Color mapping for identity regions (RGB values)
const IDENTITY_COLORS = [
    [255, 0, 0],      // 0: Red
    [0, 255, 0],      // 1: Green
    [0, 0, 255],      // 2: Blue
    [255, 255, 0],    // 3: Yellow
    [255, 0, 255],    // 4: Magenta
    [0, 255, 255],    // 5: Cyan
    [255, 128, 0],    // 6: Orange
    // Add more colors as needed
];

function processMaskForOverlays(maskImg) {
    // Create a canvas to read mask pixel data
    const canvas = document.createElement('canvas');
    canvas.width = maskImg.naturalWidth || maskImg.width;
    canvas.height = maskImg.naturalHeight || maskImg.height;
    const ctx = canvas.getContext('2d');
    
    try {
        ctx.drawImage(maskImg, 0, 0);
        const imageData = ctx.getImageData(0, 0, canvas.width, canvas.height);
        const pixels = imageData.data;
        
        // Extract binary masks for each identity color
        binaryMasks = {};
        
        IDENTITY_COLORS.forEach((color, index) => {
            const mask = new Uint8Array(canvas.width * canvas.height);
            let matchCount = 0;
            
            // Check each pixel for color match
            for (let i = 0; i < pixels.length; i += 4) {
                const r = pixels[i];
                const g = pixels[i + 1];
                const b = pixels[i + 2];
                
                // Check if pixel matches this identity color (with small tolerance)
                const matches = 
                    Math.abs(r - color[0]) < 10 &&
                    Math.abs(g - color[1]) < 10 &&
                    Math.abs(b - color[2]) < 10;
                
                if (matches) {
                    mask[i / 4] = 255;
                    matchCount++;
                } else {
                    mask[i / 4] = 0;
                }
            }
            
            binaryMasks[index] = {
                data: mask,
                width: canvas.width,
                height: canvas.height,
                matchCount: matchCount
            };
        });
        
        // Set up hover handlers if identity images are already in the DOM
        // (they might have loaded while we were processing the mask)
        const identityImages = document.querySelectorAll('.identity-image');
        if (identityImages.length > 0) {
            setupIdentityHoverHandlers();
        }
        
    } catch (e) {
        // Silently fail if CORS prevents mask processing - feature won't work but app continues
        console.error('Failed to process mask for overlays:', e.message);
    }
}

function setupIdentityHoverHandlers() {
    if (hoverHandlersSetup) {
        return;
    }
    
    const identityImages = document.querySelectorAll('.identity-image');
    
    if (identityImages.length === 0) {
        return;
    }
    
    identityImages.forEach(img => {
        const index = parseInt(img.getAttribute('data-identity-index'));
        
        img.addEventListener('mouseenter', () => {
            showMaskOverlay(index);
        });
        
        img.addEventListener('mouseleave', () => {
            hideMaskOverlay();
        });
    });
    
    hoverHandlersSetup = true;
}

function showMaskOverlay(identityIndex) {
    const mask = binaryMasks[identityIndex];
    if (!mask) {
        return;
    }
    
    // Apply overlay to Image A and Image B
    const imageA = document.getElementById('image-a');
    const imageB = document.getElementById('image-b');
    
    [imageA, imageB].forEach(img => {
        if (!img || !img.complete) {
            return;
        }
        
        createOverlay(img, mask, identityIndex);
    });
}

function createOverlay(targetImg, mask, identityIndex) {
    // Find or create overlay canvas
    const container = targetImg.parentElement;
    let overlay = container.querySelector('.mask-overlay');
    
    if (!overlay) {
        overlay = document.createElement('canvas');
        overlay.className = 'mask-overlay';
        overlay.style.position = 'absolute';
        overlay.style.pointerEvents = 'none';
        overlay.style.zIndex = '10';
        container.style.position = 'relative';
        container.appendChild(overlay);
    }
    
    // Get actual image position and size
    const imgRect = targetImg.getBoundingClientRect();
    const containerRect = container.getBoundingClientRect();
    
    // Calculate offset of image within container
    const offsetLeft = imgRect.left - containerRect.left;
    const offsetTop = imgRect.top - containerRect.top;
    
    // Position overlay exactly over the image
    overlay.style.left = offsetLeft + 'px';
    overlay.style.top = offsetTop + 'px';
    
    // Create canvas at FULL MASK RESOLUTION for sharp edges
    overlay.width = mask.width;
    overlay.height = mask.height;
    
    // Scale down with CSS to match display size (browser handles smooth scaling)
    overlay.style.width = targetImg.clientWidth + 'px';
    overlay.style.height = targetImg.clientHeight + 'px';
    
    const ctx = overlay.getContext('2d');
    ctx.clearRect(0, 0, overlay.width, overlay.height);
    
    // Get identity color for highlighting
    const color = IDENTITY_COLORS[identityIndex] || [255, 255, 255];
    
    // Create overlay effect at full resolution
    const overlayData = ctx.createImageData(overlay.width, overlay.height);
    const pixels = overlayData.data;
    
    // Direct 1:1 mapping - no scaling needed
    for (let i = 0; i < mask.data.length; i++) {
        const pixelIndex = i * 4;
        
        if (mask.data[i] > 0) {
            // Highlight this region with semi-transparent color
            pixels[pixelIndex] = color[0];     // R
            pixels[pixelIndex + 1] = color[1]; // G
            pixels[pixelIndex + 2] = color[2]; // B
            pixels[pixelIndex + 3] = 100;      // Alpha (semi-transparent)
        } else {
            pixels[pixelIndex + 3] = 0; // Fully transparent
        }
    }
    
    ctx.putImageData(overlayData, 0, 0);
    overlay.style.display = 'block';
}

function hideMaskOverlay() {
    const overlays = document.querySelectorAll('.mask-overlay');
    overlays.forEach(overlay => {
        overlay.style.display = 'none';
    });
}

function showError(message) {
    // Create error element if it doesn't exist
    let errorDiv = document.querySelector('.error-message');
    if (!errorDiv) {
        errorDiv = document.createElement('div');
        errorDiv.className = 'error-message';
        const activeSection = document.querySelector('.section.active');
        activeSection.insertBefore(errorDiv, activeSection.firstChild);
    }
    
    errorDiv.textContent = message;
    errorDiv.classList.add('show');
    
    // Hide after 5 seconds
    setTimeout(() => {
        errorDiv.classList.remove('show');
    }, 5000);
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
    lastHeight = m.vh;
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
    const radioGroups = {};
    
    // Find all radio button groups in this section
    const radios = section.querySelectorAll('input[type="radio"]');
    radios.forEach(radio => {
        if (!radioGroups[radio.name]) {
            radioGroups[radio.name] = false;
        }
        if (radio.checked) {
            radioGroups[radio.name] = true;
        }
    });
    
    // Check if all groups have a selection
    return Object.values(radioGroups).every(selected => selected);
}

function setupSubmitValidation() {
    const submitBtn = document.getElementById('submit-btn');
    const surveyForm = document.getElementById('survey-form');
    
    if (!submitBtn || !surveyForm) return;
    
    // Function to check if all questions are answered
    function validateForm() {
        // Get ALL radio inputs and group by name
        const radioGroups = {};
        const allRadios = surveyForm.querySelectorAll('input[type="radio"]');
        
        allRadios.forEach(radio => {
            if (!radioGroups[radio.name]) {
                radioGroups[radio.name] = false;
            }
            if (radio.checked) {
                radioGroups[radio.name] = true;
            }
        });
        
        // All groups must have a selection
        const allAnswered = Object.values(radioGroups).length > 0 && 
                           Object.values(radioGroups).every(answered => answered);
        
        // Enable/disable submit button
        submitBtn.disabled = !allAnswered;
        
        return allAnswered;
    }
    
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
