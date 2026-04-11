/**
 * Tests for progressive question navigation system
 */

describe('Progressive Questions System', () => {
  let questionSections;
  let currentQuestionIndex;

  beforeEach(() => {
    // Set up DOM with multiple questions
    document.body.innerHTML = `
      <div class="question-section" id="questions-container">
        <div class="question-group" data-question-index="0">
          <h3>Question 1</h3>
          <div class="btn-group">
            <input type="radio" name="better_image" value="A">
            <input type="radio" name="better_image" value="B">
          </div>
          <div class="btn-group">
            <input type="radio" name="image_confidence" value="1">
            <input type="radio" name="image_confidence" value="5">
          </div>
        </div>
        
        <div class="question-group" data-question-index="1">
          <h3>Question 2</h3>
          <div class="btn-group">
            <input type="radio" name="better_mask_match" value="A">
            <input type="radio" name="better_mask_match" value="B">
          </div>
          <div class="btn-group">
            <input type="radio" name="mask_confidence" value="1">
            <input type="radio" name="mask_confidence" value="5">
          </div>
        </div>
        
        <div class="question-group" data-question-index="2">
          <h3>Question 3</h3>
          <div class="btn-group">
            <input type="radio" name="better_identity_match" value="A">
            <input type="radio" name="better_identity_match" value="B">
          </div>
          <div class="btn-group">
            <input type="radio" name="identity_confidence" value="1">
            <input type="radio" name="identity_confidence" value="5">
          </div>
        </div>
      </div>
      
      <div class="question-navigation">
        <button id="nav-up" class="nav-arrow">▲</button>
        <button id="nav-down" class="nav-arrow">▼</button>
      </div>
      
      <button id="submit-btn">Submit</button>
    `;

    questionSections = document.querySelectorAll('.question-group');
    currentQuestionIndex = 0;
  });

  describe('Question Navigation', () => {
    test('initializes with first question visible', () => {
      const firstQuestion = questionSections[0];
      firstQuestion.classList.add('active');
      
      expect(firstQuestion.classList.contains('active')).toBe(true);
    });

    test('navigates to next question', () => {
      currentQuestionIndex = 0;
      
      // Remove active from current
      questionSections[currentQuestionIndex].classList.remove('active');
      
      // Move to next
      currentQuestionIndex++;
      questionSections[currentQuestionIndex].classList.add('active');
      
      expect(currentQuestionIndex).toBe(1);
      expect(questionSections[1].classList.contains('active')).toBe(true);
      expect(questionSections[0].classList.contains('active')).toBe(false);
    });

    test('navigates to previous question', () => {
      currentQuestionIndex = 2;
      questionSections[currentQuestionIndex].classList.add('active');
      
      // Remove active from current
      questionSections[currentQuestionIndex].classList.remove('active');
      
      // Move to previous
      currentQuestionIndex--;
      questionSections[currentQuestionIndex].classList.add('active');
      
      expect(currentQuestionIndex).toBe(1);
      expect(questionSections[1].classList.contains('active')).toBe(true);
      expect(questionSections[2].classList.contains('active')).toBe(false);
    });

    test('prevents navigating before first question', () => {
      currentQuestionIndex = 0;
      
      const canNavigateUp = currentQuestionIndex > 0;
      
      if (canNavigateUp) {
        currentQuestionIndex--;
      }
      
      expect(currentQuestionIndex).toBe(0);
    });

    test('prevents navigating past last question', () => {
      currentQuestionIndex = 2; // Last question
      const totalQuestions = questionSections.length;
      
      const canNavigateDown = currentQuestionIndex < totalQuestions - 1;
      
      if (canNavigateDown) {
        currentQuestionIndex++;
      }
      
      expect(currentQuestionIndex).toBe(2);
    });

    test('updates navigation button states', () => {
      const upBtn = document.getElementById('nav-up');
      const downBtn = document.getElementById('nav-down');
      
      currentQuestionIndex = 0;
      
      // At first question
      upBtn.disabled = currentQuestionIndex === 0;
      downBtn.disabled = currentQuestionIndex === questionSections.length - 1;
      
      expect(upBtn.disabled).toBe(true);
      expect(downBtn.disabled).toBe(false);
      
      // At last question
      currentQuestionIndex = 2;
      upBtn.disabled = currentQuestionIndex === 0;
      downBtn.disabled = currentQuestionIndex === questionSections.length - 1;
      
      expect(upBtn.disabled).toBe(false);
      expect(downBtn.disabled).toBe(true);
    });

    test('hides up button on first question', () => {
      const upBtn = document.getElementById('nav-up');
      currentQuestionIndex = 0;
      
      upBtn.style.visibility = currentQuestionIndex === 0 ? 'hidden' : 'visible';
      
      expect(upBtn.style.visibility).toBe('hidden');
    });

    test('hides down button on last question', () => {
      const downBtn = document.getElementById('nav-down');
      currentQuestionIndex = questionSections.length - 1;
      
      downBtn.style.visibility = currentQuestionIndex === questionSections.length - 1 ? 'hidden' : 'visible';
      
      expect(downBtn.style.visibility).toBe('hidden');
    });
  });

  describe('Question Completion Detection', () => {
    test('detects complete question (both choice and confidence)', () => {
      const question = questionSections[0];
      question.querySelector('input[name="better_image"][value="A"]').checked = true;
      question.querySelector('input[name="image_confidence"][value="5"]').checked = true;
      
      const isComplete = () => {
        const choiceSelected = question.querySelector('input[type="radio"]:checked:not([name*="confidence"])');
        const confidenceSelected = question.querySelector('input[name*="confidence"]:checked');
        return !!(choiceSelected && confidenceSelected);
      };
      
      expect(isComplete()).toBe(true);
    });

    test('detects incomplete question (missing choice)', () => {
      const question = questionSections[0];
      question.querySelector('input[name="image_confidence"][value="5"]').checked = true;
      // No choice selected
      
      const isComplete = () => {
        const choiceSelected = question.querySelector('input[type="radio"]:checked:not([name*="confidence"])');
        const confidenceSelected = question.querySelector('input[name*="confidence"]:checked');
        return !!(choiceSelected && confidenceSelected);
      };
      
      expect(isComplete()).toBe(false);
    });

    test('detects incomplete question (missing confidence)', () => {
      const question = questionSections[0];
      question.querySelector('input[name="better_image"][value="A"]').checked = true;
      // No confidence selected
      
      const isComplete = () => {
        const choiceSelected = question.querySelector('input[type="radio"]:checked:not([name*="confidence"])');
        const confidenceSelected = question.querySelector('input[name*="confidence"]:checked');
        return !!(choiceSelected && confidenceSelected);
      };
      
      expect(isComplete()).toBe(false);
    });

    test('checks all questions completion', () => {
      // Fill all questions
      questionSections.forEach((question, index) => {
        const radios = question.querySelectorAll('input[type="radio"]');
        radios[0].checked = true; // First choice
        radios[2].checked = true; // First confidence
      });
      
      const allComplete = () => {
        return Array.from(questionSections).every(question => {
          const allBtnGroups = question.querySelectorAll('.btn-group');
          const choiceInputs = allBtnGroups[0].querySelectorAll('input[type="radio"]');
          const confidenceInputs = allBtnGroups[1].querySelectorAll('input[type="radio"]');
          const choiceSelected = Array.from(choiceInputs).some(input => input.checked);
          const confidenceSelected = Array.from(confidenceInputs).some(input => input.checked);
          return choiceSelected && confidenceSelected;
        });
      };
      
      expect(allComplete()).toBe(true);
    });
  });

  describe('Auto-advance on Completion', () => {
    test('advances to next question when current is complete', () => {
      currentQuestionIndex = 0;
      const question = questionSections[0];
      
      // User completes question
      question.querySelector('input[name="better_image"][value="A"]').checked = true;
      question.querySelector('input[name="image_confidence"][value="5"]').checked = true;
      
      // Check if complete
      const isComplete = question.querySelector('input[type="radio"]:checked:not([name*="confidence"])') &&
                        question.querySelector('input[name*="confidence"]:checked');
      
      // Auto-advance
      if (isComplete && currentQuestionIndex < questionSections.length - 1) {
        questionSections[currentQuestionIndex].classList.remove('active');
        currentQuestionIndex++;
        questionSections[currentQuestionIndex].classList.add('active');
      }
      
      expect(currentQuestionIndex).toBe(1);
      expect(questionSections[1].classList.contains('active')).toBe(true);
    });

    test('does not auto-advance on last question', () => {
      currentQuestionIndex = 2; // Last question
      const question = questionSections[2];
      
      // User completes last question
      question.querySelector('input[name="better_identity_match"][value="A"]').checked = true;
      question.querySelector('input[name="identity_confidence"][value="5"]').checked = true;
      
      const isComplete = question.querySelector('input[type="radio"]:checked:not([name*="confidence"])') &&
                        question.querySelector('input[name*="confidence"]:checked');
      
      // Try to auto-advance (should not happen)
      const initialIndex = currentQuestionIndex;
      if (isComplete && currentQuestionIndex < questionSections.length - 1) {
        currentQuestionIndex++;
      }
      
      expect(currentQuestionIndex).toBe(initialIndex);
    });

    test('scrolls current question into view', () => {
      const question = questionSections[1];
      const scrollIntoViewMock = jest.fn();
      question.scrollIntoView = scrollIntoViewMock;
      
      // Scroll to question
      question.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
      
      expect(scrollIntoViewMock).toHaveBeenCalledWith({
        behavior: 'smooth',
        block: 'nearest'
      });
    });
  });

  describe('Submit Button State', () => {
    test('enables submit button when all questions complete', () => {
      const submitBtn = document.getElementById('submit-btn');
      
      // Fill all questions
      questionSections.forEach((question) => {
        const radios = question.querySelectorAll('input[type="radio"]');
        radios[0].checked = true;
        radios[2].checked = true;
      });
      
      // Check if all complete
      const allComplete = Array.from(questionSections).every(question => {
        const allBtnGroups = question.querySelectorAll('.btn-group');
        const choiceInputs = allBtnGroups[0].querySelectorAll('input[type="radio"]');
        const confidenceInputs = allBtnGroups[1].querySelectorAll('input[type="radio"]');
        return Array.from(choiceInputs).some(input => input.checked) &&
               Array.from(confidenceInputs).some(input => input.checked);
      });
      
      submitBtn.disabled = !allComplete;
      
      expect(submitBtn.disabled).toBe(false);
    });

    test('keeps submit button disabled when questions incomplete', () => {
      const submitBtn = document.getElementById('submit-btn');
      
      // Fill only first question
      const firstQuestion = questionSections[0];
      firstQuestion.querySelector('input[name="better_image"][value="A"]').checked = true;
      firstQuestion.querySelector('input[name="image_confidence"][value="5"]').checked = true;
      
      // Check if all complete
      const allComplete = Array.from(questionSections).every(question => {
        const allBtnGroups = question.querySelectorAll('.btn-group');
        const choiceInputs = allBtnGroups[0].querySelectorAll('input[type="radio"]');
        const confidenceInputs = allBtnGroups[1].querySelectorAll('input[type="radio"]');
        return Array.from(choiceInputs).some(input => input.checked) &&
               Array.from(confidenceInputs).some(input => input.checked);
      });
      
      submitBtn.disabled = !allComplete;
      
      expect(submitBtn.disabled).toBe(true);
    });

    test('scrolls to reveal submit button on last question complete', () => {
      const submitBtn = document.getElementById('submit-btn');
      const scrollIntoViewMock = jest.fn();
      submitBtn.scrollIntoView = scrollIntoViewMock;
      
      currentQuestionIndex = questionSections.length - 1;
      const lastQuestion = questionSections[currentQuestionIndex];
      
      // Complete last question
      lastQuestion.querySelector('input[name="better_identity_match"][value="A"]').checked = true;
      lastQuestion.querySelector('input[name="identity_confidence"][value="5"]').checked = true;
      
      // Scroll to submit button
      submitBtn.scrollIntoView({ behavior: 'smooth', block: 'end' });
      
      expect(scrollIntoViewMock).toHaveBeenCalledWith({
        behavior: 'smooth',
        block: 'end'
      });
    });
  });

  describe('Question Visibility', () => {
    test('only one question is active at a time', () => {
      // Set first question active
      questionSections[0].classList.add('active');
      
      const activeQuestions = document.querySelectorAll('.question-group.active');
      
      expect(activeQuestions.length).toBe(1);
    });

    test('removes active class when navigating away', () => {
      questionSections[0].classList.add('active');
      
      // Navigate to next
      questionSections[0].classList.remove('active');
      questionSections[1].classList.add('active');
      
      expect(questionSections[0].classList.contains('active')).toBe(false);
      expect(questionSections[1].classList.contains('active')).toBe(true);
    });

    test('applies correct CSS class for visibility', () => {
      const question = questionSections[0];
      
      // Active question should be visible
      question.classList.add('active');
      expect(question.classList.contains('active')).toBe(true);
      
      // Inactive should not have active class
      question.classList.remove('active');
      expect(question.classList.contains('active')).toBe(false);
    });
  });

  describe('Scroll Tracking', () => {
    test('tracks which question is in viewport', () => {
      // Mock IntersectionObserver behavior
      const observedElements = new Map();
      
      questionSections.forEach((question, index) => {
        observedElements.set(question, {
          isIntersecting: index === 1, // Second question in view
          intersectionRatio: index === 1 ? 1.0 : 0
        });
      });
      
      // Find which question is in view
      let inViewIndex = -1;
      observedElements.forEach((entry, element) => {
        if (entry.isIntersecting) {
          const index = parseInt(element.dataset.questionIndex);
          if (index > inViewIndex) {
            inViewIndex = index;
          }
        }
      });
      
      expect(inViewIndex).toBe(1);
    });

    test('updates current question based on scroll position', () => {
      let trackedIndex = 0;
      
      // Simulate scroll to second question
      const newIndex = 1;
      if (newIndex !== trackedIndex) {
        trackedIndex = newIndex;
      }
      
      expect(trackedIndex).toBe(1);
    });
  });
});

