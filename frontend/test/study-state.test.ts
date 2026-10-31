import { describe, expect, it } from 'vitest';

import {
  buildResponses,
  detectBrowser,
  detectOs,
  idSelector,
  isFormComplete,
  isSectionVisible,
  normalizeDemographics,
  progressFrom,
  type InputConfig,
  type QuestionConfig,
  type Trial,
} from '../src/study-state';

const TRIAL: Trial = {
  id: 7,
  prompt: 'a red cube',
  method_a: 'MethodA',
  method_b: 'MethodB',
  image_a_url: 'https://img/a.png',
  image_b_url: 'https://img/b.png',
  identity_urls: 'https://img/id.png',
  mask_url: 'https://img/mask.png',
  methods: { method_a: 'MethodA' },
  was_randomized: true,
  total_pairs: 30,
  trials_remaining: 30,
};

const INPUTS: InputConfig[] = [
  { name: 'mask', type: 'image', column: 'mask_url', label: 'Mask' },
  { name: 'identity', type: 'image_gallery', column: 'identity_urls' },
];

const QUESTIONS: QuestionConfig[] = [
  { name: 'image', type: 'ab_preference', confidence: true, section_label: 'Image' },
  { name: 'mask', type: 'ab_preference', confidence: true, depends_on: 'mask', section_label: 'Mask' },
  { name: 'identity', type: 'likert', depends_on: 'identity' },
  { name: 'comment', type: 'free_text' },
  { name: 'tags', type: 'multiple_choice' },
];

// The components ask the question-flow for this; the module exports the predicate, not the list.
const visibleNames = (trial: Trial | null) =>
  QUESTIONS.filter(q => isSectionVisible(q, trial, INPUTS)).map(q => q.name);

describe('id selectors built from config names', () => {
    it('selects a name that is not a legal selector', () => {
        expect(idSelector('quality (1-5)-evaluation')).toBe('[id="quality (1-5)-evaluation"]');
        expect(idSelector('a"b')).toBe('[id="a\\"b"]');
    });
});

describe('question gating', () => {
  it('gates a dependent question on its input column having a value', () => {
    const mask = QUESTIONS[1];
    expect(isSectionVisible(mask, TRIAL, INPUTS)).toBe(true);
    expect(isSectionVisible(mask, { ...TRIAL, mask_url: '' }, INPUTS)).toBe(false);
    expect(isSectionVisible(mask, { ...TRIAL, mask_url: null }, INPUTS)).toBe(false);
    expect(isSectionVisible(mask, { ...TRIAL, mask_url: '   ' }, INPUTS)).toBe(false);
  });

  it("shows a mask-free trial's questions that do not depend on the mask", () => {
    const trial = { ...TRIAL, mask_url: '' };
    expect(visibleNames(trial)).toEqual(['image', 'identity', 'comment', 'tags']);
  });

  it('shows a dependent question when the dependency names no input', () => {
    const orphan: QuestionConfig = { name: 'x', type: 'likert', depends_on: 'nope' };
    expect(isSectionVisible(orphan, TRIAL, INPUTS)).toBe(true);
  });

  it('treats a trial with no data as hiding dependent questions', () => {
    expect(isSectionVisible(QUESTIONS[1], null, INPUTS)).toBe(false);
  });
});

describe('answer assembly', () => {
  it('records the shape the server flattens into columns', () => {
    const fields = {
      image_choice: 'A',
      image_confidence: '4',
      mask_choice: 'B',
      comment_text: 'looks good',
      tags_value: 'sharp',
      identity_value: '3',
    };
    expect(buildResponses(QUESTIONS, fields, visibleNames(TRIAL))).toEqual({
      image: { choice: 'A', confidence: 4 },
      mask: { choice: 'B', confidence: null },
      identity: { value: 3 },
      comment: { text: 'looks good' },
      tags: { value: 'sharp' },
    });
  });

  it('leaves an unanswered choice out, so the server sees no answer', () => {
    const responses = buildResponses([QUESTIONS[0]], { image_confidence: '3' }, ['image']);
    expect(responses).toEqual({});
  });

  it('keeps a blank free-text answer as an empty string, not a missing key', () => {
    expect(buildResponses([QUESTIONS[3]], {}, ['comment'])).toEqual({ comment: { text: '' } });
  });

  it('drops answers from sections the trial hid', () => {
    const fields = { image_choice: 'A', mask_choice: 'B' };
    expect(buildResponses(QUESTIONS, fields, ['image'])).toEqual({ image: { choice: 'A', confidence: null } });
  });

  it('nulls a confidence that is not a number', () => {
    const responses = buildResponses([QUESTIONS[0]], { image_choice: 'A', image_confidence: 'high' }, ['image']);
    expect(responses.image.confidence).toBeNull();
  });
});

describe('progress', () => {
  it('counts from the index on a fresh session', () => {
    expect(progressFrom({ total_pairs: 30 }, 0)).toEqual({ current: 1, total: 30, percent: 0 });
    expect(progressFrom({ total_pairs: 30 }, 9).current).toBe(10);
  });

  it('counts from the server after a resume, where index restarts at 0', () => {
    expect(progressFrom({ total_pairs: 30, trials_remaining: 11 }, 0)).toEqual({
      current: 20, total: 30, percent: (19 / 30) * 100,
    });
  });

  it('survives a config with no pairs', () => {
    expect(progressFrom({ total_pairs: 0 }, 0).percent).toBe(0);
  });
});

describe('submit gating', () => {
  const radio = (name: string, checked: boolean, hidden = false) => ({ name, checked, hidden });

  it('requires every visible radio group to have a selection', () => {
    expect(isFormComplete([radio('a', true), radio('b', true)])).toBe(true);
    expect(isFormComplete([radio('a', true), radio('b', false), radio('b', false)])).toBe(false);
  });

  it('ignores groups inside hidden sections, which is what kept the mask question blocking submit', () => {
    expect(isFormComplete([radio('a', true), radio('mask_choice', false, true)])).toBe(true);
  });

  it('refuses to enable submit on a form with no answerable groups', () => {
    expect(isFormComplete([])).toBe(false);
    expect(isFormComplete([radio('a', false, true)])).toBe(false);
  });

  it('lets a text-only section count as complete when asked', () => {
    expect(isFormComplete([], true)).toBe(true);
  });
});

describe('device detection', () => {
  const UA = {
    chrome: 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    edge: 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.2210.91',
    firefox: 'Mozilla/5.0 (X11; Linux x86_64; rv:121.0) Gecko/20100101 Firefox/121.0',
    safari: 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15',
  };

  it('names Edge before Chrome, because its UA claims both', () => {
    expect(detectBrowser(UA.edge)).toEqual({ browser: 'Edge', browserVersion: '120.0' });
    expect(detectBrowser(UA.chrome)).toEqual({ browser: 'Chrome', browserVersion: '120.0' });
    expect(detectBrowser(UA.firefox)).toEqual({ browser: 'Firefox', browserVersion: '121.0' });
    expect(detectBrowser(UA.safari)).toEqual({ browser: 'Safari', browserVersion: '17.1' });
    expect(detectBrowser('curl/8.0').browser).toBe('Unknown');
  });

  it('names an iOS browser by the token it ships under', () => {
    const ios = {
      chrome: 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) CriOS/125.0.6422.80 Mobile/15E148 Safari/604.1',
      firefox: 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) FxiOS/125.0 Mobile/15E148 Safari/605.1.15',
      edge: 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) EdgiOS/125.0.2535.79 Mobile/15E148 Safari/604.1',
    };
    expect(detectBrowser(ios.chrome)).toEqual({ browser: 'Chrome', browserVersion: '125.0' });
    expect(detectBrowser(ios.firefox)).toEqual({ browser: 'Firefox', browserVersion: '125.0' });
    expect(detectBrowser(ios.edge)).toEqual({ browser: 'Edge', browserVersion: '125.0' });
    expect(detectOs(ios.chrome, 3)).toBe('iOS');
  });

  it('reports an iPad in desktop mode as iOS, not macOS', () => {
    const macUa = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15';
    expect(detectOs(macUa, 5)).toBe('iOS');
    expect(detectOs(macUa, 0)).toBe('macOS');
    expect(detectOs('Mozilla/5.0 (iPhone; CPU iPhone OS 17_1 like Mac OS X)', 3)).toBe('iOS');
    expect(detectOs('Mozilla/5.0 (Linux; Android 14)', 5)).toBe('Android');
    expect(detectOs('Mozilla/5.0 (Windows NT 10.0)', 0)).toBe('Windows');
    expect(detectOs('Mozilla/5.0 (X11; Linux x86_64)', 0)).toBe('Linux');
  });
});

describe('demographics assembly', () => {
  it('merges checkbox arrays and joins them for the column', () => {
    const entries: [string, string][] = [
      ['email', 'a@b.c'],
      ['tools[]', 'ps'],
      ['tools[]', 'figma'],
      ['occupation', 'designer'],
    ];
    expect(normalizeDemographics(entries, ['tools'])).toEqual({
      email: 'a@b.c',
      tools: 'ps, figma',
      occupation: 'designer',
    });
  });

  it('records "none" for an unchecked box, so an empty column never means skipped', () => {
    expect(normalizeDemographics([['email', 'a@b.c']], ['tools'])).toEqual({
      email: 'a@b.c',
      tools: 'none',
    });
  });

  it('leaves a non-checkbox field that submitted nothing alone', () => {
    expect(normalizeDemographics([['email', 'a@b.c']], [])).toEqual({ email: 'a@b.c' });
  });
});
