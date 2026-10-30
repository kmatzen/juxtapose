#!/usr/bin/env python3
"""Run the real app with one extra route that serves the fixture images same-origin.

Keeping this in the fixture means the app source stays untouched while the tiles can
still set crossOrigin='anonymous' and read mask pixels back out of a canvas.
Usage: serve.py  (env: E2E_RUN_DIR, PORT)
"""
import os
import random
from pathlib import Path

from flask import send_from_directory

from src.survey.app import app

IMAGES = Path(os.environ['E2E_RUN_DIR']) / 'images'

# The app randomises which image a participant sees as A and which as B, per response
# (random.random() < 0.5). Each run boots a fresh process, so the committed screenshots capture a
# coin flip and differ run to run. The fixture is where determinism belongs: the app's prod path
# keeps shuffling. Set E2E_RANDOM_SEED to a varying value to exercise both orientations.
random.seed(int(os.environ.get('E2E_RANDOM_SEED', '20260301')))


@app.route('/e2e-img/<path:name>')
def e2e_image(name):
    return send_from_directory(IMAGES, name)


if __name__ == '__main__':
    app.run(host='127.0.0.1', port=int(os.environ.get('PORT', 5055)))
