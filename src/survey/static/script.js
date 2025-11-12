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
    
    console.log(`✅ Survey form auto-filled: Image ${betterImage} (conf ${imageConf}), Match ${betterMatch} (conf ${promptConf})`);
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
            document.getElementById('step1').classList.add('completed');
            document.getElementById('step2').classList.add('active');
            
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
        const response = await fetch(`/api/get_image_pair/${index}`);
        const data = await response.json();
        
        if (response.ok) {
            currentImageData = data;
            currentImageIndex = index;
            
            // Update UI
            document.getElementById('prompt-text').textContent = data.prompt;
            
            const imageA = document.getElementById('image-a');
            const imageB = document.getElementById('image-b');
            
            imageA.src = data.image_a_url;
            imageB.src = data.image_b_url;
            
            // Add click handlers for lightbox
            imageA.onclick = () => openLightbox(data.image_a_url, 'Image A');
            imageB.onclick = () => openLightbox(data.image_b_url, 'Image B');
            
            // Update progress
            document.getElementById('current-question').textContent = index + 1;
            document.getElementById('total-questions').textContent = data.total_pairs;
            totalImagePairs = data.total_pairs;
            
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
        image_a_url: currentImageData.image_a_url,
        image_b_url: currentImageData.image_b_url,
        was_randomized: currentImageData.was_randomized,
        image_confidence: parseInt(surveyResponse.image_confidence),
        prompt_confidence: parseInt(surveyResponse.prompt_confidence)
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
