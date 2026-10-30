// The survey's rules - gating, payload shape, progress - kept DOM-free so they test without a browser.

export type QuestionConfig = {
    name: string;
    type: string;
    label?: string;
    section_label?: string;
    depends_on?: string;
    confidence?: boolean;
    scale?: number;
    required?: boolean;
};

export type InputConfig = {
    name: string;
    type: string;
    column: string;
    label?: string;
};

export type DemographicsField = {
    name: string;
    type: string;
    label?: string;
    options?: { value: string; label: string }[];
};

export type OutputConfig = {
    name: string;
    type: string;
    column_a?: string;
    column_b?: string;
};

export type TutorialStepConfig = {
    title?: string;
    text?: string;
    highlight?: string | null;
    highlightParent?: boolean;
    scrollToWithin?: string;
};

export type StudyConfig = {
    questions?: QuestionConfig[];
    inputs?: InputConfig[];
    outputs?: OutputConfig[];
    demographics?: DemographicsField[];
    tutorial?: { steps?: (TutorialStepConfig | 'auto_questions')[] };
    dev_mode?: boolean;
};

export type TutorialStep = {
    title: string;
    text: string;
    emphasis?: string;
    highlight?: string | null;
    highlightParent?: boolean;
    scrollToWithin?: string;
};

// 'auto_questions' is a placeholder the author writes once; it expands to one step per question.
export function buildTutorialSteps(config: StudyConfig): TutorialStep[] {
    const configured = config.tutorial?.steps;
    if (!configured?.length) {
        return [{ title: 'Tutorial', text: 'No tutorial steps configured.', highlight: null }];
    }

    const steps: TutorialStep[] = [];
    for (const step of configured) {
        if (step === 'auto_questions') {
            for (const q of config.questions ?? []) {
                const label = q.label ?? q.name;
                steps.push({
                    title: q.section_label ?? label,
                    text: label,
                    emphasis: label,
                    highlight: '.questions-container',
                    scrollToWithin: `#${q.name}-evaluation`,
                });
            }
        } else {
            steps.push({ ...step, title: step.title ?? '', text: step.text ?? '' });
        }
    }
    return steps;
}

export type Trial = {
    id: number;
    prompt: string;
    method_a: string;
    method_b: string;
    image_a_url: string;
    image_b_url: string;
    identity_urls?: string | null;
    mask_url?: string | null;
    methods?: Record<string, unknown>;
    was_randomized?: boolean;
    total_pairs: number;
    trials_remaining?: number;
    [column: string]: unknown;
};

export type FormFields = Record<string, string | undefined>;

export type AnswerValue = {
    choice?: string;
    confidence?: number | null;
    value?: number | string;
    text?: string;
};

export type Responses = Record<string, AnswerValue>;

export type RadioState = { name: string; checked: boolean; hidden: boolean };

export function isSectionVisible(
    question: QuestionConfig,
    trial: Trial | null,
    inputs: InputConfig[],
): boolean {
    if (!question.depends_on) return true;
    const input = inputs.find(i => i.name === question.depends_on);
    if (!input) return true;
    return String((trial && trial[input.column]) || '').trim() !== '';
}

const toInt = (raw: string | undefined): number | null => {
    if (raw === undefined || raw === '') return null;
    const parsed = Number.parseInt(raw, 10);
    return Number.isNaN(parsed) ? null : parsed;
};

export function buildResponses(
    questions: QuestionConfig[],
    fields: FormFields,
    visibleNames: string[],
): Responses {
    const visible = new Set(visibleNames);
    const responses: Responses = {};

    for (const question of questions) {
        if (!visible.has(question.name)) continue;

        if (question.type === 'ab_preference') {
            const choice = fields[`${question.name}_choice`];
            if (choice) {
                responses[question.name] = { choice, confidence: toInt(fields[`${question.name}_confidence`]) };
            }
        } else if (question.type === 'likert') {
            const value = toInt(fields[`${question.name}_value`]);
            if (value !== null) responses[question.name] = { value };
        } else if (question.type === 'free_text') {
            responses[question.name] = { text: fields[`${question.name}_text`] || '' };
        } else if (question.type === 'multiple_choice') {
            const value = fields[`${question.name}_value`];
            if (value) responses[question.name] = { value };
        }
    }

    return responses;
}

export function progressFrom(
    trial: Pick<Trial, 'total_pairs' | 'trials_remaining'>,
    index: number,
): { current: number; total: number; percent: number } {
    // A resumed session restarts at index 0, so the server's remaining count beats the index.
    const total = trial.total_pairs;
    const remaining = trial.trials_remaining ?? (total - index);
    const current = total - remaining + 1;
    return { current, total, percent: total > 0 ? ((total - remaining) / total) * 100 : 0 };
}

export function isFormComplete(radios: RadioState[], emptyIsComplete = false): boolean {
    // Hidden sections gate nothing: their radios stay in the form, so filter before grouping.
    const groups: Record<string, boolean> = {};
    for (const radio of radios) {
        if (radio.hidden) continue;
        groups[radio.name] = (groups[radio.name] || false) || radio.checked;
    }
    const answered = Object.values(groups);
    if (answered.length === 0) return emptyIsComplete;
    return answered.every(Boolean);
}

export function detectBrowser(
    userAgent: string,
): { browser: string; browserVersion: string } {
    const ua = userAgent || '';
    const capture = (pattern: RegExp): string => ua.match(pattern)?.[1] || '';

    // Edge's UA contains "Chrome" too, so order is the algorithm here.
    if (ua.includes('Firefox')) return { browser: 'Firefox', browserVersion: capture(/Firefox\/(\d+\.\d+)/) };
    if (ua.includes('Edg') || ua.includes('Edge')) return { browser: 'Edge', browserVersion: capture(/Edg(?:e)?\/(\d+\.\d+)/) };
    if (ua.includes('Chrome')) return { browser: 'Chrome', browserVersion: capture(/Chrome\/(\d+\.\d+)/) };
    if (ua.includes('Safari')) return { browser: 'Safari', browserVersion: capture(/Version\/(\d+\.\d+)/) };
    return { browser: 'Unknown', browserVersion: '' };
}

export function detectOs(userAgent: string, maxTouchPoints: number): string {
    const ua = userAgent || '';
    // iPadOS reports as Mac; touch points are the only signal that separates them.
    const isIOS = /iPad|iPhone|iPod/.test(ua) || (ua.includes('Mac') && maxTouchPoints > 1);
    if (isIOS) return 'iOS';
    if (ua.includes('Android')) return 'Android';
    if (ua.includes('Win')) return 'Windows';
    if (ua.includes('Mac')) return 'macOS';
    if (ua.includes('Linux')) return 'Linux';
    return 'Unknown';
}

export function normalizeDemographics(
    entries: [string, string][],
    checkboxFields: string[],
): Record<string, string | string[]> {
    const data: Record<string, string | string[]> = {};

    for (const [key, value] of entries) {
        if (key.endsWith('[]')) {
            const name = key.slice(0, -2);
            const list = data[name];
            if (Array.isArray(list)) list.push(value);
            else data[name] = [value];
        } else {
            data[key] = value;
        }
    }

    // Unchecked boxes submit nothing; an empty column reads as "skipped" downstream.
    for (const field of checkboxFields) {
        const value = data[field];
        if (Array.isArray(value)) data[field] = value.join(', ');
        else if (!value) data[field] = 'none';
    }

    return data;
}

/** Region colours the spatial mask encodes identity membership with, in identity order. */
// The palette lives in JSON because the e2e fixture paints mask regions with these bytes and the
// overlay spec asserts them back; three copies of a table that must match exactly is a drift bug.
import identityColorsJson from './identity-colors.json';

export const IDENTITY_COLORS: readonly (readonly number[])[] = identityColorsJson;

export type BinaryMask = { data: Uint8Array; width: number; height: number; matchCount: number };
export type MaskSet = Record<number, BinaryMask>;

// The mask is authored with these exact colours, but antialiasing at region edges lands a pixel a
// few steps off, so a match is within 10 per channel rather than exact.
const COLOR_TOLERANCE = 10;

/** Split one spatial mask into a binary mask per identity colour. */
export function extractIdentityMasks(rgba: Uint8ClampedArray, width: number, height: number): MaskSet {
    const masks: MaskSet = {};
    IDENTITY_COLORS.forEach((color, index) => {
        const data = new Uint8Array(width * height);
        let matchCount = 0;
        for (let i = 0; i < data.length; i += 1) {
            const p = i * 4;
            const match = Math.abs(rgba[p] - color[0]) < COLOR_TOLERANCE
                && Math.abs(rgba[p + 1] - color[1]) < COLOR_TOLERANCE
                && Math.abs(rgba[p + 2] - color[2]) < COLOR_TOLERANCE;
            data[i] = match ? 255 : 0;
            if (match) matchCount += 1;
        }
        masks[index] = { data, width, height, matchCount };
    });
    return masks;
}

/** Paint a mask as a semi-transparent identity-coloured overlay (RGBA, one pixel per mask cell). */
export function buildOverlayRgba(mask: BinaryMask, color: readonly number[]): Uint8ClampedArray {
    const out = new Uint8ClampedArray(mask.width * mask.height * 4);
    for (let i = 0; i < mask.data.length; i += 1) {
        const p = i * 4;
        if (mask.data[i] > 0) {
            out[p] = color[0];
            out[p + 1] = color[1];
            out[p + 2] = color[2];
            out[p + 3] = 100;
        } else {
            out[p + 3] = 0;
        }
    }
    return out;
}

/** A comma list is N images; a lone URL is one vertically stacked sheet of square segments. */
export function countStackedSegments(width: number, height: number): number {
    return Math.round(height / width);
}
