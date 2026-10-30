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

# Seed only on request. The committed screenshots need one stable presentation (the app flips which
# image is A and shuffles the pairs a session sees, so an unseeded process captures a coin flip);
# the behavioural suite is left unseeded on purpose, because that shuffle is counterbalancing
# position bias and freezing it would take it out of test coverage.
seed = os.environ.get('E2E_RANDOM_SEED')
if seed is not None:
    random.seed(int(seed))


@app.route('/e2e-img/<path:name>')
def e2e_image(name):
    return send_from_directory(IMAGES, name)


if __name__ == '__main__':
    app.run(host='127.0.0.1', port=int(os.environ.get('PORT', 5055)))
