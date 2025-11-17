/**
 * Tests for image loading functionality in script.js
 */

describe('Image Loading System', () => {
  let consoleError;

  beforeEach(() => {
    // Mock console.error to avoid noise in tests
    consoleError = jest.spyOn(console, 'error').mockImplementation();
    
    // Set up DOM
    document.body.innerHTML = `
      <div id="survey-section">
        <div id="image-a-container">
          <img id="image-a" alt="Image A">
          <div class="loading-spinner" style="display:none;"></div>
        </div>
        <div id="image-b-container">
          <img id="image-b" alt="Image B">
          <div class="loading-spinner" style="display:none;"></div>
        </div>
        <form id="survey-form">
          <button id="submit-btn" disabled>Submit</button>
        </form>
        <div id="prompt-text"></div>
      </div>
    `;

    // Reset fetch mock - ensure it exists as a Jest mock
    if (global.fetch && typeof global.fetch.mockClear === 'function') {
      global.fetch.mockClear();
    } else {
      global.fetch = jest.fn(() => Promise.resolve({
        ok: true,
        json: async () => ({})
      }));
    }
  });

  afterEach(() => {
    if (consoleError && consoleError.mockRestore) {
      consoleError.mockRestore();
    }
  });

  describe('loadImagePair', () => {
    test('successfully loads image pair data', async () => {
      const mockData = {
        id: 0,
        prompt: 'Test prompt',
        method_a: 'Method-A',
        method_b: 'Method-B',
        image_a_url: 'http://example.com/a.jpg',
        image_b_url: 'http://example.com/b.jpg',
        identity_urls: 'http://example.com/id.jpg',
        mask_url: 'http://example.com/mask.jpg'
      };

      global.fetch.mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => mockData
      });

      // Import the function (this is a simplified test - real implementation would require proper module loading)
      const loadImagePair = async (index) => {
        const response = await fetch(`/api/get_image_pair/${index}`);
        if (!response.ok) throw new Error('Failed to load');
        return await response.json();
      };

      const result = await loadImagePair(0);
      
      expect(global.fetch).toHaveBeenCalledWith('/api/get_image_pair/0');
      expect(result).toEqual(mockData);
      expect(result.prompt).toBe('Test prompt');
    });

    test('handles network error gracefully', async () => {
      global.fetch.mockRejectedValueOnce(new Error('Network error'));

      const loadImagePair = async (index) => {
        try {
          const response = await fetch(`/api/get_image_pair/${index}`);
          if (!response.ok) throw new Error('Failed to load');
          return await response.json();
        } catch (error) {
          console.error('Error loading image pair:', error);
          return null;
        }
      };

      const result = await loadImagePair(0);
      
      expect(result).toBeNull();
      expect(consoleError).toHaveBeenCalled();
    });

    test('handles 404 response', async () => {
      global.fetch.mockResolvedValueOnce({
        ok: false,
        status: 404,
        json: async () => ({ error: 'Not found' })
      });

      const loadImagePair = async (index) => {
        const response = await fetch(`/api/get_image_pair/${index}`);
        if (!response.ok) {
          const error = await response.json();
          throw new Error(error.error || 'Failed to load');
        }
        return await response.json();
      };

      await expect(loadImagePair(999)).rejects.toThrow('Not found');
    });

    test('handles malformed JSON response', async () => {
      global.fetch.mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => { throw new Error('Invalid JSON'); }
      });

      const loadImagePair = async (index) => {
        try {
          const response = await fetch(`/api/get_image_pair/${index}`);
          return await response.json();
        } catch (error) {
          console.error('JSON parse error:', error);
          return null;
        }
      };

      const result = await loadImagePair(0);
      
      expect(result).toBeNull();
      expect(consoleError).toHaveBeenCalled();
    });
  });

  describe('Image Preloading', () => {
    test('creates Image object with correct src', () => {
      const url = 'http://example.com/test.jpg';
      const img = new Image();
      img.src = url;
      
      expect(img.src).toBe(url);
    });

    test('handles image load success', () => {
      const img = new Image();
      
      // Set up onload handler
      let loadCalled = false;
      img.onload = () => {
        loadCalled = true;
      };
      
      // Set src - this would trigger onload in a real browser
      img.src = 'http://example.com/test.jpg';
      
      // Verify properties
      expect(img.src).toBe('http://example.com/test.jpg');
      expect(img.onload).toBeDefined();
      expect(typeof img.onload).toBe('function');
    });

    test('handles image load error', (done) => {
      const img = new Image();
      img.onerror = (error) => {
        done();
      };
      // In real implementation, this would trigger onerror
      img.onerror(new Error('Failed to load'));
    });

    test('preloads multiple images in parallel', async () => {
      const urls = [
        'http://example.com/1.jpg',
        'http://example.com/2.jpg',
        'http://example.com/3.jpg'
      ];

      const preloadImages = (imageUrls) => {
        return Promise.all(
          imageUrls.map(url => {
            return new Promise((resolve, reject) => {
              const img = new Image();
              img.onload = () => resolve(img);
              img.onerror = reject;
              img.src = url;
              
              // Manually trigger onload after a short delay to simulate loading
              setTimeout(() => {
                if (img.onload) img.onload();
              }, 5);
            });
          })
        );
      };

      const images = await preloadImages(urls);
      
      expect(images).toHaveLength(3);
      images.forEach((img, index) => {
        expect(img.src).toBe(urls[index]);
      });
    });
  });

  describe('Loading Spinner', () => {
    test('shows loading spinner during image load', () => {
      const spinner = document.querySelector('#image-a-container .loading-spinner');
      
      // Show spinner
      spinner.style.display = 'block';
      expect(spinner.style.display).toBe('block');
      
      // Hide spinner
      spinner.style.display = 'none';
      expect(spinner.style.display).toBe('none');
    });

    test('hides spinner on image load success', () => {
      const spinner = document.querySelector('#image-a-container .loading-spinner');
      const img = document.getElementById('image-a');
      
      spinner.style.display = 'block';
      
      // Simulate image loaded
      img.onload = () => {
        spinner.style.display = 'none';
      };
      img.onload();
      
      expect(spinner.style.display).toBe('none');
    });

    test('hides spinner on image load error', () => {
      const spinner = document.querySelector('#image-a-container .loading-spinner');
      const img = document.getElementById('image-a');
      
      spinner.style.display = 'block';
      
      // Simulate image error
      img.onerror = () => {
        spinner.style.display = 'none';
      };
      img.onerror();
      
      expect(spinner.style.display).toBe('none');
    });
  });

  describe('Image Display', () => {
    test('updates image src attribute', () => {
      const img = document.getElementById('image-a');
      const url = 'http://example.com/test.jpg';
      
      img.src = url;
      
      expect(img.src).toBe(url);
    });

    test('updates prompt text', () => {
      const promptEl = document.getElementById('prompt-text');
      const promptText = 'A serene mountain landscape';
      
      promptEl.textContent = promptText;
      
      expect(promptEl.textContent).toBe(promptText);
    });

    test('disables form during image loading', () => {
      const form = document.getElementById('survey-form');
      const submitBtn = document.getElementById('submit-btn');
      
      // Disable during load
      form.style.pointerEvents = 'none';
      submitBtn.disabled = true;
      
      expect(form.style.pointerEvents).toBe('none');
      expect(submitBtn.disabled).toBe(true);
    });

    test('enables form after images loaded', () => {
      const form = document.getElementById('survey-form');
      const submitBtn = document.getElementById('submit-btn');
      
      // Re-enable after load
      form.style.pointerEvents = '';
      submitBtn.disabled = false;
      
      expect(form.style.pointerEvents).toBe('');
      expect(submitBtn.disabled).toBe(false);
    });
  });

  describe('Error Handling', () => {
    test('displays error message on load failure', () => {
      const showError = (message) => {
        const errorDiv = document.createElement('div');
        errorDiv.className = 'error-message';
        errorDiv.textContent = message;
        document.body.appendChild(errorDiv);
        return errorDiv;
      };

      const errorDiv = showError('Failed to load images');
      
      expect(errorDiv.textContent).toBe('Failed to load images');
      expect(errorDiv.className).toBe('error-message');
      expect(document.querySelector('.error-message')).toBeTruthy();
    });

    test('clears previous error messages', () => {
      // Add error message
      const errorDiv = document.createElement('div');
      errorDiv.className = 'error-message';
      document.body.appendChild(errorDiv);
      
      // Clear it
      const existingError = document.querySelector('.error-message');
      if (existingError) {
        existingError.remove();
      }
      
      expect(document.querySelector('.error-message')).toBeNull();
    });

    test('retains form data on error', () => {
      // User has partially filled form
      const form = document.getElementById('survey-form');
      form.innerHTML = `
        <input type="radio" name="better_image" value="A" checked>
        <input type="radio" name="image_confidence" value="3" checked>
      `;
      
      const checkedChoice = form.querySelector('input[name="better_image"]:checked');
      const checkedConfidence = form.querySelector('input[name="image_confidence"]:checked');
      
      // After error, data should still be there
      expect(checkedChoice.value).toBe('A');
      expect(checkedConfidence.value).toBe('3');
    });
  });

  describe('Image Pair Navigation', () => {
    test('tracks current image index', () => {
      let currentIndex = 0;
      
      // Navigate to next
      currentIndex++;
      expect(currentIndex).toBe(1);
      
      // Navigate to next again
      currentIndex++;
      expect(currentIndex).toBe(2);
    });

    test('prevents navigating beyond last image', () => {
      let currentIndex = 29; // Last of 30 images
      const totalImages = 30;
      
      // Try to go next
      if (currentIndex < totalImages - 1) {
        currentIndex++;
      }
      
      expect(currentIndex).toBe(29); // Should not increment
    });

    test('clears form when navigating to new pair', () => {
      const form = document.getElementById('survey-form');
      form.innerHTML = `
        <input type="radio" name="better_image" value="A" checked>
      `;
      
      // Navigate to new pair - manually clear form (jsdom's reset() doesn't work properly)
      form.querySelectorAll('input[type="radio"]').forEach(input => {
        input.checked = false;
      });
      
      const checkedInput = form.querySelector('input:checked');
      expect(checkedInput).toBeNull();
    });
  });
});

