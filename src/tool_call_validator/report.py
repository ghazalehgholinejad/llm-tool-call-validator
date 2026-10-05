"""Self-contained HTML reports. Untrusted values are always escaped as text."""
import json
from collections import Counter
from html import escape


def render_html(result: dict) -> str:
    """Render a single-call or batch validation result without network assets."""
    rows = result['results'] if 'results' in result else [dict(result, line=1)]
    accepted = sum(row['valid'] for row in rows)
    counts = Counter()
    for row in rows:
        counts.update({error['code'] for error in row['errors']})
    ranked = sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    options = ''.join('<option value="' + escape(code, quote=True) + '">'
                      + escape(code) + ' (' + str(count) + ')</option>' for code, count in ranked)
    frequency = ('<table><caption>Records by error code</caption><thead><tr><th scope="col">Error code</th>'
                 '<th scope="col">Records</th></tr></thead><tbody>' + ''.join(
                     '<tr><th scope="row"><code>' + escape(code) + '</code></th><td>' + str(count)
                     + '</td></tr>' for code, count in ranked) + '</tbody></table>') if ranked else '<p>No validation errors.</p>'
    cards = []
    for row in rows:
        status = 'accepted' if row['valid'] else 'rejected'
        title = escape(str(row.get('call', {}).get('name', 'Rejected call')))
        errors = ''.join(
            '<li><code>' + escape(error['code']) + '</code> at <code>'
            + escape(error['path'] or '(root)') + '</code><p>'
            + escape(error['message']) + '</p></li>' for error in row['errors'])
        details = ('<ul>' + errors + '</ul>') if errors else '<p>All validation checks passed.</p>'
        if row.get('errors_truncated'):
            details += '<p><strong>More errors were omitted by the error limit.</strong></p>'
        if row['valid']:
            # ASCII escapes also handle lone Unicode surrogates in parsed JSON.
            details += '<details><summary>Accepted arguments</summary><pre>' + escape(
                json.dumps(row['call']['arguments'], ensure_ascii=True, indent=2)) + '</pre></details>'
        cards.append('<article data-status="' + status + '" data-errors="'
                     + escape(json.dumps(sorted({e['code'] for e in row['errors']})), quote=True) + '"><h2>Line '
                     + escape(str(row['line'])) + ' · ' + title + '</h2><span class="badge '
                     + status + '">' + status.capitalize() + '</span>' + details + '</article>')
    return '''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; base-uri 'none'; form-action 'none'">
<title>Tool Call Validation Report</title>
<style>
:root{color-scheme:light;font-family:system-ui,sans-serif;color:#192b3b;background:#f3f6fa}
body{max-width:960px;margin:auto;padding:32px 20px}h1{font-size:clamp(1.7rem,4vw,2.6rem);margin-bottom:8px}
.subtitle{color:#506174}.stats{display:flex;flex-wrap:wrap;gap:16px;margin:24px 0}
.stat{background:white;border:1px solid #d4deea;border-radius:12px;padding:18px;flex:1;min-width:120px}
.stat strong{display:block;font-size:2rem}nav{display:flex;flex-wrap:wrap;gap:8px;align-items:center;margin:20px 0}
input,select{font:inherit;border:1px solid #8397ac;border-radius:8px;padding:9px;max-width:100%;box-sizing:border-box}
.filters{display:flex;flex-wrap:wrap;gap:12px;margin:16px 0}.filters label{display:grid;gap:6px;flex:1;min-width:180px}
table{width:100%;border-collapse:collapse;background:white;margin:20px 0}caption{text-align:left;font-weight:600;padding:10px 0}th,td{text-align:left;padding:10px;border-bottom:1px solid #d4deea;overflow-wrap:anywhere}
button{font:inherit;cursor:pointer;border:1px solid #8397ac;border-radius:8px;background:white;padding:9px 16px}
button[aria-pressed="true"]{background:#183c60;color:white}input:focus-visible,select:focus-visible,button:focus-visible,summary:focus-visible{outline:3px solid #b05d00;outline-offset:3px}
article{background:white;border:1px solid #d4deea;border-radius:12px;padding:20px;margin:16px 0}
h2{font-size:1.1rem;margin:0 0 12px;overflow-wrap:anywhere}.badge{display:inline-block;border-radius:20px;padding:4px 12px;font-weight:600}
.accepted{background:#d9f1e5;color:#135b36}.rejected{background:#fbe0df;color:#872a26}
code,pre{font-family:ui-monospace,monospace}pre{white-space:pre-wrap;background:#f3f6fa;padding:14px;border-radius:8px}
li,p,pre{overflow-wrap:anywhere}li{margin-bottom:14px}summary{cursor:pointer;padding:10px 0}
footer{color:#506174;margin-top:24px;font-size:.9rem}[hidden]{display:none!important}
@media print{nav,.filters,#reset-filters{display:none}article{break-inside:avoid}body{background:white}}
</style></head><body><header><p class="subtitle">LLM TOOL CALL VALIDATOR</p>
<h1>Validation report</h1><p class="subtitle">Inspect proposed calls before execution. No tools were executed.</p></header>
<div class="stats"><div class="stat"><strong>''' + str(len(rows)) + '''</strong>Total calls</div>
<div class="stat"><strong>''' + str(accepted) + '''</strong>Accepted</div>
<div class="stat"><strong>''' + str(len(rows)-accepted) + '''</strong>Rejected</div></div>
<section aria-label="Error frequency">''' + frequency + '''<p>Counts cover the whole report, once per record per code. Omitted errors are not counted.</p></section>
<div class="filters" hidden><label for="search">Search results<input id="search" type="search" placeholder="Tool, error, path, or argument text"></label>
<label for="error-filter">Error code<select id="error-filter"><option value="">All error codes</option>''' + options + '''</select></label></div>
<nav aria-label="Filter validation results" hidden><button type="button" data-filter="all" aria-pressed="true">All</button>
<button type="button" data-filter="accepted" aria-pressed="false">Accepted</button>
<button type="button" data-filter="rejected" aria-pressed="false">Rejected</button><button type="button" id="reset-filters">Reset filters</button></nav>
<p id="visible-count" role="status">Showing ''' + str(len(rows)) + ''' calls</p>
<p id="empty-state" hidden>No calls match these filters. Try another search or reset filters.</p>
<main>''' + ''.join(cards) + '''</main>
<footer>Schema validity does not establish authorization or safe execution. Reports can contain sensitive argument values.</footer>
<script>
const cards = [...document.querySelectorAll('article[data-status]')];
const buttons = [...document.querySelectorAll('button[data-filter]')];
const search = document.getElementById('search');
const errorFilter = document.getElementById('error-filter');
const normalize = text => text.normalize('NFKC').toLowerCase();
const index = cards.map(card => ({card, text: normalize(card.textContent), codes: JSON.parse(card.dataset.errors)}));
let status = 'all';
function update() {
  const query = normalize(search.value.trim());
  let visible = 0;
  index.forEach(({card, text, codes}) => {
    const matches = (status === 'all' || card.dataset.status === status)
      && (!errorFilter.value || codes.includes(errorFilter.value)) && text.includes(query);
    card.hidden = !matches;
    if (matches) visible++;
  });
  buttons.forEach(button => button.setAttribute('aria-pressed', String(button.dataset.filter === status)));
  document.getElementById('visible-count').textContent = `Showing ${visible} of ${cards.length} calls`;
  document.getElementById('empty-state').hidden = visible !== 0;
}
buttons.forEach(button => button.addEventListener('click', () => { status = button.dataset.filter; update(); }));
search.addEventListener('input', update);
errorFilter.addEventListener('change', update);
document.getElementById('reset-filters').addEventListener('click', () => {
  status = 'all'; search.value = ''; errorFilter.value = ''; update();
});
document.querySelector('nav').hidden = false;
document.querySelector('.filters').hidden = false;
update();
</script></body></html>
'''
