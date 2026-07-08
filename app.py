"""Flask web app that fetches a live METAR weather report for an airport
and returns it decoded into plain English.

Routes:
    GET /            Serve the single-page front end.
    GET /api/metar   Fetch + decode the METAR for ?station=<ICAO/IATA code>.
"""
import re

import requests
from flask import Flask, Response, jsonify, render_template, request

from metar_decoder import decode_metar

app = Flask(__name__)

# Source of truth for raw METAR text; NOAA/FAA's public Aviation Weather API.
METAR_API_URL = 'https://aviationweather.gov/api/data/metar'

# ICAO codes are 4 alphanumeric characters (e.g. KHIO); IATA codes are 3
# (e.g. HIO). We accept either and let the upstream API resolve it.
STATION_RE = re.compile(r'^[A-Za-z0-9]{3,4}$')


@app.route('/')
def index() -> str:
    """Serve the single-page front end (search form + result panel)."""
    return render_template('index.html')


@app.route('/api/metar')
def api_metar() -> tuple[Response, int] | Response:
    """Look up and decode the current METAR for a station.

    Query string:
        station: 3-4 character airport code, e.g. "KHIO" or "HIO".

    Returns:
        JSON body with the decoded METAR fields/sentences/summary on
        success, or {"error": "..."} with a 4xx/5xx status on failure.
    """
    station = request.args.get('station', '').strip().upper()

    if not station:
        return jsonify({'error': 'Please enter an airport code.'}), 400
    if not STATION_RE.match(station):
        return jsonify({'error': 'Airport codes should be 3-4 letters/numbers, e.g. KHIO or HIO.'}), 400

    try:
        # format=raw returns the plain METAR text rather than JSON/XML,
        # which is what our decoder expects.
        resp = requests.get(METAR_API_URL, params={'ids': station, 'format': 'raw'}, timeout=10)
        resp.raise_for_status()
    except requests.RequestException:
        return jsonify({'error': 'Could not reach the aviation weather service. Please try again.'}), 502

    raw = resp.text.strip()
    if not raw:
        # The API returns 200 with an empty body for stations with no
        # current report (unknown code, or one that doesn't publish METARs).
        return jsonify({'error': f'No current METAR found for "{station}". Check the airport code and try again.'}), 404

    try:
        decoded = decode_metar(raw)
    except ValueError:
        return jsonify({'error': f'No current METAR found for "{station}". Check the airport code and try again.'}), 404

    return jsonify(decoded)


if __name__ == '__main__':
    # debug=True enables the interactive debugger/auto-reload for local
    # development. Never run with debug=True in a public deployment; use
    # a production WSGI server (gunicorn/waitress) instead.
    app.run(debug=True)
