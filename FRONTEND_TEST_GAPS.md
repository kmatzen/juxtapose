# Frontend Testing Gaps Analysis

## Current Status: Minimal Coverage ⚠️

```
Total Frontend Code:  1,625 lines (script.js)
Functions/Features:   51+
Current Tests:        34 tests
Actual Coverage:      0% (not measuring real code)
Status:              ❌ NOT production ready
```

## What's Currently Tested ✅

### 1. Form Validation (validation.test.js - 17 tests)
- ✅ Submit button state (enabled/disabled)
- ✅ Radio button selection
- ✅ Demographics form validation
- ✅ Email validation
- ✅ CONFIG object availability
- ✅ IDENTITY_COLORS availability

### 2. Tutorial Mode (tutorial.test.js - 17 tests)
- ✅ Tutorial mode state management
- ✅ Banner visibility
- ✅ Step navigation (next/previous)
- ✅ Element highlighting
- ✅ Tutorial completion
- ✅ Submit button state during tutorial

## What's NOT Tested ❌

### Critical Functionality (0% coverage)

#### 1. Image Loading & Display (300+ lines)
- ❌ `loadImagePair()` - Fetching image pair data
- ❌ Image preloading logic
- ❌ Loading spinner display
- ❌ Image error handling
- ❌ Image URL validation
- ❌ Fallback image display

#### 2. Progressive Question System (400+ lines)
- ❌ `initializeProgressiveQuestions()` - Question initialization
- ❌ `navigateQuestion()` - Next/previous navigation
- ❌ `isQuestionGroupComplete()` - Completion detection
- ❌ `setupAutoAdvance()` - Auto-scroll on completion
- ❌ `updateNavigationButtons()` - Button state management
- ❌ IntersectionObserver for scroll tracking
- ❌ Current question tracking

#### 3. Layout & Responsive Design (250+ lines)
- ❌ `measureLayout()` - Dynamic height calculation
- ❌ `setQuestionsHeight()` - Questions section sizing
- ❌ `scaleVisualContent()` - Image scaling
- ❌ Mobile vs desktop layout switching
- ❌ Orientation change handling
- ❌ Resize debouncing
- ❌ Viewport calculations

#### 4. Identity/Mask Overlay System (400+ lines)
- ❌ `processMaskForOverlays()` - Canvas mask processing
- ❌ `setupIdentityHoverHandlers()` - Hover interaction
- ❌ `setupDocumentTouchHandlers()` - Touch interaction
- ❌ `showMaskOverlay()` - Overlay display
- ❌ `createOverlay()` - Canvas overlay creation
- ❌ `hideMaskOverlay()` - Overlay cleanup
- ❌ Color matching logic
- ❌ CORS handling for canvas

#### 5. Demographics Submission (100+ lines)
- ❌ `handleDemographicsSubmit()` - Form submission
- ❌ `collectDeviceInfo()` - Device data collection
- ❌ Browser detection
- ❌ OS detection
- ❌ Screen info collection
- ❌ CSRF token handling
- ❌ Server response handling
- ❌ Error display

#### 6. Survey Submission (150+ lines)
- ❌ `handleSurveySubmit()` - Response submission
- ❌ Time tracking (`pairStartTime`)
- ❌ Response data serialization
- ❌ Server communication
- ❌ Progress tracking
- ❌ Completion detection
- ❌ Thank you page redirect

#### 7. Image Lightbox (50+ lines)
- ❌ `setupImageLightbox()` - Click handlers
- ❌ Fullscreen image display
- ❌ Escape key handling
- ❌ Click-to-close
- ❌ Multiple image support

#### 8. Dev Mode Auto-fill (100+ lines)
- ❌ `fillDemographicsForm()` - Auto-populate demographics
- ❌ `fillSurveyForm()` - Auto-populate survey answers
- ❌ Dev mode indicator display
- ❌ Auto-fill timing

#### 9. Error Handling & UI Feedback
- ❌ `showError()` - Error message display
- ❌ `showRetakeModal()` - Custom modal
- ❌ Network error handling
- ❌ API error responses
- ❌ Loading state management

#### 10. Conditioning System (Identity/Mask Display)
- ❌ `displayConditioningInputs()` - Layout and display
- ❌ Image slicing for stacked identities
- ❌ Border color application
- ❌ Three-tile grid layout (AMB vs MAB)

#### 11. Miscellaneous
- ❌ `getCSRFToken()` - Token extraction
- ❌ Progress bar updates
- ❌ Session state management
- ❌ URL parameter handling

## Coverage Problems

### Jest Configuration Issues
The current Jest setup shows **0% coverage** because:

1. **Not Instrumenting Source**: Jest isn't configured to measure coverage of the actual `src/survey/static/script.js` file
2. **Mock-Based Tests**: Tests use mocked DOM, not real code
3. **No Integration**: Tests don't actually load or execute `script.js`

### Current Test Approach
```javascript
// Tests are unit tests of behavior, not code coverage
expect(submitButton).toBeDisabled();  // Tests UI state
// But doesn't execute actual validateForm() from script.js
```

## Impact Assessment

### Risk Level: HIGH ⚠️

| Area | Tested | Risk |
|------|--------|------|
| Form Validation | 30% | Medium |
| Tutorial System | 60% | Low |
| Image Loading | 0% | **HIGH** |
| Progressive Questions | 0% | **HIGH** |
| Layout/Responsive | 0% | **HIGH** |
| Identity/Mask System | 0% | **CRITICAL** |
| Submissions | 0% | **HIGH** |
| Error Handling | 0% | **HIGH** |

### Production Readiness

❌ **Backend**: 78% coverage, production ready  
❌ **Frontend**: ~5% actual coverage, **NOT production ready**

## Recommendations

### Immediate (High Priority)

1. **Fix Jest Coverage Configuration**
   ```javascript
   // jest.config.js
   collectCoverageFrom: [
     'src/survey/static/script.js'
   ]
   ```

2. **Add Integration Tests** (20-30 tests)
   - Image loading flow
   - Form submissions
   - Progressive questions
   - Error handling

3. **Add E2E Tests** (10-15 scenarios)
   - Complete survey flow
   - Mobile interactions
   - Identity hover/tap
   - Lightbox functionality

### Short-term

4. **Add Component Tests** (30-40 tests)
   - Layout calculations
   - Identity/mask overlays
   - Device info collection
   - CSRF handling

5. **Add Visual Regression Tests**
   - Layout on different screen sizes
   - Mobile responsiveness
   - Tutorial highlighting

### Long-term

6. **Refactor for Testability**
   - Extract functions from DOMContentLoaded
   - Modularize large functions
   - Dependency injection for fetch/DOM

7. **Add Performance Tests**
   - Image loading speed
   - Layout calculation time
   - Scroll performance

## Estimated Effort

| Task | Tests Needed | Time | Coverage Gain |
|------|--------------|------|---------------|
| Fix coverage config | - | 1 hour | Enable measurement |
| Image loading tests | 15 | 4 hours | +10% |
| Submission tests | 10 | 3 hours | +8% |
| Layout tests | 15 | 4 hours | +12% |
| Identity/mask tests | 20 | 6 hours | +15% |
| Progressive Q tests | 15 | 4 hours | +10% |
| Error handling tests | 10 | 2 hours | +5% |
| **TOTAL** | **~85 tests** | **~24 hours** | **~60% coverage** |

## Priority Test Cases

### Must Have (P0)
1. ✅ Form validation (done)
2. ❌ Image loading & error handling
3. ❌ Survey submission flow
4. ❌ Demographics submission
5. ❌ Progressive question navigation

### Should Have (P1)
6. ✅ Tutorial system (done)
7. ❌ Identity/mask overlay system
8. ❌ Image lightbox
9. ❌ Layout calculations
10. ❌ Error message display

### Nice to Have (P2)
11. ❌ Dev mode auto-fill
12. ❌ CSRF token handling
13. ❌ Mobile touch interactions
14. ❌ Resize handling
15. ❌ Time tracking

## Conclusion

**Current State**: The frontend has minimal test coverage (~5% actual, 34 behavioral tests)

**Gap**: ~1,500 lines of untested JavaScript with complex interactions

**Risk**: HIGH - Production deployment without proper frontend testing is risky

**Recommendation**: Add at least 50-80 more frontend tests before considering production-ready, focusing on:
- Image loading & display
- Form submissions
- Progressive question system
- Identity/mask overlays
- Error handling

**Timeline**: 2-3 weeks for comprehensive frontend testing

