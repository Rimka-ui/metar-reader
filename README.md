# METAR Reader

A small Flask web app that turns cryptic aviation weather reports into
plain English. Type in an airport code — get back something like:

> Clear skies, 72°F, wind 5 mph from the south.

METAR ([Meteorological Aerodrome Report](https://en.wikipedia.org/wiki/METAR))
is the standardized format pilots and air traffic control use for current
weather conditions at an airport. It's accurate and information-dense, but
not exactly readable at a glance:

```
KHIO 072353Z 33010KT 10SM CLR 29/09 A2999 RMK AO2 SLP154 T02890094
```

This app fetches the latest METAR for any airport from the
[NOAA Aviation Weather Center](https://aviationweather.gov/) and decodes it
into a short summary plus a breakdown of wind, visibility, sky conditions,
temperature, and pressure.

## Features

- Look up any airport with a published METAR by its ICAO (4-letter, e.g.
  `KHIO`) or IATA (3-letter, e.g. `HIO`) code.
- Plain-English summary line, e.g. *"Mostly cloudy, 64°F, wind 17 mph from
  the SSE, gusting 29 mph."*
- Detail breakdown covering wind (direction/speed/gusts), visibility,
  weather phenomena (rain, fog, thunderstorms, etc.), sky cover/ceiling,
  temperature and dew point (°F and °C), and altimeter setting.
- Raw METAR text included (collapsed) for anyone who wants to double-check
  the source data.
- Friendly error messages for invalid codes, unknown stations, or upstream
  API issues.

## How it works

- **Backend:** [Flask](https://flask.palletsprojects.com/) app
  ([app.py](app.py)) exposes `GET /api/metar?station=<code>`, which fetches
  the raw METAR text from the Aviation Weather Center's public API and
  decodes it.
- **Decoder:** [metar_decoder.py](metar_decoder.py) parses the raw METAR
  string with no external dependencies, converting each field (wind,
  visibility, sky cover, temperature, etc.) into plain English.
- **Frontend:** a single page ([templates/index.html](templates/index.html))
  with vanilla JS ([static/script.js](static/script.js)) that calls the API
  and renders the result without a page reload.

## Requirements

- Python 3.10+
- Internet access (to reach `aviationweather.gov`)

## Installation

1. **Clone the repository**

   ```bash
   git clone <your-repo-url>
   cd My_app
   ```

2. **Create and activate a virtual environment** (recommended)

   ```bash
   python -m venv .venv

   # Windows
   .venv\Scripts\activate

   # macOS/Linux
   source .venv/bin/activate
   ```

3. **Install dependencies**

   ```bash
   pip install -r requirements.txt
   ```

4. **Run the app**

   ```bash
   python app.py
   ```

   The app starts in debug mode at `http://127.0.0.1:5000`.

5. Open that URL in a browser, type in an airport code (e.g. `KHIO`,
   `KJFK`, `KLAX`), and submit.

## Testing

Unit tests live in [tests/test_app.py](tests/test_app.py) and cover the
Flask routes end to end — request validation, error handling, and METAR
decoding. The upstream Aviation Weather API call is mocked with a set of
hand-picked raw METAR strings (calm wind, gusts, thunderstorms, unrestricted
visibility, sub-zero temperatures, etc.), so the tests run offline and
verify that each report is *interpreted* correctly rather than just that
the route returns 200.

1. **Install dev dependencies** (adds `pytest` on top of the app's
   requirements)

   ```bash
   pip install -r requirements-dev.txt
   ```

2. **Run the tests**

   ```bash
   pytest tests/ -v
   ```

3. **(Optional) Check coverage**

   ```bash
   pip install coverage
   coverage run -m pytest tests/
   coverage report -m --include="app.py,metar_decoder.py"
   ```

## Deploying

`app.run(debug=True)` is for local development only — it exposes an
interactive debugger and isn't hardened for public traffic. For a public
deployment, run the app behind a production WSGI server such as
[Gunicorn](https://gunicorn.org/) (Linux/macOS) or
[Waitress](https://docs.pylonsproject.org/projects/waitress/) (cross-platform),
for example:

```bash
pip install waitress
waitress-serve --listen=0.0.0.0:8000 app:app
```

## Data source

Weather data is fetched live from the
[NOAA Aviation Weather Center Data API](https://aviationweather.gov/data/api/).
This project is not affiliated with NOAA or the FAA.

## Contributors

- [Rimka-ui](https://github.com/Rimka-ui)

## License

No license has been chosen for this project yet, so all rights are
reserved by default — others may view the code but have no legal right
to reuse or redistribute it. Add a `LICENSE` file if you'd like to
change that.
