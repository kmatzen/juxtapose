# Audit findings and their disposition

Source: a full-repo senior-engineer audit (correctness, security, scale, tests, speed, lean) of the
survey app, 2026-11. Each in-scope finding is one PR, merged with CI green on the merge SHA.

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
