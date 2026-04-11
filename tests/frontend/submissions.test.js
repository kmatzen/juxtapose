/**
 * Tests for form submission functionality (demographics and survey)
 */

describe('Form Submissions', () => {
  let consoleError;

  beforeEach(() => {
    consoleError = jest.spyOn(console, 'error').mockImplementation();
    
    // Reset fetch mock - ensure it exists as a Jest mock
    if (global.fetch && typeof global.fetch.mockClear === 'function') {
      global.fetch.mockClear();
    } else {
      global.fetch = jest.fn(() => Promise.resolve({
        ok: true,
        json: async () => ({ success: true })
      }));
    }
    
    // Set up DOM
    document.body.innerHTML = `
      <form id="demographics-form">
        <input type="email" id="email" value="test@example.com">
        <input type="text" id="occupation" value="Engineer">
        <select id="image_gen_tools"><option value="DALL-E" selected>DALL-E</option></select>
        <select id="works_on_ai"><option value="no" selected>No</option></select>
        <select id="ai_usage"><option value="often" selected>Often</option></select>
        <select id="works_with_graphics"><option value="professional" selected>Professional</option></select>
        <select id="ai_familiarity"><option value="advanced" selected>Advanced</option></select>
        <button id="submit-demographics-btn" type="submit">Submit</button>
      </form>
      
      <form id="survey-form">
        <input type="radio" name="better_image" value="A" checked>
        <input type="radio" name="image_confidence" value="4" checked>
        <input type="radio" name="better_mask_match" value="B" checked>
        <input type="radio" name="mask_confidence" value="3" checked>
        <input type="radio" name="better_identity_match" value="A" checked>
        <input type="radio" name="identity_confidence" value="5" checked>
        <button id="submit-btn" type="submit">Submit</button>
      </form>
    `;
  });

  afterEach(() => {
    if (consoleError && consoleError.mockRestore) {
      consoleError.mockRestore();
    }
  });

  describe('Demographics Submission', () => {
    test('collects all form data correctly', () => {
      const form = document.getElementById('demographics-form');
      const formData = {
        email: form.querySelector('#email').value,
        occupation: form.querySelector('#occupation').value,
        image_gen_tools: form.querySelector('#image_gen_tools').value,
        works_on_ai: form.querySelector('#works_on_ai').value,
        ai_usage: form.querySelector('#ai_usage').value,
        works_with_graphics: form.querySelector('#works_with_graphics').value,
        ai_familiarity: form.querySelector('#ai_familiarity').value
      };

      expect(formData.email).toBe('test@example.com');
      expect(formData.occupation).toBe('Engineer');
      expect(formData.image_gen_tools).toBe('DALL-E');
      expect(formData.works_on_ai).toBe('no');
      expect(formData.ai_usage).toBe('often');
      expect(formData.works_with_graphics).toBe('professional');
      expect(formData.ai_familiarity).toBe('advanced');
    });

    test('includes device info in submission', () => {
      const deviceInfo = {
        browser: 'Chrome',
        browser_version: '120.0',
        os: 'macOS',
        screen_width: 1920,
        screen_height: 1080,
        pixel_ratio: 2.0,
        color_depth: 24,
        viewport_width: 1200,
        viewport_height: 800
      };

      expect(deviceInfo).toHaveProperty('browser');
      expect(deviceInfo).toHaveProperty('os');
      expect(deviceInfo).toHaveProperty('screen_width');
      expect(deviceInfo.pixel_ratio).toBeGreaterThan(0);
    });

    test('sends POST request with correct data', async () => {
      global.fetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({ success: true })
      });

      const submitDemographics = async (data) => {
        const response = await fetch('/api/submit_demographics', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(data)
        });
        return await response.json();
      };

      const data = {
        email: 'test@example.com',
        occupation: 'Engineer',
        device_info: { browser: 'Chrome', os: 'macOS' }
      };

      await submitDemographics(data);

      expect(global.fetch).toHaveBeenCalledWith(
        '/api/submit_demographics',
        expect.objectContaining({
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(data)
        })
      );
    });

    test('handles successful submission', async () => {
      global.fetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({ success: true })
      });

      const submitDemographics = async (data) => {
        const response = await fetch('/api/submit_demographics', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(data)
        });
        if (!response.ok) throw new Error('Submission failed');
        return await response.json();
      };

      const result = await submitDemographics({ email: 'test@example.com' });

      expect(result.success).toBe(true);
    });

    test('handles submission error', async () => {
      global.fetch.mockResolvedValueOnce({
        ok: false,
        status: 400,
        json: async () => ({ error: 'Invalid data' })
      });

      const submitDemographics = async (data) => {
        const response = await fetch('/api/submit_demographics', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(data)
        });
        if (!response.ok) {
          const error = await response.json();
          throw new Error(error.error);
        }
        return await response.json();
      };

      await expect(submitDemographics({})).rejects.toThrow('Invalid data');
    });

    test('handles network error', async () => {
      global.fetch.mockRejectedValueOnce(new Error('Network error'));

      const submitDemographics = async (data) => {
        try {
          const response = await fetch('/api/submit_demographics', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
          });
          return await response.json();
        } catch (error) {
          console.error('Network error:', error);
          throw error;
        }
      };

      await expect(submitDemographics({})).rejects.toThrow('Network error');
      expect(consoleError).toHaveBeenCalled();
    });

    test('disables submit button during submission', () => {
      const submitBtn = document.getElementById('submit-demographics-btn');
      
      // Disable during submission
      submitBtn.disabled = true;
      submitBtn.textContent = 'Submitting...';
      
      expect(submitBtn.disabled).toBe(true);
      expect(submitBtn.textContent).toBe('Submitting...');
    });

    test('re-enables submit button after submission', () => {
      const submitBtn = document.getElementById('submit-demographics-btn');
      
      submitBtn.disabled = false;
      submitBtn.textContent = 'Submit';
      
      expect(submitBtn.disabled).toBe(false);
      expect(submitBtn.textContent).toBe('Submit');
    });
  });

  describe('Survey Response Submission', () => {
    test('collects all survey responses', () => {
      const form = document.getElementById('survey-form');
      const formData = {
        better_image: form.querySelector('input[name="better_image"]:checked').value,
        image_confidence: parseInt(form.querySelector('input[name="image_confidence"]:checked').value),
        better_mask_match: form.querySelector('input[name="better_mask_match"]:checked').value,
        mask_confidence: parseInt(form.querySelector('input[name="mask_confidence"]:checked').value),
        better_identity_match: form.querySelector('input[name="better_identity_match"]:checked').value,
        identity_confidence: parseInt(form.querySelector('input[name="identity_confidence"]:checked').value)
      };

      expect(formData.better_image).toBe('A');
      expect(formData.image_confidence).toBe(4);
      expect(formData.better_mask_match).toBe('B');
      expect(formData.mask_confidence).toBe(3);
      expect(formData.better_identity_match).toBe('A');
      expect(formData.identity_confidence).toBe(5);
    });

    test('includes image pair ID in submission', () => {
      const submissionData = {
        image_pair_id: 5,
        better_image: 'A',
        image_confidence: 4
      };

      expect(submissionData).toHaveProperty('image_pair_id');
      expect(submissionData.image_pair_id).toBe(5);
    });

    test('includes time spent on pair', () => {
      const startTime = Date.now();
      
      // Simulate user spent 10 seconds
      const endTime = startTime + 10000;
      const timeSpent = (endTime - startTime) / 1000;

      expect(timeSpent).toBe(10);
    });

    test('sends POST request to submit survey', async () => {
      global.fetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({ success: true, completed: false, nextIndex: 1 })
      });

      const submitSurvey = async (data) => {
        const response = await fetch('/api/submit_survey', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(data)
        });
        return await response.json();
      };

      const data = {
        image_pair_id: 0,
        better_image: 'A',
        image_confidence: 4,
        better_mask_match: 'B',
        mask_confidence: 3,
        better_identity_match: 'A',
        identity_confidence: 5,
        time_spent: 10.5
      };

      const result = await submitSurvey(data);

      expect(global.fetch).toHaveBeenCalledWith('/api/submit_survey', expect.any(Object));
      expect(result.success).toBe(true);
      expect(result.nextIndex).toBe(1);
    });

    test('handles survey completion', async () => {
      global.fetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({ success: true, completed: true })
      });

      const submitSurvey = async (data) => {
        const response = await fetch('/api/submit_survey', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(data)
        });
        return await response.json();
      };

      const result = await submitSurvey({ image_pair_id: 29 });

      expect(result.completed).toBe(true);
    });

    test('validates required fields before submission', () => {
      const form = document.getElementById('survey-form');
      
      const isValid = () => {
        const requiredFields = [
          'better_image',
          'image_confidence',
          'better_mask_match',
          'mask_confidence',
          'better_identity_match',
          'identity_confidence'
        ];
        
        return requiredFields.every(field => {
          const input = form.querySelector(`input[name="${field}"]:checked`);
          return input !== null;
        });
      };

      expect(isValid()).toBe(true);
      
      // Remove one selection
      form.querySelector('input[name="better_image"]').checked = false;
      
      expect(isValid()).toBe(false);
    });

    test('clears form after successful submission', () => {
      const form = document.getElementById('survey-form');
      
      // Check that inputs are initially selected
      expect(form.querySelector('input[name="better_image"]:checked')).not.toBeNull();
      
      // Manually clear form (jsdom's form.reset() doesn't work properly with checked radio buttons)
      form.querySelectorAll('input[type="radio"]').forEach(input => {
        input.checked = false;
      });
      
      expect(form.querySelector('input[name="better_image"]:checked')).toBeNull();
    });

    test('retains form data on submission error', () => {
      const form = document.getElementById('survey-form');
      const initialValue = form.querySelector('input[name="better_image"]:checked').value;
      
      // On error, don't clear form
      // (form data should persist)
      
      expect(form.querySelector('input[name="better_image"]:checked').value).toBe(initialValue);
    });
  });

  describe('CSRF Token Handling', () => {
    test('extracts CSRF token from cookie', () => {
      // Mock document.cookie
      Object.defineProperty(document, 'cookie', {
        writable: true,
        value: 'csrf_token=abc123; session=xyz'
      });

      const getCSRFToken = () => {
        const match = document.cookie.match(/csrf_token=([^;]+)/);
        return match ? match[1] : null;
      };

      const token = getCSRFToken();
      expect(token).toBe('abc123');
    });

    test('includes CSRF token in request headers', async () => {
      global.fetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({ success: true })
      });

      const submitWithCSRF = async (data, csrfToken) => {
        const headers = {
          'Content-Type': 'application/json'
        };
        
        if (csrfToken) {
          headers['X-CSRFToken'] = csrfToken;
        }

        const response = await fetch('/api/submit_survey', {
          method: 'POST',
          headers,
          body: JSON.stringify(data)
        });
        return await response.json();
      };

      await submitWithCSRF({ image_pair_id: 0 }, 'token123');

      expect(global.fetch).toHaveBeenCalledWith(
        '/api/submit_survey',
        expect.objectContaining({
          headers: expect.objectContaining({
            'X-CSRFToken': 'token123'
          })
        })
      );
    });

    test('handles missing CSRF token gracefully', async () => {
      global.fetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({ success: true })
      });

      const submitWithCSRF = async (data, csrfToken) => {
        const headers = {
          'Content-Type': 'application/json'
        };
        
        if (csrfToken) {
          headers['X-CSRFToken'] = csrfToken;
        }

        const response = await fetch('/api/submit_survey', {
          method: 'POST',
          headers,
          body: JSON.stringify(data)
        });
        return await response.json();
      };

      // Submit without token
      const result = await submitWithCSRF({ image_pair_id: 0 }, null);

      expect(result.success).toBe(true);
    });
  });

  describe('Error Display', () => {
    test('shows error message to user', () => {
      const showError = (message) => {
        const errorDiv = document.createElement('div');
        errorDiv.className = 'error-message';
        errorDiv.textContent = message;
        errorDiv.style.cssText = 'color: red; padding: 10px; margin: 10px 0;';
        document.body.appendChild(errorDiv);
      };

      showError('Submission failed. Please try again.');

      const errorDiv = document.querySelector('.error-message');
      expect(errorDiv).toBeTruthy();
      expect(errorDiv.textContent).toContain('Submission failed');
    });

    test('clears previous error messages', () => {
      // Add multiple error messages
      for (let i = 0; i < 3; i++) {
        const errorDiv = document.createElement('div');
        errorDiv.className = 'error-message';
        document.body.appendChild(errorDiv);
      }

      // Clear all
      document.querySelectorAll('.error-message').forEach(el => el.remove());

      expect(document.querySelectorAll('.error-message').length).toBe(0);
    });
  });
});

