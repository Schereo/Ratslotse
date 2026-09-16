const root = document.documentElement;
const theme = document.getElementById('theme');
function setTheme(dark) {
  root.classList.toggle('dark', dark);
  theme.setAttribute('aria-pressed', String(dark));
  theme.textContent = dark ? 'Hellmodus' : 'Dunkelmodus';
}
try { setTheme(localStorage.getItem('pruefansicht-theme') === 'dark'); } catch { setTheme(false); }
theme.addEventListener('click', () => {
  const dark = !root.classList.contains('dark');
  setTheme(dark);
  try { localStorage.setItem('pruefansicht-theme', dark ? 'dark' : 'light'); } catch {}
});
document.getElementById('print').addEventListener('click', () => window.print());
const number = new Intl.NumberFormat('de-DE');
const percent = new Intl.NumberFormat('de-DE', { minimumFractionDigits: 1, maximumFractionDigits: 1 });
function updateRatios() {
  const basis = document.querySelector('input[name="basis"]:checked').value;
  document.getElementById('basis-hinweis').textContent = basis === 'alle'
    ? '100 Prozent entsprechen allen gültigen Stimmen der jeweiligen Wahlart.'
    : '100 Prozent entsprechen nur den Stimmen für Prange und Rohr. Die übrigen Kandidaturen sind herausgerechnet.';
  const blocks = Object.entries(window.wahlarten).map(([key, data]) => {
    const denominator = basis === 'alle' ? data.gueltige_stimmen : data.finalisten_stimmen;
    const block = document.createElement('div');
    block.className = 'method';
    block.dataset.method = key;
    block.innerHTML = `<h3>${key === 'urne' ? 'Urnenwahl' : 'Briefwahl'}</h3><p class="hint">Bezugsgröße: ${number.format(denominator)} Stimmen</p><dl></dl>`;
    const list = block.querySelector('dl');
    for (const [name, votes] of [['Ulf Prange', data.prange_stimmen], ['Jascha Rohr', data.rohr_stimmen]]) {
      const row = document.createElement('div');
      const label = document.createElement('dt');
      label.textContent = name;
      const value = document.createElement('dd');
      value.append(`${percent.format(100 * votes / denominator)} %`);
      const count = document.createElement('span');
      count.textContent = `${number.format(votes)} Stimmen`;
      value.append(count); row.append(label, value); list.append(row);
    }
    return block;
  });
  document.getElementById('quoten').replaceChildren(...blocks);
}
document.querySelectorAll('input[name="basis"]').forEach(input => input.addEventListener('change', updateRatios));
updateRatios();
let messageTimer;
function announce(text) {
  const status = document.getElementById('status');
  status.textContent = text;
  clearTimeout(messageTimer);
  messageTimer = setTimeout(() => status.textContent = '', 3500);
}
document.querySelectorAll('[data-copy]').forEach(button => button.addEventListener('click', async () => {
  const section = document.getElementById(button.dataset.copy);
  const text = `${section.querySelector('h2').textContent}\n\n${section.querySelector('.summary-copy').innerText.trim()}`;
  try { await navigator.clipboard.writeText(text); announce('Abschnitt kopiert.'); }
  catch { announce('Kopieren ist im Browser gesperrt. Du kannst den Text direkt markieren.'); }
}));
const observer = new IntersectionObserver(entries => {
  for (const entry of entries) if (entry.isIntersecting) {
    document.querySelectorAll('nav a').forEach(link => {
      if (link.hash === `#${entry.target.id}`) link.setAttribute('aria-current', 'location');
      else link.removeAttribute('aria-current');
    });
  }
}, { rootMargin: '-15% 0px -65% 0px' });
document.querySelectorAll('main section').forEach(section => observer.observe(section));
