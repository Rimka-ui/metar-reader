import re

import requests
from flask import Flask, jsonify, render_template, request

from metar_decoder import decode_metar

app = Flask(__name__)

METAR_API_URL = 'https://aviationweather.gov/api/data/metar'
STATION_RE = re.compile(r'^[A-Za-z0-9]{3,4}$')


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/api/metar')
def api_metar():
    station = request.args.get('station', '').strip().upper()

    if not station:
        return jsonify({'error': 'Please enter an airport code.'}), 400
    if not STATION_RE.match(station):
        return jsonify({'error': 'Airport codes should be 3-4 letters/numbers, e.g. KHIO or HIO.'}), 400

    try:
        resp = requests.get(METAR_API_URL, params={'ids': station, 'format': 'raw'}, timeout=10)
        resp.raise_for_status()
    except requests.RequestException:
        return jsonify({'error': 'Could not reach the aviation weather service. Please try again.'}), 502

    raw = resp.text.strip()
    if not raw:
        return jsonify({'error': f'No current METAR found for "{station}". Check the airport code and try again.'}), 404

    try:
        decoded = decode_metar(raw)
    except ValueError:
        return jsonify({'error': f'No current METAR found for "{station}". Check the airport code and try again.'}), 404

    return jsonify(decoded)


if __name__ == '__main__':
    app.run(debug=True)
