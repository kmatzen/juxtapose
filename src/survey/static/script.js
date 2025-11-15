// State management
let demographicsData = null;
let currentImageIndex = 0;
let currentImageData = null;
let totalImagePairs = 30;
let deviceInfo = {};
let devMode = false;

// Initialize
document.addEventListener('DOMContentLoaded', async function() {
    await checkDevMode();
    collectDeviceInfo();
    setupEventListeners();
});

// Recalculate heights on window resize
let resizeTimeout;
window.addEventListener('resize', () => {
    // Debounce resize events
    clearTimeout(resizeTimeout);
    resizeTimeout = setTimeout(() => {
        if (questionSections.length > 0) {
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
    
    // Detect OS
    let os = 'Unknown';
    if (ua.indexOf('Win') > -1) os = 'Windows';
    else if (ua.indexOf('Mac') > -1) os = 'macOS';
    else if (ua.indexOf('Linux') > -1) os = 'Linux';
    else if (ua.indexOf('Android') > -1) os = 'Android';
    else if (ua.indexOf('iOS') > -1 || ua.indexOf('iPhone') > -1 || ua.indexOf('iPad') > -1) os = 'iOS';
    
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
    
    // Display info to user
    document.getElementById('user-browser').textContent = `${browser} ${browserVersion}`;
    document.getElementById('user-os').textContent = os;
    document.getElementById('user-screen').textContent = `${screen.width} × ${screen.height}px`;
    document.getElementById('user-pixel-ratio').textContent = `${window.devicePixelRatio || 1}x`;
    document.getElementById('user-color').textContent = screen.colorDepth;
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
    
    const betterMatch = Math.random() < 0.5 ? 'A' : 'B';
    document.querySelector(`input[name="better_prompt_match"][value="${betterMatch}"]`).checked = true;
    
    const promptConf = Math.floor(Math.random() * 5) + 1;
    document.querySelector(`input[name="prompt_confidence"][value="${promptConf}"]`).checked = true;
    
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
    
    console.log(`✅ Survey form auto-filled: Image ${betterImage} (conf ${imageConf}), Match ${betterMatch} (conf ${promptConf}), Mask ${betterMask} (conf ${maskConf}), Identity ${betterIdentity} (conf ${identityConf})`);
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
            
            // Update button text
            const submitBtn = document.getElementById('submit-btn');
            if (index >= data.total_pairs - 1) {
                submitBtn.textContent = 'Submit Survey';
            } else {
                submitBtn.textContent = 'Next Image Pair';
            }
            
            // Reset form
            document.getElementById('survey-form').reset();
            
            // Reinitialize progressive questions for new image pair
            setTimeout(() => {
                initializeProgressiveQuestions();
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
        image_confidence: parseInt(surveyResponse.image_confidence),
        prompt_confidence: parseInt(surveyResponse.prompt_confidence),
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
    document.getElementById('conditioning-container').style.display = 'block';
    document.getElementById('identity-section').style.display = 'block';
    document.getElementById('mask-section').style.display = 'block';
    document.getElementById('identity-evaluation').style.display = 'block';
    document.getElementById('mask-evaluation').style.display = 'block';
    
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
            slicedImg.onclick = () => openLightbox(slicedImg.src, `Identity Reference ${i + 1}`);
            identityContainer.appendChild(slicedImg);
        }
    };
    stackedImg.onerror = () => {
        console.error('Failed to load identity image:', identityUrl);
        identityContainer.innerHTML = '<p style="color: red;">Failed to load identity images</p>';
    };
    stackedImg.src = identityUrl;
    
    // Display mask image
    const maskImg = document.getElementById('mask-image');
    maskImg.src = data.mask_url;
    maskImg.onclick = () => openLightbox(data.mask_url, 'Spatial Mask');
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
}

function setQuestionsHeight() {
    // Measure the height of one evaluation section
    if (questionSections.length === 0) return;
    
    const firstSection = questionSections[0];
    
    // Wait for content to be fully rendered
    if (!firstSection || firstSection.offsetHeight === 0) {
        // Retry after a short delay
        setTimeout(setQuestionsHeight, 100);
        return;
    }
    
    const sectionHeight = firstSection.offsetHeight;
    
    // Add some padding for comfortable viewing
    const desiredHeight = sectionHeight + 60; // 60px for padding/spacing
    
    // Get viewport height
    const vh = window.innerHeight;
    
    // Questions section should be at least one full question, but not more than 50vh
    const maxHeight = vh * 0.5;
    const minHeight = 300;
    
    const finalHeight = Math.min(Math.max(desiredHeight, minHeight), maxHeight);
    
    // Set the questions section height
    const questionsSection = document.querySelector('.questions-section');
    if (questionsSection) {
        questionsSection.style.height = `${finalHeight}px`;
    }
    
    // Calculate available space for visual content section
    const container = document.querySelector('.container');
    const progressContainer = document.querySelector('.progress-container');
    const containerPadding = 80; // Container padding (40px top + 40px bottom)
    const progressHeight = progressContainer ? progressContainer.offsetHeight : 60;
    const margins = 40; // Margins and gaps
    
    const availableHeight = vh - finalHeight - progressHeight - containerPadding - margins;
    
    // Scale the visual content section to fit
    scaleVisualContent(availableHeight);
}

function scaleVisualContent(availableHeight) {
    const visualSection = document.querySelector('.visual-content-section');
    if (!visualSection) return;
    
    // Set max-height on each column independently for independent scrolling
    const contextColumn = document.querySelector('.context-column');
    const generatedImagesColumn = document.querySelector('.generated-images-column');
    
    if (contextColumn) {
        contextColumn.style.maxHeight = `${availableHeight}px`;
    }
    if (generatedImagesColumn) {
        generatedImagesColumn.style.maxHeight = `${availableHeight}px`;
    }
    
    // Get all images in the visual section
    const generatedImages = visualSection.querySelectorAll('.generated-image');
    const identityImages = visualSection.querySelectorAll('.identity-image, .identity-stacked-image');
    const maskImage = visualSection.querySelector('#mask-image');
    
    // Calculate how much space we have for images
    // Account for: prompt box (~50px), padding (40px), margins (30px), headers (30px)
    const promptAndHeaderSpace = 150;
    
    // Generated images are side-by-side, so they can use most of the available height
    const availableImageSpace = availableHeight - promptAndHeaderSpace;
    
    // Calculate max height for generated images
    const maxImageHeight = Math.floor(availableImageSpace * 0.8);
    
    // Calculate max width for generated images
    // Right column is 55% of visual section width
    // Get the actual visual section width
    const visualSectionWidth = visualSection.offsetWidth;
    const rightColumnWidth = visualSectionWidth * 0.55;
    
    // Each image box gets ~half the right column width, accounting for gap and padding
    // gap: 15px, box padding: 24px (12px each side), border: 6px (3px each side)
    const imageBoxOverhead = 30; // padding + border per box
    const gap = 15;
    const maxImageWidth = Math.floor((rightColumnWidth - gap) / 2 - imageBoxOverhead);
    
    // Apply both width and height constraints to generated images
    generatedImages.forEach(img => {
        img.style.maxHeight = `${maxImageHeight}px`;
        img.style.maxWidth = `${maxImageWidth}px`;
        img.style.minWidth = '200px';
        img.style.minHeight = '200px';
        img.style.width = 'auto';
        img.style.height = 'auto';
        img.style.objectFit = 'contain';
    });
    
    // Identity and mask images: smaller to fit in left column alongside prompt
    const smallImageHeight = Math.floor((availableHeight - promptAndHeaderSpace) / 3);
    
    identityImages.forEach(img => {
        img.style.maxHeight = `${smallImageHeight}px`;
        img.style.minWidth = '200px';
        img.style.minHeight = '200px';
        img.style.width = 'auto';
        img.style.objectFit = 'contain';
    });
    
    if (maskImage) {
        maskImage.style.maxHeight = `${smallImageHeight}px`;
        maskImage.style.minWidth = '200px';
        maskImage.style.minHeight = '200px';
        maskImage.style.width = 'auto';
        maskImage.style.objectFit = 'contain';
    }
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

// Submit button is now always visible at the bottom of the questions section

// Initialize progressive questions when survey section loads
// This is now handled in loadImagePair() to avoid MutationObserver overhead
