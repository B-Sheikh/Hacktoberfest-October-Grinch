const form = document.getElementById('login-form');
form.onsubmit = async event => {
  event.preventDefault(); const button = form.querySelector('button'); button.disabled = true;
  const error = document.getElementById('login-error'); error.textContent = '';
  try {
    const response = await fetch('/api/auth/login', { method: 'POST', body: new FormData(form) });
    const value = await response.json();
    if (!response.ok) throw Error(typeof value.detail === 'string' ? value.detail : 'Check your username and password.');
    location.assign('/office');
  } catch (failure) { error.textContent = failure.message; button.disabled = false; }
};
