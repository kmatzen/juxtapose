// State management
let demographicsData = null;
let currentImageIndex = 0;
let currentImageData = null;
let totalImagePairs = 30;

// Initialize
document.addEventListener('DOMContentLoaded', function() {
    setupEventListeners();
});

function setupEventListeners() {
    // Demographics form submission
    const demographicsForm = document.getElementById('demographics-form');
    if (demographicsForm) {
        demographicsForm.addEventListener('submit', handleDemographicsSubmit);
    }
    
    // Survey form submission
    const surveyForm = document.getElementById('survey-form');
    if (surveyForm) {
        surveyForm.addEventListener('submit', handleSurveySubmit);
    }
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
            document.getElementById('image-a').src = data.image_a_url;
            document.getElementById('image-b').src = data.image_b_url;
            
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
            if (result.error && result.error.includes('already submitted')) {
                showError('You have already evaluated this image pair.');
            } else {
                showError('Failed to submit response. Please try again.');
            }
            console.error('Error:', result.error);
        }
    } catch (error) {
        showError('Network error. Please check your connection and try again.');
        console.error('Error:', error);
    }
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
