// State management
let demographicsData = null;
let currentQuestionIndex = 0;
let currentQuestionData = null;
let totalQuestions = 30;

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
    demographicsData = Object.fromEntries(formData.entries());
    
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
            
            // Load first question
            await loadQuestionPair(0);
            
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

async function loadQuestionPair(index) {
    try {
        const response = await fetch(`/api/get_question_pair/${index}`);
        const data = await response.json();
        
        if (response.ok) {
            currentQuestionData = data;
            currentQuestionIndex = index;
            
            // Update UI
            document.getElementById('prompt-text').textContent = data.prompt;
            document.getElementById('question-a').textContent = data.question_a;
            document.getElementById('question-b').textContent = data.question_b;
            
            // Update progress
            document.getElementById('current-question').textContent = index + 1;
            document.getElementById('total-questions').textContent = data.total_pairs;
            totalQuestions = data.total_pairs;
            
            const progressPercent = ((index) / data.total_pairs) * 100;
            document.getElementById('progress-bar-fill').style.width = progressPercent + '%';
            
            // Update button text
            const submitBtn = document.getElementById('submit-btn');
            if (index >= data.total_pairs - 1) {
                submitBtn.textContent = 'Submit Survey';
            } else {
                submitBtn.textContent = 'Next Question';
            }
            
            // Reset form
            document.getElementById('survey-form').reset();
            
        } else {
            showError('Failed to load question. Please refresh the page.');
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
    
    // Add the current question data to the response
    const completeResponse = {
        ...surveyResponse,
        question_pair_id: currentQuestionData.id,
        question_a: currentQuestionData.question_a,
        question_b: currentQuestionData.question_b,
        prompt: currentQuestionData.prompt,
        was_randomized: currentQuestionData.was_randomized,
        confidence: parseInt(surveyResponse.confidence)
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
                // All questions completed, redirect to thank you page
                window.location.href = '/';
            } else {
                // Load next question
                currentQuestionIndex++;
                await loadQuestionPair(currentQuestionIndex);
                window.scrollTo(0, 0);
            }
        } else {
            if (result.error && result.error.includes('already submitted')) {
                showError('You have already answered this question.');
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
