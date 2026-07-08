const form = document.getElementById('metar-form');
const input = document.getElementById('station-input');
const result = document.getElementById('result');
const submitBtn = form.querySelector('button');

function escapeHtml(str) {
  const div = document.createElement('div');
  div.textContent = str;
  return div.innerHTML;
}

function showError(message) {
  result.classList.remove('hidden');
  result.classList.add('error');
  result.innerHTML = `<p>${escapeHtml(message)}</p>`;
}

function showResult(data, station) {
  result.classList.remove('hidden');
  result.classList.remove('error');

  const detailsHtml = data.sentences.map((s) => `<li>${escapeHtml(s)}</li>`).join('');

  result.innerHTML = `
    <div class="station-header">
      <h2>${escapeHtml(data.fields.station || station)}</h2>
      <span class="observed">${escapeHtml(data.fields.observed || '')}</span>
    </div>
    <p class="summary">${escapeHtml(data.summary)}</p>
    <ul class="details">${detailsHtml}</ul>
    <details class="raw-metar">
      <summary>Raw METAR</summary>
      ${escapeHtml(data.raw)}
    </details>
  `;
}

form.addEventListener('submit', async (e) => {
  e.preventDefault();
  const station = input.value.trim().toUpperCase();
  if (!station) {
    showError('Please enter an airport code.');
    return;
  }

  submitBtn.disabled = true;
  submitBtn.textContent = 'Loading...';
  result.classList.add('hidden');

  try {
    const res = await fetch(`/api/metar?station=${encodeURIComponent(station)}`);
    const data = await res.json();

    if (!res.ok) {
      showError(data.error || 'Something went wrong. Please try again.');
    } else {
      showResult(data, station);
    }
  } catch (err) {
    showError('Could not reach the server. Please try again.');
  } finally {
    submitBtn.disabled = false;
    submitBtn.textContent = 'Get Weather';
  }
});
