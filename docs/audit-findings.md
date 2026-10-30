# Audit findings and their disposition

Source: three full-repo senior-engineer audits (correctness, security, scale, tests, speed, lean) of the
survey app, 2026-11, 2026-11-05 and 2026-11-06. Each in-scope finding is one PR, merged with CI green on the
merge SHA. The first audit's findings are the table below; the second audit's are in
[Second audit, 2026-11-05](#second-audit-2026-11-05) and the third's in
[Third audit, 2026-11-06](#third-audit-2026-11-06).

| # | Finding | Disposition |
|---|---|---|
| 1 | `debug=DEV_MODE` served the Werkzeug debugger on `0.0.0.0` | Fixed - [#55](https://github.com/kmatzen/juxtapose/pull/55) |
| 2 | Production inferred from `bool(DATA_DIR)`: gates fail open when unset | Fixed - [#57](https://github.com/kmatzen/juxtapose/pull/57) (`APP_ENV`) |
| 3 | No WAL, no busy timeout: parallel submits 500 and lose answers | Fixed - [#59](https://github.com/kmatzen/juxtapose/pull/59) |
| 4 | `APP_ENV=production` + `DEV_MODE=true` was representable | Fixed - [#58](https://github.com/kmatzen/juxtapose/pull/58) |
| 5 | Browser-reported `time_spent` stored unbounded, feeding the averages | Fixed - [#61](https://github.com/kmatzen/juxtapose/pull/61) (`timing_flag`, raw value kept) |
| 6 | "Config re-read on every pair request" | **Retracted** - the code read the config parsed at import; the guarantee is now tested ([#60](https://github.com/kmatzen/juxtapose/pull/60)) |
| 7 | Whole study materialised per worker; per-request linear scan | Fixed - [#62](https://github.com/kmatzen/juxtapose/pull/62) (32.9 MB → 1.4 MB per worker at 50k pairs) |
| 8 | No test for concurrent submits | Fixed with 3 - [#59](https://github.com/kmatzen/juxtapose/pull/59) |
| 9 | `app.py` (1406 lines) mixes app setup, DB, stimulus, assignment, routes, admin | **Deferred.** Trigger: the next change that has to touch two unrelated concerns in one diff, or a study that needs a second entry point. Then split by job into `db.py` / `study.py` / `admin.py` - moves only, tests unchanged. |
| 10 | Admin password compared with `==` | Fixed - [#63](https://github.com/kmatzen/juxtapose/pull/63) (`hmac.compare_digest`) |
| 11 | Participant emails in `audit.log` plaintext | Fixed - [#64](https://github.com/kmatzen/juxtapose/pull/64) (stable hash, IP kept) |
| 12 | Dev run wrote `survey.db` into the source tree | Fixed - [#65](https://github.com/kmatzen/juxtapose/pull/65) (`$TMPDIR/juxtapose-dev/`) |
| — | No Dockerfile/Procfile; `app.run` is the entrypoint | Out of scope by decision. README documents `gunicorn src.survey.app:app`; the repo ships no image build, so deployment stays the operator's. |

## Second audit, 2026-11-05

The first audit's fixes are in place; this pass looked at what a live study does under load and at the
numbers the dashboard reports.

| # | Finding | Disposition |
|---|---|---|
| 1 | The dashboard's "avg time per trial" averaged the rows `timing_flag` marks as not a judgement | Fixed - [#67](https://github.com/kmatzen/juxtapose/pull/67) (average over unflagged rows; raw values kept) |
| 2 | No upper bound on browser-reported `time_spent`: a hidden tab keeps counting, so one idle participant reported an hour | Fixed - [#68](https://github.com/kmatzen/juxtapose/pull/68) (ceiling 120s, the study owner's value; same flag, raw kept) |
| 3 | `audit.log` stamped server-local time while the database stamps UTC, so the two records of one deletion sat the UTC offset apart | Fixed - [#69](https://github.com/kmatzen/juxtapose/pull/69) (UTC from 2026-11-05; earlier lines are local, README says so) |
| 4 | Every 30s dashboard poll re-read and re-parsed every answer in the study | Fixed - [#71](https://github.com/kmatzen/juxtapose/pull/71) (aggregate cached on answer count + newest timestamp) |
| 5 | Rate-limit counters lived in one worker's memory while gunicorn runs several, so the caps were a multiple of the documented ones | Fixed - [#70](https://github.com/kmatzen/juxtapose/pull/70) (`RATELIMIT_STORAGE_URI`, redis in production, boot gate) |
| 6 | The stale-session gate hung off Flask's `TESTING` flag, so any suite setting it stopped exercising a security behaviour | Fixed - [#72](https://github.com/kmatzen/juxtapose/pull/72) (named opt-out, production refuses it). **Report correction:** the gate did have coverage - two tests flipped `TESTING` off; the defect was the entanglement, not a coverage hole. |
| 7 | `TrialStore` kept its own `OrderedDict` cache and evicted it by hand from request threads | Fixed - [#73](https://github.com/kmatzen/juxtapose/pull/73) (`lru_cache`). Stated as it was found: a latent trap, not a live bug. |
| 8 | Referral codes left no trace of which code admitted which session, so a leak could not be traced | Fixed - [#74](https://github.com/kmatzen/juxtapose/pull/74) (`REFERRAL_ACCEPTED`, code hashed as emails are, tied to the session) |
| 9 | `SHOW_PROMPT` / `ENABLE_PROMPT_QUESTION` env overrides mirrored values the study config already states, and could contradict it | Fixed - [#75](https://github.com/kmatzen/juxtapose/pull/75) (config decides; `ENABLE_PROMPT_QUESTION` was read by nothing and went with its input) |
| 10 | `audit.log` is appended to inside the request, on the data volume | **Recorded, not coded** - [#76](https://github.com/kmatzen/juxtapose/pull/76) and the *Known limit* section above: trigger and fix shape, no thread before a measured cost |

### Deferred from the second audit

Four items were left out of the numbered findings because each is a decision, not a defect at today's
size. Recorded so they are not rediscovered as surprises:

| Item | Disposition |
|---|---|
| Admin login does not rotate the session id when it elevates | Deferred. Flask's signed cookie makes fixation hard to exploit; revisit if the session ever carries more than `admin_authenticated`. |
| `FOREIGN KEY` constraints are declared and `PRAGMA foreign_keys` is never enabled | Deferred. Safe while every delete is explicit and inside one transaction. Enabling it needs a pass for pre-existing orphans first. |
| The participant count is recomputed on every dashboard poll | Deferred. `COUNT(DISTINCT ...)` over the join is cheap next to what #71 removed; it belongs in the same cache when it matters. |
| A dev `survey.db` from before #65 can sit in an existing checkout | Operator action: delete it. New dev runs write to `$TMPDIR/juxtapose-dev/` (#65). |

### Measured along the way, not fixed by this goal

- `tests/test_concurrent_submit.py::test_parallel_submits_all_land` was flaky: **4 failures in 20 runs
  at `edd0307` with no change from this goal, 1 in 20 with #73's cache, 0 in isolation.** It is the
  16-thread contended-submit test from #59 and it wants a deterministic barrier, not a longer sleep.
  **Fixed by the third audit** (its finding 4): the test now opens one `threading.Barrier` across every
  submit and runs against the app's real WAL and `busy_timeout`. The old test patched
  `sqlite3.connect(timeout=0)`, which disabled the very mechanism under test - that is why it was the
  flaky one. 20 runs, 0 failures.
- `tests/README.md` advertised `test_data_logic.py::test_get_completed_pair_ids_with_prompt_question_disabled`,
  which does not exist in `tests/`. The stale reference went with #75; the DISTINCT-completeness
  behaviour it described has no test named for it.

## Third audit, 2026-11-06

The third full-repo pass (senior-engineer review: correctness, security, scale, tests, speed, lean),
run against the state the first two audits left. It found 19 defects; all 19 are fixed in one PR,
[#78](https://github.com/kmatzen/juxtapose/pull/78), each by a test that fails without the fix
(or, for a deletion, a grep showing no reference left), and every repro case was re-measured on the
final SHA. The theme: what the app *stores* was audited against what it *shows* - the export, the
dashboard and the retake warning each read a narrower slice than the one they describe.

| # | Finding | Disposition |
|---|---|---|
| 1 | `_flatten_result` read only `{choice, confidence}`, so every `free_text`, `likert` and `multiple_choice` answer exported as an empty column (3 stored answers produced a row of blanks) | Fixed - writes `{name}_value` / `{name}_text`, and emits `_choice` / `_confidence` / `_preferred_method` only for answers that have a choice. `tests/test_export_answer_types.py`, `test_flatten_result.py::test_every_answer_shape_reaches_the_analyst` |
| 2 | `submit_demographics` inserted a demographics row on every POST, so a retake's two POSTs joined every answer twice: 3 answers showed as 6 dashboard rows and 6 CSV rows, labelled "Showing 6 of 3" | Fixed - deletes the participant's row before the insert, `UNIQUE(participant_id)`, and a migration that dedupes to the newest row first. `tests/test_demographics_uniqueness.py` |
| 3 | The stats cache was keyed on (database, answer count, newest timestamp), so an UPDATE landing in the same second with the same count never invalidated it: a corrected preference stayed invisible until the process restarted | Fixed - a one-row `stats_version` counter bumped by INSERT/UPDATE/DELETE triggers keys the cache. `PRAGMA data_version` was measured and cannot do this here (WAL, one connection per request). `test_an_updated_answer_changes_the_statistics`; #71's idle-poll win is still asserted |
| 4 | Submit was a check-then-write with no unique key, so 4 parallel submits of one trial stored 4 rows | Fixed - `UNIQUE(participant_id, image_pair_id)` (existing duplicates deduped first) and one `INSERT … ON CONFLICT DO UPDATE`. `tests/test_submit_integrity.py`, and `test_parallel_submits_all_land` now passes 20/20 (see *Measured along the way*) |
| 5 | The submit cap was the constant `60 per hour` while a study can be 80 pairs, so the 429 landed on the trial that ends the study | Fixed - the cap is derived from the study (`pairs_per_user` + 20). `tests/test_rate_limit.py`; README's rate-limit paragraph matches |
| 6 | No body cap and no question-key check: a 2 MB `responses` blob was accepted and stored (2,044,890 bytes in one cell) | Fixed - `MAX_CONTENT_LENGTH` 64 KB (413), and 400 for response keys the study does not ask. `tests/test_submit_integrity.py` |
| 7 | The results table paged on `ORDER BY s.created_at DESC`, which is second-granularity, so ties are undefined and one arriving answer shifts the window: of 251 answers, one was shown twice and the newest appeared on no page | Fixed - orders by `s.id`, a key that cannot tie. `test_an_answer_arriving_mid_paging_never_repeats_another` |
| 8 | `trial-runner` had no in-flight guard (`demographics-form` has one), so a double click - or Enter on the last field, which bypasses the disabled button - posted the trial twice and advanced the index twice, skipping a trial | Fixed - guard with `finally`. `frontend/test/double-submit.test.ts` asserts one POST and one next-pair request |
| 9 | Submit accepted any in-study `image_pair_id`, not just the trials served to that session, so a scripted client could bank answers for trials it never saw | Fixed - 400 unless the id is in `session['user_image_pairs']`. `tests/test_stimulus_integrity.py` |
| 10 | `_validate` checked a column reference only when the key was present, and never required a question's `type`: a study that cannot serve a trial booted, and a question with no type died at import as a bare `KeyError` | Fixed - each refused by name at boot, including a real `import src.survey.app` in a subprocess that used to exit 0. `tests/test_config_setup.py`; README states the contract |
| 11 | The tutorial's single pair was loaded by the eager loader: 0.42 s and 25.6 MB **per worker process** for one row at 50k rows | Fixed - `TrialStore(…, start_id=0).first()`, eager loader deleted. Measured 0.14 s / 9.5 MB |
| 12 | The CSV writer emitted formula-leading cells, so a free-text answer starting `=`, `+`, `-` or `@` executes when opened in Excel | Fixed - `_csv_safe` prefixes a `'`. Latent at baseline, hidden by finding 1 (the text was not exported at all). `tests/test_export_answer_types.py` |
| 13 | The retake warning counted the answers of ONE participant (`LIMIT 1`, no `ORDER BY`) while the confirm it gates deletes every participant for the email: it promised "nothing to lose" over 2 finished answers, and the delete branch never ran, so retakes stacked on the old answers | Fixed - the count runs over the same subquery the `DELETE` runs over. `test_the_warning_counts_every_account_the_confirm_deletes`. The modal's copy is unchanged |
| 14 | The pair route read the session's email and that email's answered trials, then read both again to skip answered ones: 2 recomputes over 4 connections on a session's first pair request, with list membership scanned per candidate trial | Fixed - one connection and one set serve both jobs; both helpers accept a caller's connection. `test_one_pair_request_reads_the_answered_set_once` |
| 15 | `/health` returned the database path to any unauthenticated caller | Fixed - key removed; the health check still reports what an operator needs |
| 16 | The dashboard's results `SELECT` omitted `timing_flag`, which the CSV export carries, so answers the app flags as "not a judgement" were invisible on the page that reviews them | Fixed - column added, plus a Timing column in the results table. `frontend/test/admin.test.ts` |
| 17 | The tutorial banner escaped `emphasis` and pasted `step.text` straight into `innerHTML`, so a study-config string built live markup in the page | Fixed - both fields escaped. The test puts an `<img onerror>` in a step and asserts no node is built |
| 18 | Dead code and an ignored payload: the browser posted a copy of the stimulus record (`stimulus_data`, `was_randomized`) that `submit_survey` rebuilds from its own served-trial record, plus `q`, `setVisible`, `compose`, `preloadAll`, `ImagePreloader` and `StimulusView.isBlocked` | Fixed - the payload is `{image_pair_id, responses, time_spent}`, grep shows 0 references for each symbol, and `test_the_ignored_payload_keys_change_nothing` proves the stored row is identical with and without the dropped keys |
| 19 | A `/api/config` that would not load returned silently, and the runner starts from the config callback, so the page sat on an intake form that could never advance - no message, no retry | Fixed - shows the failure, retries the read once, clears the warning on success. `tests/e2e/config-load.spec.js` aborts the first request in Chromium and lands on a working study |

### Deferred from the third audit

| Item | Disposition |
|---|---|
| Retake modal copy | Out of scope by decision. Finding 13 fixed what the modal *promises*; the wording is the study owner's. Trigger: the owner asks for different copy. |
| Content-Security-Policy | Out of scope by decision, as in audits 1-2. Finding 17 closed the one injection the audit found. Trigger: a study served to untrusted networks, where the header is worth its deployment cost. |
| The second-audit deferrals (admin session-id rotation, `PRAGMA foreign_keys`, participant-count caching, old dev `survey.db`) | Unchanged. The third audit found nothing that raises their priority. |

## Known limit: the audit log is appended to inside the request

Second audit, finding 10 (2026-11-05). Every audited action opens `AUDIT_LOG_FILE`, appends one JSON
line, and closes it - a synchronous write on the request path, and on a deployment whose `DATA_DIR`
is a network volume, a network round trip inside the request.

At the volume this study runs at it is invisible: the audited actions are rare (admin login, session
admission, delete-by-email), not per trial, and a line is a few hundred bytes. It becomes a real cost
when an audited action moves onto the participant's hot path, or when audited actions reach thousands
per minute. The fix at that point is a queue and one writer thread - `queue.Queue` plus a daemon
thread that flushes on shutdown, in one process, so no lines are lost and no per-worker file splitting
is needed - not a second log per worker.

Not built now, deliberately: a queue ahead of a measured latency problem buys a thread, a shutdown
path, and a new way to lose audit lines, all before the cost exists.

## What the gates now refuse at boot

See [README](../README.md#environment-variables) for the contract. The mode is declared, not
inferred: `APP_ENV` must be `production` or `dev`, and production refuses to start without a real
`SECRET_KEY` and `ADMIN_PASSWORD`, or with `DEV_MODE=true`.
