// The survey's rules - gating, payload shape, progress - kept DOM-free so they test without a browser.

export type QuestionConfig = {
    name: string;
    type: string;
    label?: string;
    section_label?: string;
    depends_on?: string;
    confidence?: boolean;
    scale?: number;
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

export type StudyConfig = {
    questions?: QuestionConfig[];
    inputs?: InputConfig[];
    demographics?: DemographicsField[];
    dev_mode?: boolean;
};

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

export function visibleQuestionNames(
    questions: QuestionConfig[],
    trial: Trial | null,
    inputs: InputConfig[],
): string[] {
    return questions.filter(q => isSectionVisible(q, trial, inputs)).map(q => q.name);
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

export function buildSubmission(
    trial: Trial,
    responses: Responses,
    timeSpent: number | null,
): Record<string, unknown> {
    // The server stores this blob as the record of what was shown; a dropped key is silent.
    return {
        image_pair_id: trial.id,
        stimulus_data: {
            prompt: trial.prompt,
            method_a: trial.method_a,
            method_b: trial.method_b,
            image_a_url: trial.image_a_url,
            image_b_url: trial.image_b_url,
            identity_urls: trial.identity_urls || null,
            mask_url: trial.mask_url || null,
            methods: trial.methods || {},
        },
        responses,
        was_randomized: trial.was_randomized,
        time_spent: timeSpent,
    };
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
