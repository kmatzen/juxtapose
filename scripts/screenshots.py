#!/usr/bin/env python3
"""Capture screenshots of the running app for PR visual previews.

Boots against a already-running server (BASE_URL) and writes PNGs to SHOT_DIR.
Each page is captured independently so one failure never aborts the rest --
the CI job always uploads whatever was produced.

Usage (see .github/workflows/ci.yml):
    BASE_URL=http://127.0.0.1:5000 python scripts/screenshots.py
"""
import os
from playwright.sync_api import sync_playwright

BASE = os.environ.get("BASE_URL", "http://127.0.0.1:5000")
OUT = os.environ.get("SHOT_DIR", "screenshots")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "admin123")

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


with sync_playwright() as p:
    # PW_EXECUTABLE_PATH lets you point at a preinstalled Chromium (e.g. local
    # sandboxes); unset in CI, where `playwright install` provides the browser.
    launch_kwargs = {}
    _exe = os.environ.get("PW_EXECUTABLE_PATH")
    if _exe:
        launch_kwargs["executable_path"] = _exe
    browser = p.chromium.launch(**launch_kwargs)
    context = browser.new_context(viewport={"width": 1280, "height": 900})
    page = context.new_page()

    # 1. Landing page (demographics form)
    def home():
        page.goto(BASE + "/", wait_until="networkidle", timeout=30000)
        page.wait_for_timeout(1000)
        shot(page, "01-home-demographics")
    capture("home", home)

    # 2. Survey trial view (submit demographics to advance; DEV_MODE auto-fills)
    def survey():
        page.goto(BASE + "/", wait_until="networkidle", timeout=30000)
        page.wait_for_timeout(1500)
        btn = page.query_selector('#demographics-form button[type="submit"]')
        if btn:
            btn.click()
            page.wait_for_timeout(3000)
        shot(page, "02-survey-trial")
    capture("survey", survey)

    # 3. Admin login page
    def admin_login():
        page.goto(BASE + "/admin/login", wait_until="networkidle", timeout=30000)
        page.wait_for_timeout(500)
        shot(page, "03-admin-login")
    capture("admin-login", admin_login)

    # 4. Admin dashboard (after logging in)
    def admin_dashboard():
        page.goto(BASE + "/admin/login", wait_until="networkidle", timeout=30000)
        page.fill('input[name="password"]', ADMIN_PASSWORD)
        page.click('button[type="submit"]')
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(1500)
        shot(page, "04-admin-dashboard")
    capture("admin-dashboard", admin_dashboard)

    browser.close()

print("done; screenshots in", OUT)
