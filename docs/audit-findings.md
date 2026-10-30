# Audit findings and their disposition

Source: two full-repo senior-engineer audits (correctness, security, scale, tests, speed, lean) of the
survey app, 2026-11 and 2026-11-05. Each in-scope finding is one PR, merged with CI green on the
merge SHA. The first audit's findings are the table below; the second audit's are in
[Second audit, 2026-11-05](#second-audit-2026-11-05).

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

- `tests/test_concurrent_submit.py::test_parallel_submits_all_land` is flaky: **4 failures in 20 runs
  at `edd0307` with no change from this goal, 1 in 20 with #73's cache, 0 in isolation.** It is the
  16-thread contended-submit test from #59 and it wants a deterministic barrier, not a longer sleep.
- `tests/README.md` advertised `test_data_logic.py::test_get_completed_pair_ids_with_prompt_question_disabled`,
  which does not exist in `tests/`. The stale reference went with #75; the DISTINCT-completeness
  behaviour it described has no test named for it.

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
