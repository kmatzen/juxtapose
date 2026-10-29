#!/usr/bin/env python3
"""Run the real app with one extra route that serves the fixture images same-origin.

Keeping this in the fixture means the app source stays untouched while script.js can
still set crossOrigin='anonymous' and read mask pixels back out of a canvas.
Usage: serve.py  (env: E2E_RUN_DIR, PORT)
"""
import os
from pathlib import Path

from flask import send_from_directory

from src.survey.app import app

IMAGES = Path(os.environ['E2E_RUN_DIR']) / 'images'


@app.route('/e2e-img/<path:name>')
def e2e_image(name):
    return send_from_directory(IMAGES, name)


if __name__ == '__main__':
    app.run(host='127.0.0.1', port=int(os.environ.get('PORT', 5055)))
