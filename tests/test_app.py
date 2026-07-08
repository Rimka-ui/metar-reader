"""Unit tests for app.py's Flask routes.

The upstream Aviation Weather API call (requests.get) is mocked so
these run offline and deterministically. Everything downstream of the
fetch -- station validation, decode_metar, JSON shaping -- runs for
real, so these tests verify that a given raw METAR is *interpreted*
correctly, not just that the route returns 200.
"""
from unittest.mock import Mock, patch

import pytest
import requests

from app import app


@pytest.fixture
def client():
    app.testing = True
    with app.test_client() as client:
        yield client


def mock_metar_response(raw_text):
    """Build a fake requests.Response for a successful upstream fetch."""
    resp = Mock()
    resp.text = raw_text
    resp.raise_for_status = Mock()
    return resp


# ---------------------------------------------------------------------------
# Front end
# ---------------------------------------------------------------------------

def test_index_serves_front_end(client):
    resp = client.get('/')
    assert resp.status_code == 200
    assert b'METAR Reader' in resp.data


# ---------------------------------------------------------------------------
# Input validation (no network call should happen for these)
# ---------------------------------------------------------------------------

def test_missing_station_returns_400(client):
    resp = client.get('/api/metar')
    assert resp.status_code == 400
    assert 'airport code' in resp.get_json()['error']


@pytest.mark.parametrize('station', ['', '  ', 'A', 'TOOLONG', 'AB!'])
def test_invalid_station_format_returns_400(client, station):
    resp = client.get('/api/metar', query_string={'station': station})
    assert resp.status_code == 400


@patch('app.requests.get')
def test_station_is_stripped_and_uppercased_before_upstream_call(mock_get, client):
    mock_get.return_value = mock_metar_response(
        'METAR KHIO 081512Z 00000KT 10SM CLR 17/12 A3020'
    )
    client.get('/api/metar', query_string={'station': ' khio '})

    _, kwargs = mock_get.call_args
    assert kwargs['params']['ids'] == 'KHIO'


# ---------------------------------------------------------------------------
# Decoding / interpretation of mocked METAR text
# ---------------------------------------------------------------------------

@patch('app.requests.get')
def test_calm_wind_and_broken_clouds_decoded_correctly(mock_get, client):
    mock_get.return_value = mock_metar_response(
        'SPECI KHIO 081512Z 00000KT 10SM BKN024 17/12 A3020 RMK AO2 T01670122'
    )

    resp = client.get('/api/metar', query_string={'station': 'KHIO'})
    data = resp.get_json()
    fields = data['fields']

    assert resp.status_code == 200
    assert fields['wind'] == {'speed_mph': 0}
    assert fields['visibility'] == '10 statute miles'
    assert fields['sky'] == ['Mostly cloudy (broken clouds) at 2,400 ft']
    assert fields['temperature_f'] == 63
    assert fields['dewpoint_f'] == 54
    assert fields['altimeter_inhg'] == 30.2
    assert 'Calm winds.' in data['sentences']
    assert data['summary'] == (
        'Mostly cloudy (broken clouds), 63°F, calm wind.'
    )


@patch('app.requests.get')
def test_gusting_wind_decoded_with_direction_and_gust(mock_get, client):
    mock_get.return_value = mock_metar_response(
        'METAR KDEN 081553Z 27015G25KT 10SM FEW250 22/M03 A2992'
    )

    resp = client.get('/api/metar', query_string={'station': 'KDEN'})
    fields = resp.get_json()['fields']

    assert fields['wind'] == {
        'direction': 'from the W (270°)',
        'speed_mph': 17,
        'gust_mph': 29,
    }
    assert fields['temperature_f'] == 72
    assert fields['dewpoint_f'] == 27


@patch('app.requests.get')
def test_thunderstorm_and_rain_weather_phrase(mock_get, client):
    mock_get.return_value = mock_metar_response(
        'METAR KTPA 081753Z 18012KT 3SM +TSRA BKN008 OVC015 26/24 A2985'
    )

    resp = client.get('/api/metar', query_string={'station': 'KTPA'})
    fields = resp.get_json()['fields']

    assert fields['weather'] == ['Heavy thunderstorm with rain']
    assert fields['visibility'] == '3 statute miles'
    assert fields['sky'] == [
        'Mostly cloudy (broken clouds) at 800 ft',
        'Overcast at 1,500 ft',
    ]
    assert fields['wind'] == {'direction': 'from the S (180°)', 'speed_mph': 14}


@patch('app.requests.get')
def test_unrestricted_visibility_and_q_altimeter(mock_get, client):
    mock_get.return_value = mock_metar_response(
        'METAR EGLL 081750Z 24008KT 9999 FEW035 18/10 Q1015'
    )

    resp = client.get('/api/metar', query_string={'station': 'EGLL'})
    fields = resp.get_json()['fields']

    assert fields['visibility'] == '10+ km'
    assert fields['sky'] == ['A few clouds at 3,500 ft']
    assert fields['altimeter_inhg'] == 29.97
    assert fields['wind']['direction'] == 'from the WSW (240°)'


@patch('app.requests.get')
def test_negative_temperatures_and_clear_skies(mock_get, client):
    mock_get.return_value = mock_metar_response(
        'METAR PAFA 081753Z 09005KT 10SM SKC M15/M20 A2990'
    )

    resp = client.get('/api/metar', query_string={'station': 'PAFA'})
    fields = resp.get_json()['fields']

    assert fields['sky'] == ['Clear skies']
    assert fields['temperature_c'] == -15
    assert fields['temperature_f'] == 5
    assert fields['dewpoint_c'] == -20
    assert fields['dewpoint_f'] == -4


# ---------------------------------------------------------------------------
# Upstream / decoding failure paths
# ---------------------------------------------------------------------------

@patch('app.requests.get')
def test_upstream_network_error_returns_502(mock_get, client):
    mock_get.side_effect = requests.RequestException('boom')

    resp = client.get('/api/metar', query_string={'station': 'KHIO'})

    assert resp.status_code == 502
    assert 'Could not reach' in resp.get_json()['error']


@patch('app.requests.get')
def test_empty_upstream_body_returns_404(mock_get, client):
    mock_get.return_value = mock_metar_response('')

    resp = client.get('/api/metar', query_string={'station': 'ZZZZ'})

    assert resp.status_code == 404
    assert 'No current METAR found for "ZZZZ"' in resp.get_json()['error']


@patch('app.decode_metar')
@patch('app.requests.get')
def test_decode_failure_returns_404(mock_get, mock_decode, client):
    mock_get.return_value = mock_metar_response('GARBLED DATA')
    mock_decode.side_effect = ValueError('unparseable')

    resp = client.get('/api/metar', query_string={'station': 'KHIO'})

    assert resp.status_code == 404
    assert 'No current METAR found for "KHIO"' in resp.get_json()['error']
