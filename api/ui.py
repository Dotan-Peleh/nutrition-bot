"""Single-file HTML demo UI served at `/`.

Pure inline HTML + vanilla JS so it ships in the image with no static-files
mount. Calls /analyze and /products/search on the same origin.
"""

INDEX_HTML = """<!doctype html>
<html dir="rtl" lang="he">
<head>
<meta charset="utf-8">
<title>NutriCart</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>
  :root{
    --bg:#f7f7f5; --panel:#fff; --ink:#1a1a1a; --muted:#666;
    --border:#e2e2dc; --accent:#1f6f4a;
    --a:#1b8a4a; --b:#5fae34; --c:#d6a700; --d:#df6b14; --e:#c0282b;
    --bad-bg:#fdecec; --bad-ink:#9b1c1c;
    --good-bg:#eaf6ed; --good-ink:#155a3a;
  }
  *{box-sizing:border-box}
  body{margin:0;background:var(--bg);color:var(--ink);
       font:15px/1.4 -apple-system,BlinkMacSystemFont,"Segoe UI",Heebo,Arial,sans-serif}
  header{padding:16px 24px;border-bottom:1px solid var(--border);background:#fff}
  header h1{margin:0;font-size:22px}
  header p{margin:4px 0 0;color:var(--muted);font-size:13px}
  main{max-width:980px;margin:0 auto;padding:20px 24px 40px}

  /* Search + chips */
  .search-wrap{position:relative;margin-bottom:12px}
  .search-wrap input{width:100%;padding:11px 14px;border:1px solid var(--border);
    border-radius:8px;background:#fff;font:14px inherit}
  .search-wrap input:focus{outline:2px solid var(--accent);outline-offset:-1px}
  .suggestions{position:absolute;top:100%;right:0;left:0;background:#fff;
    border:1px solid var(--border);border-top:0;border-radius:0 0 8px 8px;
    box-shadow:0 8px 16px rgba(0,0,0,.06);max-height:300px;overflow-y:auto;
    z-index:10;display:none}
  .suggestions.open{display:block}
  .suggestion{padding:8px 14px;cursor:pointer;font-size:14px;
    border-bottom:1px solid #f0f0ec}
  .suggestion:last-child{border-bottom:0}
  .suggestion:hover, .suggestion.active{background:#f3f3ee}
  .suggestion .meta{color:var(--muted);font-size:12px}
  .suggestion.empty{color:var(--muted);font-style:italic;cursor:default}

  textarea{width:100%;min-height:120px;padding:12px;border:1px solid var(--border);
    border-radius:8px;background:#fff;font:14px/1.5 inherit;resize:vertical}

  .row{display:grid;grid-template-columns:1fr 1fr;gap:18px}
  @media(max-width:780px){.row{grid-template-columns:1fr}}
  fieldset{border:1px solid var(--border);border-radius:8px;padding:10px 14px;background:#fff}
  legend{padding:0 6px;color:var(--muted);font-size:12px}
  label{display:inline-block;margin:4px 12px 4px 0;font-size:13px}
  button{margin-top:12px;padding:10px 18px;background:var(--accent);color:#fff;
    border:0;border-radius:8px;font:600 14px inherit;cursor:pointer}
  button:hover{background:#155a3a}
  button:disabled{opacity:.5;cursor:wait}

  .results{margin-top:24px}
  .item{background:var(--panel);border:1px solid var(--border);border-radius:10px;
    padding:14px 16px;margin-bottom:14px}
  .head{display:flex;align-items:center;gap:10px;margin-bottom:8px}
  .grade{display:inline-block;min-width:30px;text-align:center;
    padding:3px 8px;border-radius:6px;color:#fff;font-weight:700;font-size:14px}
  .grade.A{background:var(--a)} .grade.B{background:var(--b)}
  .grade.C{background:var(--c)} .grade.D{background:var(--d)}
  .grade.E{background:var(--e)}
  .name{font-weight:600}
  .raw{color:var(--muted);font-size:12px}

  /* Nutrient table */
  .nutrients{display:grid;grid-template-columns:repeat(6,1fr);gap:6px;
    margin-top:8px;font-size:12px}
  .n-cell{padding:8px;border-radius:6px;background:#f7f7f5;text-align:center}
  .n-cell .label{color:var(--muted);font-size:11px;margin-bottom:2px}
  .n-cell .val{font-weight:600;font-size:14px}
  .n-cell.bad{background:var(--bad-bg);color:var(--bad-ink)}
  .n-cell.bad .label{color:var(--bad-ink);opacity:.8}
  .n-cell.better{background:var(--good-bg);color:var(--good-ink)}
  .n-cell.better .label{color:var(--good-ink);opacity:.8}
  .per100{color:var(--muted);font-size:11px;text-align:left;margin-top:6px}

  .flags{margin-top:6px;display:flex;flex-wrap:wrap;gap:6px}
  .flag{background:var(--bad-bg);color:var(--bad-ink);padding:3px 8px;
    border-radius:6px;font-size:11px;font-weight:500}

  /* Alternatives */
  .alts{margin-top:12px;padding-top:12px;border-top:1px dashed var(--border)}
  .alts h3{margin:0 0 8px;font-size:13px;color:var(--muted);font-weight:600}
  .alt{background:#fafaf6;border:1px solid var(--border);border-radius:8px;
    padding:10px 12px;margin-bottom:8px}
  .alt-head{display:flex;justify-content:space-between;align-items:center;gap:10px}
  .alt-name{font-weight:500;font-size:14px}
  .alt-delta{color:var(--good-ink);font-weight:700;font-size:13px}
  .alt-why{color:var(--good-ink);font-size:12px;margin-top:4px}

  .cart{background:var(--panel);border:1px solid var(--border);border-radius:10px;
    padding:14px 16px;margin-top:16px}
  .cart h2{margin:0 0 8px;font-size:15px}
  .grade-pills{display:flex;gap:6px;flex-wrap:wrap;margin-top:6px}
  .err{color:var(--e);margin-top:10px;font-size:13px}
  .nomatch{color:var(--muted);font-style:italic;font-size:13px}
</style>
</head>
<body>
<header>
  <h1>NutriCart · ניתוח רשימת קניות</h1>
  <p>חפש מוצר כדי לראות מה קיים, או הדבק רשימה (פריט בכל שורה) ולחץ "נתח".</p>
</header>
<main>
  <div class="search-wrap">
    <input id="search" type="text" placeholder="חפש מוצר (לדוגמה: קוטג', גבינה צהובה, לחם)..." autocomplete="off">
    <div id="suggestions" class="suggestions"></div>
  </div>

  <div class="row">
    <div>
      <textarea id="items" placeholder="קוטג׳ 5%&#10;לחם&#10;יוגורט"></textarea>
    </div>
    <div>
      <fieldset>
        <legend>פרופיל תזונתי</legend>
        <label><input type="checkbox" id="low_sodium"> דל נתרן</label>
        <label><input type="checkbox" id="diabetic"> סוכרת</label>
        <label><input type="checkbox" id="high_protein"> חלבון גבוה</label>
        <label><input type="checkbox" id="lactose_free"> ללא לקטוז</label>
        <label><input type="checkbox" id="gluten_free"> ללא גלוטן</label>
      </fieldset>
      <button id="go">נתח רשימה</button>
      <div id="err" class="err"></div>
    </div>
  </div>

  <section class="results" id="results"></section>
</main>

<script>
// ------- Autocomplete -------
let searchTimer = null;
let activeSugg = -1;
const searchEl = document.getElementById('search');
const suggBox = document.getElementById('suggestions');

function closeSugg() { suggBox.classList.remove('open'); suggBox.innerHTML=''; activeSugg=-1; }

async function doSearch(q) {
  if (!q || q.length < 2) { closeSugg(); return; }
  try {
    const r = await fetch(`/products/search?q=${encodeURIComponent(q)}&limit=8`, {method:'POST'});
    if (!r.ok) { closeSugg(); return; }
    const items = await r.json();
    suggBox.innerHTML = '';
    if (!items.length) {
      suggBox.innerHTML = '<div class="suggestion empty">אין תוצאות במאגר</div>';
    } else {
      for (const it of items) {
        const div = document.createElement('div');
        div.className = 'suggestion';
        div.innerHTML = `<div>${it.name_he}</div>
                         <div class="meta">${it.brand || ''} · התאמה ${Math.round(it.score)}%</div>`;
        div.addEventListener('mousedown', e => {
          e.preventDefault();
          addToList(it.name_he);
          searchEl.value = '';
          closeSugg();
          searchEl.focus();
        });
        suggBox.appendChild(div);
      }
    }
    suggBox.classList.add('open');
  } catch(e) { closeSugg(); }
}

searchEl.addEventListener('input', () => {
  clearTimeout(searchTimer);
  searchTimer = setTimeout(() => doSearch(searchEl.value.trim()), 200);
});
searchEl.addEventListener('blur', () => setTimeout(closeSugg, 200));
searchEl.addEventListener('keydown', e => {
  const list = suggBox.querySelectorAll('.suggestion:not(.empty)');
  if (!list.length) return;
  if (e.key === 'ArrowDown') { e.preventDefault();
    activeSugg = (activeSugg + 1) % list.length;
    list.forEach((el,i)=>el.classList.toggle('active', i===activeSugg)); }
  else if (e.key === 'ArrowUp') { e.preventDefault();
    activeSugg = (activeSugg - 1 + list.length) % list.length;
    list.forEach((el,i)=>el.classList.toggle('active', i===activeSugg)); }
  else if (e.key === 'Enter' && activeSugg >= 0) { e.preventDefault();
    list[activeSugg].dispatchEvent(new MouseEvent('mousedown')); }
});

function addToList(name) {
  const ta = document.getElementById('items');
  ta.value = (ta.value.trim() + '\\n' + name).trim() + '\\n';
}

// ------- Nutrient rendering -------
const NUTRIENT_LABELS = {
  energy_kj: ['אנרגיה', 'kJ'],
  sodium_mg: ['נתרן', 'mg'],
  sugars_g:  ['סוכר', 'g'],
  sat_fat_g: ['שומן רווי', 'g'],
  fiber_g:   ['סיבים', 'g'],
  protein_g: ['חלבון', 'g'],
};
const RED_FLAG_KEY = {sodium:'sodium_mg', sugar:'sugars_g', sat_fat:'sat_fat_g'};

function fmt(v, unit) {
  if (v == null || isNaN(v)) return '—';
  if (unit === 'kJ') return Math.round(v);
  if (v >= 100) return Math.round(v);
  if (v >= 10) return v.toFixed(1);
  return v.toFixed(2);
}

function renderNutrients(nutrients, redFlags, altNutrients) {
  if (!nutrients) return '';
  const flagged = new Set((redFlags||[]).map(f => RED_FLAG_KEY[f.nutrient]).filter(Boolean));
  let html = '<div class="nutrients">';
  for (const [key, [label, unit]] of Object.entries(NUTRIENT_LABELS)) {
    const v = nutrients[key];
    let cls = 'n-cell';
    if (flagged.has(key)) cls += ' bad';
    // If we're rendering an alternative, mark cells where alt is meaningfully better
    if (altNutrients) {
      const orig = altNutrients[key];
      if (orig != null && v != null) {
        const improvedDown = ['sodium_mg','sugars_g','sat_fat_g'].includes(key);
        const improvedUp = ['fiber_g','protein_g'].includes(key);
        if (improvedDown && orig > 0 && v < orig * 0.85) cls += ' better';
        if (improvedUp && v > orig * 1.15) cls += ' better';
      }
    }
    html += `<div class="${cls}">
       <div class="label">${label}</div>
       <div class="val">${fmt(v, unit)}<span style="font-size:10px;color:#888"> ${unit}</span></div>
     </div>`;
  }
  html += '</div>';
  if (redFlags && redFlags.length) {
    html += '<div class="flags">';
    for (const f of redFlags) {
      const lbl = {sodium:'נתרן גבוה', sugar:'סוכר גבוה', sat_fat:'שומן רווי גבוה'}[f.nutrient] || f.nutrient;
      html += `<span class="flag">⚠ ${lbl} (${fmt(f.actual)}${f.unit} > ${fmt(f.threshold)}${f.unit})</span>`;
    }
    html += '</div>';
  }
  return html + '<div class="per100">ל-100 גרם / 100 מ"ל</div>';
}

function render(data) {
  const out = document.getElementById('results');
  out.innerHTML = '';
  for (const it of data.items) {
    const card = document.createElement('div');
    card.className = 'item';
    if (!it.matched_name_he) {
      card.innerHTML = `<div class="head"><span class="raw">${it.raw}</span>
                        <span class="nomatch">לא נמצאה התאמה במאגר</span></div>`;
    } else {
      const g = it.score?.nutri_score_grade || '-';
      const s = it.score?.final_score ?? '-';
      let html = `<div class="head">
        <span class="grade ${g}">${g}</span>
        <div>
          <div class="name">${it.matched_name_he}</div>
          <div class="raw">${it.raw} · ציון ${s}/100</div>
        </div>
      </div>`;
      html += renderNutrients(it.nutrients, it.score?.red_label_flags);

      if (it.alternatives && it.alternatives.length) {
        html += '<div class="alts"><h3>חלופות בריאות יותר באותה קטגוריה:</h3>';
        for (const a of it.alternatives) {
          html += `<div class="alt">
            <div class="alt-head">
              <span class="alt-name">${a.name_he}</span>
              <span class="alt-delta">+${a.score_delta} נק׳ · ציון ${a.score}</span>
            </div>
            <div class="alt-why">✓ ${a.explanation}</div>
            ${renderNutrients(a.nutrients, null, it.nutrients)}
          </div>`;
        }
        html += '</div>';
      }
      card.innerHTML = html;
    }
    out.appendChild(card);
  }
  const cart = data.cart;
  const cartEl = document.createElement('div');
  cartEl.className = 'cart';
  const pills = Object.entries(cart.grade_distribution || {})
    .map(([g,n]) => `<span class="grade ${g}">${g}×${n}</span>`).join('');
  cartEl.innerHTML = `<h2>סיכום עגלה</h2>
    <div>ציון כולל: <b>${cart.total_score}/100</b></div>
    <div class="grade-pills">${pills}</div>`;
  out.appendChild(cartEl);
}

document.getElementById('go').addEventListener('click', async () => {
  const txt = document.getElementById('items').value.trim();
  const items = txt.split(/\\r?\\n/).map(s=>s.trim()).filter(Boolean);
  const errEl = document.getElementById('err');
  errEl.textContent = '';
  if (!items.length) { errEl.textContent = 'הזן לפחות פריט אחד.'; return; }
  const profile = {};
  for (const k of ['low_sodium','diabetic','high_protein','lactose_free','gluten_free']) {
    if (document.getElementById(k).checked) profile[k] = true;
  }
  const btn = document.getElementById('go');
  btn.disabled = true; btn.textContent = '...';
  try {
    const r = await fetch('/analyze', {
      method: 'POST',
      headers: {'content-type':'application/json'},
      body: JSON.stringify({items, profile}),
    });
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    const data = await r.json();
    render(data);
  } catch(e) {
    errEl.textContent = String(e);
  } finally {
    btn.disabled = false; btn.textContent = 'נתח רשימה';
  }
});
</script>
</body>
</html>
"""
