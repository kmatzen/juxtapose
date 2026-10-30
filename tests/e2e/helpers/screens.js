const fs = require('fs');
const os = require('os');
const path = require('path');
const { spawn } = require('child_process');
const { expect } = require('@playwright/test');

const PASSWORD = process.env.ADMIN_PASSWORD || 'e2e-admin-password';
// Change this and every committed screenshot moves: it fixes which image is A, and which
// pair the single-row study shows. Name it in the PR when the images are regenerated.
const SHOT_SEED = process.env.E2E_RANDOM_SEED || '20260301';

// Committed screenshots are reviewable artifacts, so they must not drift between runs. These
// servers get a one-row study (nothing to shuffle), a throwaway DATA_DIR and fixed emails.
// The runner picks which image a participant sees as A and which as B per trial, through an
// injectable random that defaults to Math.random. Frozen clock alone still shuffles the committed
// screenshots, so the shot pages get a fixed sequence: same study, same pixels, every run.
async function pinRandom(context, seed = 0x9e3779b9) {
  await context.addInitScript((start) => {
    let x = start >>> 0;
    Math.random = () => {
      x = (x + 0x6d2b79f5) >>> 0;
      let t = x;
      t = Math.imul(t ^ (t >>> 15), t | 1);
      t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  }, seed);
}

async function startShotServer(port) {
  const dataDir = fs.mkdtempSync(path.join(os.tmpdir(), 'juxtapose-shot-'));
  const child = spawn('bash', ['tests/e2e/fixture/server.sh'], {
    env: {
      ...process.env,
      PORT: String(port),
      E2E_ROWS: '1',
      E2E_RANDOM_SEED: SHOT_SEED,
      E2E_RUN_DIR: dataDir,
      ADMIN_PASSWORD: PASSWORD,
    },
    stdio: 'ignore',
  });
  const base = `http://127.0.0.1:${port}`;

  try {
    await expect.poll(async () => {
      try {
        return (await fetch(`${base}/health`)).ok;
      } catch {
        return false;
      }
    }, { timeout: 90000, message: `screenshot server on ${port} did not boot` }).toBe(true);
  } catch (error) {
    child.kill('SIGTERM');
    throw error;
  }

  return {
    base,
    stop() {
      child.kill('SIGTERM');
      fs.rmSync(dataDir, { recursive: true, force: true });
    },
  };
}

// The trial is dimmed while its images preload, and the survey form stays dimmed behind the
// retake modal. So: everything the participant can actually see must be loaded and undimmed.
async function settleForShot(page) {
  await page.waitForFunction(() => {
    const shown = (el) => !!el && el.offsetParent !== null;
    const images = Array.from(document.querySelectorAll('img'))
      .filter((i) => i.getAttribute('src') && shown(i));
    const loaded = images.every((i) => i.complete && i.naturalWidth > 0);
    const form = document.getElementById('survey-form');
    const formReady = !shown(form)
      || (form.style.opacity === '1' && form.style.pointerEvents !== 'none');
    const loading = Array.from(document.querySelectorAll('.loading-indicator')).filter(shown);
    return loaded && formReady && loading.length === 0;
  }, null, { timeout: 20000 });
}

// Layout is measured after load (setQuestionsHeight), and the shot moves with any scroll, so
// wait for the geometry fingerprint to stop changing before capturing.
async function waitForStableLayout(page) {
  await page.waitForFunction(() => new Promise((resolve, reject) => {
    const probes = ['.questions-section', '.questions-container', '#survey-section',
      '#image-a', '#image-b', '#results-table', '.table-scroll', '.admin-container'];
    const fingerprint = () => [window.scrollX, window.scrollY].concat(probes.map((sel) => {
      const el = document.querySelector(sel);
      if (!el) return `${sel}:-`;
      const r = el.getBoundingClientRect();
      return `${sel}:${Math.round(r.top)},${Math.round(r.height)},${Math.round(el.scrollTop)}`;
    })).join('|');

    let last = fingerprint();
    let stableSince = performance.now();
    const deadline = performance.now() + 20000;
    const tick = () => {
      const now = fingerprint();
      if (now !== last) {
        last = now;
        stableSince = performance.now();
      } else if (performance.now() - stableSince > 300) {
        resolve(true);
        return;
      }
      if (performance.now() > deadline) {
        reject(new Error('layout never stabilised before the screenshot'));
      }
      requestAnimationFrame(tick);
    };
    requestAnimationFrame(tick);
  }), null, { timeout: 30000 });
}

async function shot(page, name, opts = {}) {
  await settleForShot(page);
  await page.evaluate(() => {
    window.scrollTo(0, 0);
    const container = document.querySelector('.questions-container');
    if (container) container.scrollTop = 0;
  });
  await waitForStableLayout(page);
  await page.screenshot({
    path: `docs/screenshots/${name}.png`,
    fullPage: true,
    animations: 'disabled',
    ...opts,
  });
}

module.exports = { pinRandom, startShotServer, settleForShot, shot, PASSWORD, SHOT_SEED };
