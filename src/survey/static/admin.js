/** Output goes to innerHTML: participant / data-file / config values must go through esc(). */

function esc(value) {
    if (value === null || value === undefined) return '';
    return String(value)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
}

function buildDemographicsHeader(demoFields) {
    let headerHtml = '<tr><th>Email</th><th>Referral</th><th>Browser</th><th>OS</th><th>Screen</th>';
    for (const f of (demoFields || [])) {
        if (f.type === 'email') continue;
        headerHtml += `<th>${esc(f.label)}</th>`;
    }
    headerHtml += '<th>Responses</th></tr>';
    return headerHtml;
}

function buildDemographicsRows(participants, demoFields, pairsPerUser) {
    return (participants || []).map(p => {
        let cells = `<td>${esc(p.email) || '-'}</td>`;
        cells += `<td>${esc(p.referral_code) || '-'}</td>`;
        cells += `<td style="font-size:11px;">${esc(p.browser) || '-'} ${esc(p.browser_version)}</td>`;
        cells += `<td>${esc(p.os) || '-'}</td>`;
        cells += `<td style="font-size:11px;">${esc(p.screen_width) || '?'}×${esc(p.screen_height) || '?'}</td>`;
        for (const f of (demoFields || [])) {
            if (f.type === 'email') continue;
            cells += `<td>${esc(p[f.name]) || '-'}</td>`;
        }
        cells += `<td><strong>${esc(p.responseCount)}/${esc(pairsPerUser)}</strong></td>`;
        return `<tr>${cells}</tr>`;
    }).join('');
}

function buildResponsesHeader(questions) {
    let headerHtml = '<tr><th>Date</th><th>Email</th><th>Pair#</th><th>Method A</th><th>Method B</th>';
    for (const q of (questions || [])) {
        if (q.type === 'ab_preference') {
            const label = q.section_label || q.name;
            headerHtml += `<th>Choice (${esc(label)})</th><th>Preferred (${esc(label)})</th>`;
            if (q.confidence) headerHtml += `<th>Conf (${esc(label)})</th>`;
        }
    }
    headerHtml += '<th>Time (s)</th></tr>';
    return headerHtml;
}

function formatTimeSpent(value) {
    // SQLite stores time_spent untyped as sent; a non-number threw and blanked the table.
    if (value === null || value === undefined || value === '') return '-';
    const n = Number(value);
    return Number.isFinite(n) ? n.toFixed(1) : '-';
}

function buildResponsesRows(rows, questions) {
    return (rows || []).map(row => {
        let cells = `<td style="font-size:11px;">${row.response_created ? esc(new Date(row.response_created).toLocaleDateString()) : '-'}</td>`;
        cells += `<td>${esc(row.email) || '-'}</td>`;
        cells += `<td>${esc(row.image_pair_id) || '-'}</td>`;
        cells += `<td style="font-size:11px;">${esc(row.method_a) || 'N/A'}</td>`;
        cells += `<td style="font-size:11px;">${esc(row.method_b) || 'N/A'}</td>`;
        for (const q of (questions || [])) {
            if (q.type === 'ab_preference') {
                const choice = row[`${q.name}_choice`] || '-';
                const pref = row[`${q.name}_preferred_method`] || '-';
                cells += `<td>${esc(choice)}</td><td><strong>${esc(pref)}</strong></td>`;
                if (q.confidence) {
                    const conf = row[`${q.name}_confidence`];
                    cells += `<td>${conf != null ? esc(conf) : '-'}</td>`;
                }
            }
        }
        cells += `<td>${row.time_spent != null ? formatTimeSpent(row.time_spent) : '-'}</td>`;
        return `<tr>${cells}</tr>`;
    }).join('');
}

if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
        esc,
        buildDemographicsHeader,
        buildDemographicsRows,
        buildResponsesHeader,
        buildResponsesRows,
        formatTimeSpent,
    };
}
