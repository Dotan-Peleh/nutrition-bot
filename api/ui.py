"""Single-file HTML demo UI served at `/`.

Pure inline HTML + vanilla JS so it ships in the image with no static-files
mount. Calls /analyze on the same origin, no auth handling needed because
Cloud Run's proxy passes the ID token through.
"""

INDEX_HTML = """<!doctype html>
<html dir="rtl" lang="he">
<head>
<meta charset="utf-8">
<title>NutriCart</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>
  :root{--bg:#f7f7f5;--ink:#1a1a1a;--muted:#666;--border:#e2e2dc;--accent:#1f6f4a;
        --a:#1b8a4a;--b:#5fae34;--c:#d6a700;--d:#df6b14;--e:#c0282b;}
  *{box-sizing:border-box}
  body{margin:0;background:var(--bg);color:var(--ink);
       font:15px/1.4 -apple-system,BlinkMacSystemFont,"Segoe UI",Heebo,Arial,sans-serif}
  header{padding:18px 24px;border-bottom:1px solid var(--border);background:#fff}
  header h1{margin:0;font-size:22px}
  header p{margin:4px 0 0;color:var(--muted);font-size:13px}
  main{max-width:900px;margin:0 auto;padding:24px}
  .row{display:grid;grid-template-columns:1fr 1fr;gap:20px}
  @media(max-width:700px){.row{grid-template-columns:1fr}}
  textarea{width:100%;min-height:180px;padding:12px;border:1px solid var(--border);
           border-radius:8px;background:#fff;font:14px/1.5 inherit;resize:vertical}
  fieldset{border:1px solid var(--border);border-radius:8px;padding:10px 14px;background:#fff}
  legend{padding:0 6px;color:var(--muted);font-size:12px}
  label{display:inline-block;margin:4px 12px 4px 0;font-size:13px}
  button{margin-top:12px;padding:10px 18px;background:var(--accent);color:#fff;
         border:0;border-radius:8px;font:600 14px inherit;cursor:pointer}
  button:hover{background:#155a3a}
  button:disabled{opacity:.5;cursor:wait}
  .results{margin-top:28px}
  .item{background:#fff;border:1px solid var(--border);border-radius:10px;
        padding:14px 16px;margin-bottom:12px}
  .head{display:flex;align-items:center;gap:10px}
  .grade{display:inline-block;min-width:32px;text-align:center;
         padding:4px 8px;border-radius:6px;color:#fff;font-weight:700}
  .grade.A{background:var(--a)} .grade.B{background:var(--b)}
  .grade.C{background:var(--c)} .grade.D{background:var(--d)}
  .grade.E{background:var(--e)}
  .name{font-weight:600}
  .raw{color:var(--muted);font-size:13px}
  .meta{color:var(--muted);font-size:12px;margin-top:4px}
  .alts{margin-top:10px;padding-top:10px;border-top:1px dashed var(--border)}
  .alt{display:flex;justify-content:space-between;gap:12px;
       padding:6px 0;font-size:13px}
  .alt .name{font-weight:500}
  .alt .delta{color:var(--a);font-weight:600;white-space:nowrap}
  .alt .why{color:var(--muted);font-size:12px;flex-basis:100%}
  .cart{background:#fff;border:1px solid var(--border);border-radius:10px;
        padding:14px 16px;margin-top:18px}
  .cart h2{margin:0 0 8px;font-size:15px}
  .grade-pills{display:flex;gap:6px;flex-wrap:wrap;margin-top:6px}
  .err{color:var(--e);margin-top:10px;font-size:13px}
  .nomatch{color:var(--muted);font-style:italic}
</style>
</head>
<body>
<header>
  <h1>NutriCart · ניתוח רשימת קניות</h1>
  <p>הדבק רשימת מוצרים בעברית (אחד בכל שורה) ולחץ "נתח" — תקבל ציון תזונתי וחלופות בריאות יותר.</p>
</header>
<main>
  <div class="row">
    <div>
      <textarea id="items" placeholder="קוטג׳ 5%&#10;לחם&#10;במבה&#10;יוגורט&#10;קולה זירו"></textarea>
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
const gradeOf = it => it && it.score ? it.score.nutri_score_grade : null;
const scoreOf = it => it && it.score ? it.score.final_score : null;

function render(data) {
  const out = document.getElementById('results');
  out.innerHTML = '';
  for (const it of data.items) {
    const g = gradeOf(it), s = scoreOf(it);
    const matched = it.matched_name_he;
    const card = document.createElement('div');
    card.className = 'item';
    if (!matched) {
      card.innerHTML = `<div class="head"><span class="raw">${it.raw}</span>
                        <span class="nomatch">לא נמצאה התאמה</span></div>`;
    } else {
      let alts = '';
      if (it.alternatives && it.alternatives.length) {
        alts = '<div class="alts">';
        for (const a of it.alternatives) {
          alts += `<div class="alt">
            <span class="name">${a.name_he}</span>
            <span class="delta">${a.score} (+${a.score_delta})</span>
            <span class="why">${a.explanation}</span>
          </div>`;
        }
        alts += '</div>';
      }
      card.innerHTML = `
        <div class="head">
          <span class="grade ${g}">${g}</span>
          <div>
            <div class="name">${matched}</div>
            <div class="raw">${it.raw} · ציון ${s}</div>
          </div>
        </div>${alts}`;
    }
    out.appendChild(card);
  }
  const cart = data.cart;
  const cartEl = document.createElement('div');
  cartEl.className = 'cart';
  const pills = Object.entries(cart.grade_distribution || {})
    .map(([g,n]) => `<span class="grade ${g}">${g}×${n}</span>`).join('');
  cartEl.innerHTML = `<h2>סיכום עגלה</h2>
    <div>ציון כולל: <b>${cart.total_score}</b></div>
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
