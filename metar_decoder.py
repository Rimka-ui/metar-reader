"""Decode raw METAR strings into structured data and plain-English sentences."""
import re

COMPASS = ['N', 'NNE', 'NE', 'ENE', 'E', 'ESE', 'SE', 'SSE',
           'S', 'SSW', 'SW', 'WSW', 'W', 'WNW', 'NW', 'NNW']

SKY_COVER = {
    'SKC': 'Clear skies',
    'CLR': 'Clear skies',
    'NSC': 'No significant clouds',
    'NCD': 'No clouds detected',
    'FEW': 'A few clouds',
    'SCT': 'Scattered clouds',
    'BKN': 'Mostly cloudy (broken clouds)',
    'OVC': 'Overcast',
    'VV': 'Sky obscured',
}

WX_INTENSITY = {'-': 'Light', '+': 'Heavy', 'VC': 'Nearby'}

WX_DESCRIPTOR = {
    'MI': 'shallow', 'PR': 'partial', 'BC': 'patchy', 'DR': 'low drifting',
    'BL': 'blowing', 'SH': 'showers of', 'TS': 'thunderstorm with', 'FZ': 'freezing',
}

WX_PHENOMENA = {
    'DZ': 'drizzle', 'RA': 'rain', 'SN': 'snow', 'SG': 'snow grains',
    'IC': 'ice crystals', 'PL': 'ice pellets', 'GR': 'hail', 'GS': 'small hail',
    'UP': 'unknown precipitation', 'BR': 'mist', 'FG': 'fog', 'FU': 'smoke',
    'VA': 'volcanic ash', 'DU': 'dust', 'SA': 'sand', 'HZ': 'haze', 'PY': 'spray',
    'PO': 'dust/sand whirls', 'SQ': 'squalls', 'FC': 'funnel cloud/tornado',
    'SS': 'sandstorm', 'DS': 'duststorm',
}

WX_RE = re.compile(
    r'^(?P<intensity>-|\+|VC)?'
    r'(?P<descriptor>MI|PR|BC|DR|BL|SH|TS|FZ)*'
    r'(?P<phenomena>(?:DZ|RA|SN|SG|IC|PL|GR|GS|UP|BR|FG|FU|VA|DU|SA|HZ|PY|PO|SQ|FC|SS|DS){1,4})$'
)

WIND_RE = re.compile(r'^(?P<dir>\d{3}|VRB)(?P<speed>\d{2,3})(G(?P<gust>\d{2,3}))?(?P<unit>KT|MPS|KMH)$')
WIND_VAR_RE = re.compile(r'^\d{3}V\d{3}$')
TIME_RE = re.compile(r'^(?P<day>\d{2})(?P<hour>\d{2})(?P<min>\d{2})Z$')
TEMP_RE = re.compile(r'^(?P<temp>M?\d{2})/(?P<dew>M?\d{2})?$')
ALTIM_RE = re.compile(r'^(?P<kind>A|Q)(?P<val>\d{4})$')
SKY_RE = re.compile(r'^(?P<cover>SKC|CLR|NSC|NCD|FEW|SCT|BKN|OVC|VV)(?P<height>\d{3})?(?P<type>CB|TCU)?$')
VIS_METERS_RE = re.compile(r'^\d{4}$')


def _degrees_to_compass(deg):
    ix = int((deg + 11.25) / 22.5) % 16
    return COMPASS[ix]


def _c_to_f(c):
    return round(c * 9 / 5 + 32)


def _parse_temp_token(token):
    return -int(token[1:]) if token.startswith('M') else int(token)


def decode_metar(raw):
    """Decode a raw METAR string. Returns a dict with structured fields,
    a list of human-readable detail sentences, and a one-line summary."""
    raw = raw.strip()
    if not raw:
        raise ValueError('Empty METAR')

    tokens = raw.split()
    details = {
        'station': None,
        'observed': None,
        'wind': None,
        'visibility': None,
        'weather': [],
        'sky': [],
        'temperature_f': None,
        'temperature_c': None,
        'dewpoint_f': None,
        'dewpoint_c': None,
        'altimeter_inhg': None,
    }
    sentences = []

    i = 0
    n = len(tokens)

    # Report type prefix
    if i < n and tokens[i] in ('METAR', 'SPECI'):
        i += 1

    # Station identifier
    if i < n and re.match(r'^[A-Z0-9]{4}$', tokens[i]):
        details['station'] = tokens[i]
        i += 1

    # Observation time
    if i < n:
        m = TIME_RE.match(tokens[i])
        if m:
            details['observed'] = f"day {m.group('day')} at {m.group('hour')}:{m.group('min')} UTC"
            i += 1

    # Auto / correction flags
    while i < n and tokens[i] in ('AUTO', 'COR'):
        if tokens[i] == 'AUTO':
            sentences.append('This is an automated observation.')
        i += 1

    while i < n:
        token = tokens[i]

        if token == 'RMK':
            break

        m = WIND_RE.match(token)
        if m:
            speed = int(m.group('speed'))
            gust = int(m.group('gust')) if m.group('gust') else None
            unit = m.group('unit')
            to_mph = {'KT': 1.15078, 'MPS': 2.23694, 'KMH': 0.621371}[unit]
            speed_mph = round(speed * to_mph)
            gust_mph = round(gust * to_mph) if gust else None

            if m.group('dir') == 'VRB':
                direction = 'variable direction'
            else:
                deg = int(m.group('dir'))
                direction = f'from the {_degrees_to_compass(deg)} ({deg}°)'

            if speed == 0:
                wind_text = 'Calm winds'
                details['wind'] = {'speed_mph': 0}
            else:
                wind_text = f'Wind {direction} at {speed_mph} mph'
                details['wind'] = {'direction': direction, 'speed_mph': speed_mph}
                if gust_mph:
                    wind_text += f', gusting to {gust_mph} mph'
                    details['wind']['gust_mph'] = gust_mph
            sentences.append(wind_text + '.')
            i += 1
            continue

        if WIND_VAR_RE.match(token):
            i += 1
            continue

        # Visibility in statute miles, possibly split across two tokens (e.g. "1 1/2SM")
        if i + 1 < n and re.match(r'^\d+$', token) and re.match(r'^\d/\dSM$', tokens[i + 1]):
            whole = int(token)
            frac = tokens[i + 1][:-2]
            num, den = frac.split('/')
            miles = whole + int(num) / int(den)
            details['visibility'] = f'{miles} statute miles'
            sentences.append(f'Visibility {miles} miles.')
            i += 2
            continue

        m = re.match(r'^(?P<neg>M)?(?:(?P<whole>\d+))?(?:(?P<frac>\d/\d))?SM$', token)
        if m and 'SM' in token:
            whole = int(m.group('whole')) if m.group('whole') else 0
            frac = m.group('frac')
            miles = whole + (int(frac.split('/')[0]) / int(frac.split('/')[1]) if frac else 0)
            prefix = 'less than ' if m.group('neg') else ''
            details['visibility'] = f'{prefix}{miles} statute miles'
            sentences.append(f'Visibility {prefix}{miles} miles.')
            i += 1
            continue

        if VIS_METERS_RE.match(token):
            meters = int(token)
            if meters == 9999:
                details['visibility'] = '10+ km'
                sentences.append('Visibility 10+ km (unrestricted).')
            else:
                miles = round(meters / 1609.34, 1)
                details['visibility'] = f'{meters} meters (~{miles} mi)'
                sentences.append(f'Visibility about {miles} miles.')
            i += 1
            continue

        if token.startswith('R') and '/' in token:
            i += 1
            continue

        m = WX_RE.match(token)
        if m and any(m.groupdict().values()):
            intensity = WX_INTENSITY.get(m.group('intensity'), '')
            descriptor = m.group('descriptor') or ''
            descriptor_text = WX_DESCRIPTOR.get(descriptor, '')
            phen_codes = re.findall(r'DZ|RA|SN|SG|IC|PL|GR|GS|UP|BR|FG|FU|VA|DU|SA|HZ|PY|PO|SQ|FC|SS|DS',
                                     m.group('phenomena'))
            phen_text = ' and '.join(WX_PHENOMENA.get(p, p) for p in phen_codes)
            phrase = ' '.join(filter(None, [intensity, descriptor_text, phen_text])).strip()
            phrase = phrase[0].upper() + phrase[1:] if phrase else phrase
            if phrase:
                details['weather'].append(phrase)
                sentences.append(phrase + '.')
            i += 1
            continue

        m = SKY_RE.match(token)
        if m:
            cover = m.group('cover')
            cover_text = SKY_COVER.get(cover, cover)
            if m.group('height'):
                height_ft = int(m.group('height')) * 100
                layer_text = f'{cover_text} at {height_ft:,} ft'
            else:
                layer_text = cover_text
            details['sky'].append(layer_text)
            sentences.append(layer_text + '.')
            i += 1
            continue

        m = TEMP_RE.match(token)
        if m and m.group('dew') is not None:
            temp_c = _parse_temp_token(m.group('temp'))
            dew_c = _parse_temp_token(m.group('dew'))
            details['temperature_c'] = temp_c
            details['temperature_f'] = _c_to_f(temp_c)
            details['dewpoint_c'] = dew_c
            details['dewpoint_f'] = _c_to_f(dew_c)
            sentences.append(
                f"Temperature {details['temperature_f']}°F ({temp_c}°C), "
                f"dew point {details['dewpoint_f']}°F ({dew_c}°C)."
            )
            i += 1
            continue

        m = ALTIM_RE.match(token)
        if m:
            if m.group('kind') == 'A':
                inhg = int(m.group('val')) / 100
            else:
                inhg = round(int(m.group('val')) * 0.02953, 2)
            details['altimeter_inhg'] = inhg
            sentences.append(f'Altimeter setting {inhg:.2f} inHg.')
            i += 1
            continue

        # Unrecognized token: skip
        i += 1

    if not details['sky'] and 'CAVOK' in tokens:
        sentences.append('Ceiling and visibility OK (CAVOK).')

    summary = build_summary(details)
    return {
        'raw': raw,
        'fields': details,
        'sentences': sentences,
        'summary': summary,
    }


def build_summary(details):
    parts = []

    if details['sky']:
        parts.append(details['sky'][0].split(' at ')[0])
    elif not details['weather']:
        parts.append('Clear skies')

    if details['weather']:
        parts.append(', '.join(details['weather']).lower())

    if details['temperature_f'] is not None:
        parts.append(f"{details['temperature_f']}°F")

    wind = details['wind']
    if wind:
        if wind.get('speed_mph', 0) == 0:
            parts.append('calm wind')
        else:
            gust = f", gusting {wind['gust_mph']} mph" if wind.get('gust_mph') else ''
            parts.append(f"wind {wind['speed_mph']} mph {wind['direction']}{gust}")

    return ', '.join(parts) + '.' if parts else 'No summary available.'
