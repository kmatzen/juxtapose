#!/usr/bin/env python3
"""Capture screenshots of the running app for PR visual previews.

Boots against an already-running server (BASE_URL) and writes PNGs to SHOT_DIR.
Each page is captured independently so one failure never aborts the rest --
the CI job always uploads whatever was produced. Participant-facing pages are
captured at both desktop and mobile widths; the admin pages at desktop only.

Usage (see .github/workflows/ci.yml):
    BASE_URL=http://127.0.0.1:5000 python scripts/screenshots.py
"""
import os
from playwright.sync_api import sync_playwright

BASE = os.environ.get("BASE_URL", "http://127.0.0.1:5000")
OUT = os.environ.get("SHOT_DIR", "screenshots")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "admin123")

DESKTOP = {"width": 1280, "height": 900}
MOBILE = {"width": 390, "height": 844}  # iPhone-ish portrait

os.makedirs(OUT, exist_ok=True)


def shot(page, name):
    path = os.path.join(OUT, name + ".png")
    page.screenshot(path=path, full_page=True)
    print("saved", path)


def capture(label, fn):
    """Run one capture step, logging (not raising) on failure."""
    try:
        fn()
    except Exception as e:  # noqa: BLE001 - best-effort, keep going
        print(f"[warn] {label} failed: {e}")


def home(page, suffix):
    page.goto(BASE + "/", wait_until="networkidle", timeout=30000)
    page.wait_for_timeout(1000)
    shot(page, f"01-home-demographics-{suffix}")


def survey(page, suffix):
    page.goto(BASE + "/", wait_until="networkidle", timeout=30000)
    page.wait_for_timeout(1500)
    btn = page.query_selector('#demographics-form button[type="submit"]')
    if btn:
        btn.click()
        page.wait_for_timeout(3000)
    shot(page, f"02-survey-trial-{suffix}")


def admin_login(page):
    page.goto(BASE + "/admin/login", wait_until="networkidle", timeout=30000)
    page.wait_for_timeout(500)
    shot(page, "03-admin-login-desktop")


def admin_dashboard(page):
    page.goto(BASE + "/admin/login", wait_until="networkidle", timeout=30000)
    page.fill('input[name="password"]', ADMIN_PASSWORD)
    page.click('button[type="submit"]')
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(1500)
    shot(page, "04-admin-dashboard-desktop")


with sync_playwright() as p:
    # PW_EXECUTABLE_PATH lets you point at a preinstalled Chromium (e.g. local
    # sandboxes); unset in CI, where `playwright install` provides the browser.
    launch_kwargs = {}
    _exe = os.environ.get("PW_EXECUTABLE_PATH")
    if _exe:
        launch_kwargs["executable_path"] = _exe
    browser = p.chromium.launch(**launch_kwargs)

    # Participant-facing pages at both widths (responsiveness matters here).
    for suffix, viewport in (("desktop", DESKTOP), ("mobile", MOBILE)):
        context = browser.new_context(viewport=viewport)
        page = context.new_page()
        capture(f"home-{suffix}", lambda: home(page, suffix))
        capture(f"survey-{suffix}", lambda: survey(page, suffix))
        context.close()

    # Admin pages at desktop width only.
    context = browser.new_context(viewport=DESKTOP)
    page = context.new_page()
    capture("admin-login", lambda: admin_login(page))
    capture("admin-dashboard", lambda: admin_dashboard(page))
    context.close()

    browser.close()

print("done; screenshots in", OUT)
