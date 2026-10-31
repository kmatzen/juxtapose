# Audit findings and their disposition

Source: four full-repo senior-engineer audits (correctness, security, scale, tests, speed, lean) of the
survey app, 2026-11, 2026-11-05, 2026-11-06 and 2026-10-30. The first three each landed as PRs merged with CI
green on the merge SHA. The fourth landed as one commit on branch `wt/ponytail-audit-4`, not merged: merging
is the owner's decision. The first audit's findings are the table below; the second audit's are in
[Second audit, 2026-11-05](#second-audit-2026-11-05), the third's in
[Third audit, 2026-11-06](#third-audit-2026-11-06) and the fourth's in
[Fourth audit, 2026-10-30](#fourth-audit-2026-10-30).

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

## Fourth audit, 2026-10-30

The fourth full-repo pass, run against the state the third left. It found 16 defects (5 must fix, 5 should
fix, 6 nice to have) and all 16 are fixed in one commit on `wt/ponytail-audit-4`, each by a test that fails
without the fix - a grep showing no reference left, for a deletion - with the red run recorded before the
green one, and every proof re-measured on the final SHA. The theme: the participant-facing edges that no
test walked. CSRF was off in every fixture, so a form that cannot be submitted shipped; the proxy that
production requires made every rate limit and every audit line speak about the wrong machine; and a
returning participant was served a study that the app's own completion rule kept ending early.

| # | Finding | Disposition |
|---|---|---|
| 1 | The "Start Over" form posted with no CSRF token, so with the gate on - which is production - `/reset_session_confirm` answered 400 and the button under the warning could never work | Fixed - the form carries a hidden `csrf_token()`. `tests/test_csrf_forms.py` reads the token off the page as the browser does, posts, and asserts 302 with the participant's rows gone; a tokenless post is 400 and deletes nothing |
| 2 | Submit locked forever on a trial with no visible radio group: `isFormComplete([])` is false and the change handler listened only to radios, so typing the answer that trial asks for never re-ran the gate | Fixed - an empty set of visible radio groups is complete (`question-flow.ts`), and the free-text answers are what the trial requires. `frontend/test/components/no-radio-trial.test.ts` (all-free-text trial, and radios hidden by `depends_on`); the shipped config's gate stays shut until a radio is picked |
| 3 | One non-numeric `confidence` value made `/api/admin/stats` raise TypeError on every poll, permanently, and `admin.ts` swallows poll errors, so the stat cards froze silently mid-study | Fixed - the average takes numbers only, junk excluded. `tests/test_stats_answer_shape.py` posts the string through the real submit route, then asserts 200 and a correct `avg_confidence`. Red pre-fix: 500 `unsupported operand type(s) for +: 'int' and 'str'` |
| 4 | Behind the TLS proxy production requires, every client was `127.0.0.1`: the 10/hour admin-login cap was one global budget any visitor can exhaust, and every `audit.log` line named the proxy instead of the person who logged in | Fixed - `ProxyFix(app.wsgi_app, x_for=1)`, one trusted hop, named in the README. `tests/test_proxy_ip.py`: a second client behind the proxy keeps its own login budget, the audit line reads `203.0.113.9`, and a direct headerless request is unchanged |
| 5 | A required `free_text` question rendered no `required` attribute, always posted `{text: ''}`, and passed the server's completeness rule, so the study collected blanks and reported the trial finished | Fixed - the textarea carries `required` when the config says so, and completeness needs non-blank text. `tests/test_required_free_text.py`: blank is not complete, filled is, and the attribute is in the rendered page |
| 6 | Both app fixtures set `WTF_CSRF_ENABLED False`, so all 223 backend tests ran with the gate off - which is how finding 1 shipped | Fixed - `csrf_app` / `csrf_client` keep the gate ON and read the token off the rendered page, the referral and reset forms post through it, and a tokenless post is refused (that refusal is the proof the fixture is real, not decoration). The duplicated boot in `referral_client` is gone; the bulk suite keeps its off-switch |
| 7 | A returning participant was told 30 pairs and cut off at 20/30: the assignment budget ignored what their email had already answered, while the completion gate counted by email, so the study ended with a third of the served assignment unserved | Fixed - the assignment is `pairs_per_user` minus what that email answered. `tests/test_resume_budget.py` (40 trials in the file, because with exactly 30 the `min()` masks the bug): told 20, ends at 20/20, thank-you page, stored rows exactly at the cap |
| 8 | The dashboard's 30s poll reloaded offset 0 and threw away every page "Load more" had appended, so an analyst reading row 350 lost it on the next poll | Fixed - a refresh asks for the window the analyst has open. `frontend/test/admin.test.ts` boots the page through its `[data-admin-app]` marker, pages to 400 rows, advances the clock 30s, and asserts 400 are still there |
| 9 | CSV export - the one action that copies every participant email out of the database - was the only admin action with no audit line | Fixed - `EXPORT_CSV` with the row count taken from the same FROM clause the stream uses. `tests/test_export_stream.py::test_exporting_the_csv_leaves_an_audit_line` |
| 10 | A quoted `scale: "5"` was the one config value the boot gate did not refuse, and it 500s every page render at template time; on an `ab_preference` question `scale` also moved dev autofill's confidence range while the template renders a fixed 1-5, so dev runs silently left confidence empty | Fixed - a scale that is not a whole number ≥ 2 is refused at boot naming the question, and dev autofill uses 5. `tests/test_scale_gate.py` runs a real `import src.survey.app` in a subprocess: pre-fix it exits 0 on a config that 500s every page. `dev-autofill.test.ts` finds the confidence radio with `scale: 50` |
| 11 | `empty()` in `lib/dom.ts` had no reference anywhere in the repo | Fixed - deleted. Grep over `src`, `frontend/src`, `frontend/test`, `tests`, `docs`, config: 0 references (the one `empty(` hit is the unrelated Python test name `test_get_completed_pair_ids_empty`) |
| 12 | `renderDeviceInfo` and its `fmt` helper were a second implementation of the device list, used by their own test only; `mountDevicePanel` is what the page runs | Fixed - both deleted with the `byId` import they needed. The coverage moved by deletion, not by loss: `device-panel.test.ts` already asserts all five spans (`user-browser`/`-os`/`-screen`/`-pixel-ratio`/`-color`) and the page that has no list |
| 13 | `visibleQuestionNames` was exported for the test suite only; the components ask `visibleSections()` | Fixed - deleted; `study-state.test.ts` filters with the exported `isSectionVisible` it is actually testing |
| 14 | `_ROW_PARSES` was instrumentation inside production code, read by one test, and its `global` increment is not thread-safe | Fixed - deleted. `test_trial_store.py` counts parses by wrapping `_parse_trial_line` and measures boot on `_read_trial_row.cache_info()`, so the boot-cost, cache-hit and unknown-id assertions still bite |
| 15 | `tests/README.md` stated 113 backend / 329 total where the suite is 254 backend / 195 frontend / 25 browser | Fixed - the counts are measured from the final SHA's run output, and the browser tier is named as Chromium-run |
| 16 | `admin_export` held the whole study in memory twice and derived its columns from the rows it happened to find, so a partially answered study exported a different shape than a finished one | Fixed - streamed one row at a time with the header built from the config (`_export_fieldnames`). `tests/fixtures/export_snapshot.csv` pins the bytes (every column, every row, every `_csv_safe` prefix) against the pre-fix output, and the streaming test asserts the header leaves before a row is read |

### Notes from the fourth audit

- Consequence of finding 16, stated plainly: the columns are now the study's, not the answers'. Every
  configured question and demographics field is a column whether or not anyone answered it, and a key the
  browser posts that the config does not declare - the retake modal's `confirm_retake` - is no longer a
  column. A study's CSV keeps one shape from the first answer to the last, which is what an analyst's
  spreadsheet needs.
- Finding 4's trust is unconditional by decision: exactly one TLS-terminating hop, no env knob. A
  deployment with two proxies must collapse `X-Forwarded-For` at the edge; the README says so. Trusting
  more than one hop is how a client gets to choose the address the login cap and the audit log see.
- `byId` in `lib/dom.ts` is now exported for its own test only - finding 13's pattern, in a new place. It
  is not in the 16, so it stays for the next pass.
- The browser tier's screenshots were not reproducible, on any SHA: the mobile survey shot landed on one
  of two images, and the committed `06-mobile-survey.png` was one of the two by luck (measured on the
  parent SHA as well as this one, before and after). The cause is not the study and not the app's data.
  A `fullPage` screenshot is stitched from viewport strips by scrolling the page, and the app's
  scroll-driven progressive question flow *reacts to that scrolling*: the ↑/↓ nav arrows are painted in
  their enabled/disabled state, so one page state produced two artifacts. `shot()` in
  `tests/e2e/helpers/screens.js` now parks the pointer outside the viewport (`.radio-label:hover` was
  painting on whatever scrolled beneath it) and pins what the shot depicts: a shot of the study must show
  its first question. Measured after the fix: seven committed screenshots, five consecutive full runs of
  both shot specs, one byte-identical output per file, and `01` and `03` stay distinct, so the
  overlay-hover shot still shows the hover. `05-admin-dashboard.png` is the one image that changed: the
  parked pointer no longer hovers a results-table row. `keepHover` exists because the park would
  otherwise erase the hover that shot `03` is there to document.
- `tests/README.md`'s *Test Structure* tree is still a map of a suite that no longer exists: it lists a
  `tests/frontend/` directory of `.test.js` files (the frontend tests are `frontend/test/*.ts`) and 5 of
  the 12 Playwright specs. Finding 15 corrected the counts and the one documented command that named a test
  which does not exist; the tree itself is the same rot and was left for the next pass on the docs.

## Fifth audit, 2026-10-30

The fifth full-repo pass, run against the state the fourth left on the unmerged `wt/ponytail-audit-4`.
It found 19 defects (6 must fix, 6 should fix, 7 nice to have). Fourteen were already fixed by the
fourth audit and were re-measured here rather than trusted: every repro script was re-run against
that tree and 12 of the 13 breakages it claims are gone. Four were still live and are fixed in
`6a2fb11` on `wt/ponytail-audit-5-close`, each by a test that fails without it (finding 15 excepted: it
is a stated-equivalent rewrite, so its test pins results and export agreeing and cannot be red by
design); one was fixed
half-way by the fourth audit and finished here; two are recorded as known limits. The theme: the
fourth audit fixed what each route computes and left what a *returning session* is told against
what it is served, and what a *refresh* does to a trial already on screen.

| # | Finding | Disposition |
|---|---|---|
| 1 | `submit_survey` accepted a non-numeric `confidence` (`{"choice":"A","confidence":"very"}`), and `admin_stats` summed it: the dashboard poll returned 500 on every call from then on, permanently, for that study | Fixed by the fourth audit, re-measured here - two stats polls return 200 with that row stored. `tests/test_stats_answer_shape.py` |
| 2 | `reset_session_confirm.html` posted a form with no CSRF token, so "Start Over" answered 400 in every deployment that is not dev mode - the suite could not see it because it ran with CSRF off | Fixed by the fourth audit (the template renders the token, `conftest` runs CSRF on). Covered in the browser tier by `tests/e2e/session-lifecycle.spec.js`, which is red on `main` (the page never leaves `/reset_session_confirm`) and green here |
| 3 | No `ProxyFix`: behind the TLS proxy every participant was `127.0.0.1`, so the admin login cap of 10/hour was one global budget and the audit log recorded proxy addresses | Fixed by the fourth audit - werkzeug `ProxyFix(x_for=1)`. Measured: 25 distinct `X-Forwarded-For` clients get 25 buckets and a 26th fresh client can log in. `tests/test_proxy_ip.py` |
| 4 | A returning participant was promised the study size and served less: the completion gate counted the email's answers from every session against the new session's assignment, so the client left the study early | Half fixed by the fourth audit (the assignment is now reduced - a returner is told 2, not 4); the gate at `submit_survey` counted the email-wide total, measured `completed: true` after 10 of the 20 trials it was promised. Fixed here - the gate intersects with `session['user_image_pairs']`. `test_the_completion_gate_counts_this_session_not_the_email`, and `tests/e2e/session-lifecycle.spec.js` (promises 4 on `main`, 2 here) |
| 5 | A study of free-text questions only could never be submitted: `isFormComplete` over zero radios is false, and the submit handler was wired to radio change | Fixed by the fourth audit. `frontend/test/components/no-radio-trial.test.ts` |
| 6 | A required `free_text` question submitted blank: `{"comments": {"text": ""}}` was stored and the server reported the trial complete | Fixed by the fourth audit - the textarea is `required` and the server refuses the blank. Measured: `completed: false`, `completed_pairs: 0` |
| 7 | `tests/conftest.py` set `WTF_CSRF_ENABLED: False` for the whole backend suite, so no test could see a missing token (finding 2 shipped green for this reason) | Fixed by the fourth audit - CSRF is parameterised and on by default |
| 8 | `get_image_pair` drew the A/B position afresh on every request and overwrote the session record, so a mid-trial refresh - what the app's own banner tells a participant to do - swapped the tiles under them, and the answer's attribution followed the newest cookie write | Fixed here - one draw per (session, trial), attributed from that record. Measured 52 of 100 repeat requests changed position over 20 sessions before, 0 after. `tests/test_pair_flip.py` |
| 9 | The CSV export wrote no audit line, so the download of every answer in a study was unlogged | Fixed by the fourth audit - `EXPORT_CSV` on the streaming export. `tests/test_export_stream.py` |
| 10 | The dashboard's 30-second poll reloaded from offset 0 and replaced the row list, so rows the operator added with "Load more" disappeared on the next tick | Fixed by the fourth audit. `frontend/test/admin.test.ts` |
| 11 | A quoted likert `scale: "5"` booted and then 500s every page (`range(1, "5" + 1)` in `index.html`) | Fixed by the fourth audit - the scale is validated at boot and refused by name. `tests/test_scale_gate.py` |
| 12 | `delete_by_email` read `request.json.get('email')`, so a JSON body that is not an object raised `AttributeError` and answered 500 where every other bad input gets a clean 400 | Fixed here - `get_json(silent=True)` plus a dict check. Measured: `[]`, `"delete me"`, `{"email": 5}` and `7` each answer 400 with exactly one `DELETE_FAILED` audit line (a form-encoded body now answers 400 there too, where Flask answered 415). `tests/test_audit_five_cleanups.py` |
| 13 | Dead code: `lib/dom.ts:empty`, `lib/device-info.ts` (`fmt`, `renderDeviceInfo`) duplicating `device-panel.ts`, `study-state.ts:visibleQuestionNames`, `app.py:_ROW_PARSES` | Deleted by the fourth audit (grep shows 0 references for each). `INPUTS_BY_NAME` and `config.get_inputs_by_name` joined them here, when finding 14 made the lookup unused |
| 14 | `_parse_trial_line` resolved a data column through the input **name** first, so an input named after another input's column answered for it and applied the wrong `optional` flag: a blank `mask_url` was stored as `''` instead of `None` | Fixed here - the column-keyed lookup only. Proven red by booting a study whose input names collide with another input's column (`tests/test_trial_input_lookup.py`): the lookup lived in a module-import constant, so a monkeypatched `CONFIG` cannot reach it and the test has to boot. |
| 15 | The admin results and export queries wrote `LEFT JOIN survey_responses … WHERE s.id IS NOT NULL`, which is an inner join stated twice, and `_STATS_CACHE` keyed on the module constant `DATABASE` | Fixed here - `JOIN survey_responses`, `cache_key = version`. The demographics join stays `LEFT`, see the notes. `test_results_and_export_agree_on_who_answered` |
| 16 | `tests/README.md` counted 113 backend tests; the suite had 223 | Updated by the fourth audit and refreshed here to what the gates print on this branch: 263 backend, 195 frontend (20 files), 26 Chromium participant specs |
| 17 | The export built the whole study in memory twice (a list of rows, then the CSV string) | Streaming on the fourth audit. `tests/test_export_stream.py`, `tests/fixtures/export_snapshot.csv` |
| 18 | The session cookie grows with the assignment and the per-trial flip record: measured 374 B at 30 pairs, 803 B at 200, 2,004 B at 300 | Known limit, recorded below. Not code at this study's size |
| 19 | `src/survey/app.py` is 1,610 lines and holds six jobs | Unchanged deferral, as in audits 1-4 (first audit, finding 9). This pass added 12 net lines to it, so the trigger is unchanged |

### Deferred from the fifth audit

| Item | Disposition |
|---|---|
| Finding 18, the session cookie | Recorded, not built. The ~4 KB cookie cap is crossed near 1,000 trials per participant, far above the shipped study's 30, and every measured study config so far is under 100. The fix at that point is a table keyed by session id holding the assignment and the flip record, with only the key in the cookie - not a bigger cookie. Trigger: a study whose `pairs_per_user` passes ~500, or a proxy with a smaller header cap. |
| Finding 19, the size of `app.py` | Out of scope by decision, as in audits 1-4. Trigger: the next feature that needs its own blueprint, which is the split that pays for itself. |

### Notes from the fifth audit

- Finding 14's red is reproducible on a tree that predates the fix, which a monkeypatch-based test
  could not be. From the branch tip: `git worktree add --detach /tmp/jx-red 21df595`, copy
  `tests/test_trial_input_lookup.py` into it, run
  `APP_ENV=dev python -m pytest tests/test_trial_input_lookup.py -q --no-cov` there —
  `1 failed: the blank mask_url cell parsed to ''`. The same file on `3ccad70` passes.
- The phone screenshot spec was timing out, on this machine, on about one full-tier run in three, and
  the fourth audit had measured it green five times on its own SHA. Measured on `62b7d50`: run on
  their own the shot specs pass 9/9; run in the tier, `mobile-screenshots.spec.js` failed **3 of 3**
  full passes and `screenshots.spec.js` once, every time at `shot()`'s 20 s "shots depict the first
  question" predicate, with a fully rendered page in the failure artifact.
  The cause is the predicate's own mechanism: `shot()` scrolls the page to the top, and the app's
  scroll-driven progressive flow, having already advanced on a short viewport, does not walk back —
  the first question is a state the shot waits for and, once advanced, can never get. `shot()` now
  **drives** it: `goToFirstQuestion` presses `#prev-question-btn` until it is disabled (bounded at 8,
  a hard failure past that) before the layout and first-question waits. Measured after: three full
  tier passes with `CI=1 npx playwright test --repeat-each=2` are green (52 passed + 1 skipped, 53,
  52 + 1 skipped, no failures and no flakes; the skip is the auth setup when a storage state is
  already cached), the phone shot spec takes 1.9-2.2 s, and one clean pass on the landed SHA reports
  27 passed in 2.1 m. The same specs previously sat the full 20 s and failed. `settleForShot` also now reports which of its three conditions a timeout was waiting
  on, because the page looks rendered when it fails and the message is the only evidence. The shot
  specs are not reordered: running them first was tried and changed nothing, since the flow advances
  inside the spec itself.
- `E2E_PORT` must not be `5071`. `tests/e2e/screenshots.spec.js` starts its own fixture server on
  5071 with `stdio: 'ignore'`, so if the suite's webServer already holds that port the shot server
  fails to bind silently and the spec drives the shared fixture server, which serves a random trial;
  the identity tiles of that trial are empty, so the determinism assertion reports
  `locator('img.identity-image').first() - element(s) not found`. Measured: the spec is green on
  `main` and on this branch at the default port (5055) and red only under that collision. It cost
  this audit one false finding against the fourth.
- Making the demographics join inner (finding 15) is **not** equivalent: it drops answers whose
  participant has no demographics row, and `tests/test_admin_pagination.py` and
  `tests/test_timing_flag.py` failed on it. Only the `survey_responses` join was the same query
  stated twice.
- The fourth audit's own suite hid the second half of finding 4: `answer()` in
  `tests/test_resume_budget.py` asserted the POST succeeded and ignored the `completed` flag the
  client navigates on, so the test was green while the participant was cut off. The new test asserts
  the flag, and the browser spec asserts the promise the participant reads.
- A browser spec that asserts a returning-session budget needs a fixture whose rows outnumber the
  per-user cap: with `E2E_ROWS == pairs_per_user` the `min()` in the assignment hides the budget, and
  the spec is green before the fix. `session-lifecycle.spec.js` starts its own server (6 rows, cap 4)
  for that reason, the same trap `tests/test_resume_budget.py` documents at the backend tier.
- `byId` in `lib/dom.ts` is still exported for its own test only - unchanged from the fourth audit.

## Sixth audit, 2026-10-30

The sixth full-repo pass, run against the state the fifth left (`8c91b7d`, the tip of
`wt/ponytail-audit-5-close`). It reported 19 findings; 15 were open and are cured here, one was
already gone and is retracted, and three joined the standing deferrals. Every cure is a commit pair:
a test that fails on the finding first, then the change that makes it pass. Measured on the final SHA
of `wt/ponytail-audit-6-fixes`: pytest 312, vitest 212, the Chromium tier 27, 0 failures; every
repro script in `/tmp/jx-audit` re-run against this tree. The theme: the fifth audit fixed what each
route computes for a *session* and left what a session that **loses something** is left with - a
config that renders nothing, an image that never arrives, a browser that gets closed mid-study, a
participant with no email.

| # | Finding | Disposition |
|---|---|---|
| 1 | A fresh, unauthenticated session could delete another participant's answers: `submit_demographics` with a retake count deleted every row for an address the session had never proven it owned | Fixed - the delete requires the session's own email (`RETAKE_DELETE_REFUSED`). Measured: attacker's POST 403, victim's rows `(3, 1)` before and after, one audit line. `tests/test_retake_ownership.py` |
| 2 | `/api/*` answered a session that had never passed the referral gate, so the gate guarded the page and not the data | Fixed - one `_require_referral` on the API. Measured: `GET /` 302 to `/referral`, and `submit_demographics`, `get_image_pair` and `submit_survey` each 403. `tests/test_referral_gate.py` |
| 3 | Progress and completion were keyed on the **email**, so a study whose intake has no email field could never finish, and two people at one address each saw the other's progress | Fixed - progress, completion and the owed-trial list key on the session's `participant_id`; email stays the key only for person-level questions (retake count, the `pairs_per_user` cap, delete-by-email). Measured: a no-email study finishes, the thank-you page renders, an answered trial 404s. `tests/test_progress_by_participant.py` |
| 3c | A `multiple_choice` question with no options, or a demographics `select`/`radio`/`checkbox` with none, booted and rendered nothing to answer: the study could never be completed | Fixed with finding 3 - the config refuses both at boot, naming the question. Measured: boot raises `Question 'notes' is a multiple_choice with no options`. `tests/test_question_options_gate.py` |
| 4 | Admin login compared the password with `==` on a `str` against bytes, so a correct non-ASCII password failed and the comparison was not constant-time | Fixed - `compare_digest` on bytes. Measured: login with a correct non-ASCII password 302s authenticated. `tests/test_admin_password_compare.py` |
| 5 | A tile whose request stalls fires neither `load` nor `error`: the view that blocks the form on `true` never reached `false`, so the participant sat on a "Loading" spinner with the form greyed out for the rest of the session - and when a pair did fail, its answers stayed submittable | Fixed - the component that blocks the form owns the deadline (15 s) that unblocks it, and `stimulus.failed()` joins `blocksSubmit` with a message that says to refresh, so an answer to a pair nobody saw cannot enter the study data. `frontend/test/components/stimulus-failure-gate.test.ts` |
| 6 | A `depends_on` follow-up counted as unanswered when the trial's own input column was blank, so a trial with no mask could never be submitted | Fixed - one rule, `_question_shown`, mirroring `isSectionVisible`, in the server-side completeness path: a follow-up is exempt only where its stored stimulus input is blank. Measured: a maskless trial submits, `mask_adherence` stored, `completed` honest. `tests/test_visibility_rule.py` |
| 7 | `submit_survey` accepted answers the page cannot produce: `confidence: 501` was stored and averaged, and the dashboard reported `avg_confidence 501.0` | Fixed - choice, confidence, likert scale and multiple-choice value are validated against the config. Measured on the original repro: 501 rejected, `avg_confidence 5.0`. `tests/test_answer_shapes.py` |
| 8 | Referral codes were guessable at the speed of the network: the gate had no rate limit and compared codes with whitespace and case intact | Fixed - `REFERRAL_CODES` normalised at boot, the referral POST capped per address. Measured: the 19th attempt from one address is the first 429. `tests/test_rate_limit.py` |
| 9 | The dashboard could not answer "how many people started, and how many finished": the audit measured 14 of 30 completed and 5 dropped out of a study by reading the raw rows in SQL | Fixed - `/api/admin/participants` groups by participant, and the dashboard's default view is that roster. Measured: the endpoint reproduces the 14-of-30 and 5-dropout counts of the hand-written SQL. `tests/test_admin_participants.py`, `frontend/test/admin-participants.test.ts` |
| 10 | The layout is measured from the viewport and from rendered question heights at pair load and never again: rotate a phone and the tiles keep the height computed for the orientation the participant left | Fixed - a `resize` listener re-runs `layout()`, removed on dispose. Measured red/green by the tile heights a viewport change produces. `frontend/test/components/question-flow.test.ts` |
| 11 | The stacked identity sheet was cut one **square** per segment, so a 512x768 sheet of three panels was cut across the panels | Fixed - `stackedSliceBands` tiles `image.height` across the segments. Measured: 200x800 unchanged (4x200), 512x768 cuts at 384, 200x550 bands tile to exactly 550. `frontend/test/identity-masks.test.ts` |
| 12 | The e2e fixture writer wrote a study config and announced the run dir as success while the app refused to boot on it, so a broken fixture surfaced as 27 opaque browser failures | Fixed at the repo's only config writer (the app has no admin config-write path): `make_run.py` loads what it wrote through `src.survey.config.load_config` and exits 1 naming the key. `tests/test_e2e_fixture_writer.py` |
| 13 | The admin results query spelled out the export's column list a second time, so the table and the CSV could drift apart silently | Fixed - `_ADMIN_RESULTS_SELECT = 'SELECT' + _EXPORT_SELECT + _EXPORT_FROM`, the literal deleted, and an agreement test pins the two column sets. `tests/test_admin_query_agreement.py` |
| 14 | The docs a newcomer follows were fiction: `tests/README.md`'s tree named 23 paths, **20 of which do not exist** (a `frontend/` directory of `.test.js` suites deleted two audits ago); its counts (474/263/195/27) and README's (223/192/24) were stale; the env contract omitted `SURVEY_CONFIG` and `IMAGE_PAIRS_FILE`, the two variables a study cannot boot without; and README said "When `DATA_DIR` is set, the app enables production mode", handing the security mode back to `DATA_DIR` after audit 1 moved it to `APP_ENV` - two rows above the row that says so correctly | Fixed - counts replaced by the commands that print them, the tree rewritten against `ls tests/`, the three env rows added, the mode sentence fixed. `tests/test_docs_contract.py` fails on any of the four regressions. `docs/frontend-architecture.md` already stated the model rule, so it was left alone |
| 15 | `_csv_safe` prefixed `= + - @` and let a leading **tab** or **carriage return** through - the same Excel/Sheets trigger set, with a participant as the cell's author | Fixed. Measured: `=`/`+`/`-`/`@` were guarded, `\t`/`\r` were not; all six now reach the cell prefixed. `tests/test_export_csv_injection.py` |
| 16 | A loop planted a `csrfToken` cookie on every response | **Retracted** - measured zero hits for `csrfToken` across `src/`, `templates/` and `tests/`; it is gone and nothing plants a CSRF cookie |
| 17 | Dead code shipped: `lib/dom.ts:byId` and its `escapeId` helper (used only by that file's own test), `StimulusView`'s `onTrial` prop (called on every load, answered with `() => {}` at the only mount), and `generate_csrf` imported into `app.py` unused | Deleted, suite green (vitest 210, pytest 312 at that commit). The fourth audit's note "`byId` is still exported for its own test only" is closed |
| 18 | `PERMANENT_SESSION_LIFETIME` is configured at import and read by nothing: Flask writes an expiry only for a session marked permanent, so the session cookie died with the browser and took the owed trials with it - the resume the index page promises was a within-one-tab promise | Fixed - `session.permanent = True` at both participant session mints. Measured: the cookie now carries `Expires`, and the test pins it to the configured 2 hours. `tests/test_session_lifetime.py` |
| 19 | `showOverlay` painted only tiles already `complete`, so hovering a reference while the pair downloaded highlighted one tile and left the other bare, with nothing to re-run the paint | Fixed - the overlay arrives with the tile, and only while that hover is the live one: leaving first paints nothing. `frontend/test/components/conditioning-tiles.test.ts` |

### Deferred from the sixth audit

The four standing deferrals are unchanged and re-confirmed here, not re-litigated: the size of
`app.py` (now 1,704 lines; +94 from this audit, same trigger - the next feature that needs its own
blueprint), the session-cookie table (fifth audit, finding 18), admin session-id rotation (first
audit), and `PRAGMA foreign_keys` (second audit).

### Notes from the sixth audit

- Finding 12 was **scoped down with the user's agreement**. The finding reads "an admin config write
  reports success when the write failed"; the app has no admin config-write path at all, so there is
  no such report to fix. The repo's only writer of study configs is the browser-tier fixture, which
  had exactly the claimed behaviour: announce success, let the app refuse at boot.
- Finding 9's number is the audit's own: the 14-of-30 completion and 5-dropout figures were measured
  with hand-written SQL against a study with 30 participants, and the endpoint test asserts the API
  reproduces them, so the dashboard cannot silently disagree with the query the audit used.
- Two browser specs needed repair because the app is now stricter than they were.
  `admin-dashboard.spec.js` carried its XSS payload in an `ab_preference` `choice`, which finding 7
  makes a 400 - it posts it as a free-text answer now, and the fixture study gained the optional
  free-text question that lets a participant author a cell. `tutorial.spec.js` looped over the
  walkthrough with `i < 12`, which was a step count in disguise: the study now has 13 steps, the loop
  ran out before the banner did, and the bound is a runaway guard (24) with the fixture's config
  owning the real count.
- `check_demographics` reporting `completed_pairs: 0` in one repro script is that script's partial
  demographics POST, not a regression: re-measured with a complete intake on the shipped config,
  progress advances 1, 2, 3, the third submit reports `completed: true`, the fourth pair request 404s,
  and `/` serves the thank-you page.

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
