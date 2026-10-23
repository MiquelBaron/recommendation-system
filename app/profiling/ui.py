from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse

from app.profiling.stages import RequestProfile
from app.profiling.store import clear_profiles, get_profile, list_profiles

router = APIRouter(tags=["profiling"])


def _profile_to_dict(profile: RequestProfile) -> dict[str, Any]:
    return {
        "request_id": profile.request_id,
        "method": profile.method,
        "path": profile.path,
        "query": profile.query,
        "status_code": profile.status_code,
        "started_at": profile.started_at,
        "total_ms": round(profile.total_ms, 3),
        "cprofile_enabled": profile.cprofile_enabled,
        "has_cprofile": bool(profile.cprofile_text),
        "stages": [
            {"name": s.name, "duration_ms": round(s.duration_ms, 3)}
            for s in profile.stages
        ],
        "cprofile_text": profile.cprofile_text,
    }


@router.get("/profiling", response_class=HTMLResponse)
def profiling_ui() -> HTMLResponse:
    return HTMLResponse(content=_UI_HTML)


@router.get("/profiling/api/requests")
def profiling_list(limit: int = 50) -> JSONResponse:
    items = [_profile_to_dict(p) for p in list_profiles(limit=limit)]
    # Keep list payload light: drop bulky cProfile text.
    for item in items:
        item.pop("cprofile_text", None)
    return JSONResponse(items)


@router.get("/profiling/api/requests/{request_id}")
def profiling_detail(request_id: str) -> JSONResponse:
    profile = get_profile(request_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="profile not found")
    return JSONResponse(_profile_to_dict(profile))


@router.delete("/profiling/api/requests")
def profiling_clear() -> dict[str, str]:
    clear_profiles()
    return {"status": "cleared"}


_UI_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Request profiling</title>
  <style>
    :root {
      --bg: #0f1419;
      --panel: #1a2332;
      --border: #2d3a4d;
      --text: #e7ecf3;
      --muted: #8b9bb4;
      --accent: #3d9cf0;
      --ok: #3ecf8e;
      --warn: #f0b429;
      --err: #f07178;
      --bar: #3d9cf0;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      font-family: "Segoe UI", system-ui, sans-serif;
      background: var(--bg);
      color: var(--text);
      line-height: 1.45;
    }
    header {
      padding: 1rem 1.25rem;
      border-bottom: 1px solid var(--border);
      display: flex;
      flex-wrap: wrap;
      gap: 0.75rem;
      align-items: center;
      justify-content: space-between;
    }
    header h1 { margin: 0; font-size: 1.15rem; font-weight: 600; }
    header p { margin: 0; color: var(--muted); font-size: 0.85rem; }
    .actions { display: flex; gap: 0.5rem; flex-wrap: wrap; }
    button, .btn {
      background: var(--panel);
      color: var(--text);
      border: 1px solid var(--border);
      border-radius: 6px;
      padding: 0.4rem 0.75rem;
      cursor: pointer;
      font-size: 0.85rem;
      text-decoration: none;
    }
    button:hover, .btn:hover { border-color: var(--accent); }
    main {
      display: grid;
      grid-template-columns: minmax(280px, 1fr) minmax(320px, 1.4fr);
      gap: 0;
      min-height: calc(100vh - 72px);
    }
    @media (max-width: 900px) {
      main { grid-template-columns: 1fr; }
    }
    .list, .detail {
      padding: 1rem 1.25rem;
      overflow: auto;
      max-height: calc(100vh - 72px);
    }
    .list { border-right: 1px solid var(--border); }
    .row {
      display: block;
      width: 100%;
      text-align: left;
      background: transparent;
      border: 1px solid transparent;
      border-radius: 8px;
      padding: 0.65rem 0.75rem;
      margin-bottom: 0.35rem;
      color: inherit;
      cursor: pointer;
    }
    .row:hover, .row.active { background: var(--panel); border-color: var(--border); }
    .row .meta { color: var(--muted); font-size: 0.78rem; margin-top: 0.2rem; }
    .badge {
      display: inline-block;
      font-size: 0.72rem;
      padding: 0.1rem 0.4rem;
      border-radius: 4px;
      background: #243044;
      color: var(--muted);
      margin-left: 0.35rem;
    }
    .badge.cp { color: var(--warn); }
    .status-2 { color: var(--ok); }
    .status-4, .status-5 { color: var(--err); }
    .stage {
      margin: 0.55rem 0;
    }
    .stage-head {
      display: flex;
      justify-content: space-between;
      font-size: 0.85rem;
      margin-bottom: 0.2rem;
    }
    .bar-track {
      height: 8px;
      background: #243044;
      border-radius: 4px;
      overflow: hidden;
    }
    .bar-fill {
      height: 100%;
      background: var(--bar);
      border-radius: 4px;
    }
    pre {
      background: #0b1016;
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 0.85rem;
      overflow: auto;
      font-size: 0.75rem;
      max-height: 420px;
    }
    .empty { color: var(--muted); padding: 1rem 0; }
    code { color: var(--accent); font-size: 0.85em; }
    h2 { font-size: 1rem; margin: 0 0 0.75rem; }
    h3 { font-size: 0.9rem; margin: 1.25rem 0 0.5rem; color: var(--muted); font-weight: 600; }
  </style>
</head>
<body>
  <header>
    <div>
      <h1>Request profiling</h1>
      <p>
        Stages are always recorded. Add <code>?profile=1</code> or header
        <code>X-Profile: 1</code> for cProfile. Response header <code>X-Profile-Id</code>.
      </p>
    </div>
    <div class="actions">
      <button type="button" id="refresh">Refresh</button>
      <button type="button" id="clear">Clear</button>
      <a class="btn" href="/docs" target="_blank" rel="noreferrer">API docs</a>
    </div>
  </header>
  <main>
    <section class="list">
      <h2>Recent requests</h2>
      <div id="list"><p class="empty">Loading…</p></div>
    </section>
    <section class="detail">
      <h2>Detail</h2>
      <div id="detail"><p class="empty">Select a request.</p></div>
    </section>
  </main>
  <script>
    let selectedId = null;

    async function fetchList() {
      const res = await fetch("/profiling/api/requests?limit=80");
      const data = await res.json();
      const root = document.getElementById("list");
      if (!data.length) {
        root.innerHTML = '<p class="empty">No profiles yet. Hit any API endpoint.</p>';
        return;
      }
      root.innerHTML = data.map(p => {
        const active = p.request_id === selectedId ? "active" : "";
        const statusClass = "status-" + String(p.status_code || 0)[0];
        const cp = p.has_cprofile || p.cprofile_enabled
          ? '<span class="badge cp">cProfile</span>' : "";
        return `
          <button type="button" class="row ${active}" data-id="${p.request_id}">
            <div>
              <strong>${escapeHtml(p.method)} ${escapeHtml(p.path)}</strong>
              <span class="${statusClass}">${p.status_code}</span>
              ${cp}
            </div>
            <div class="meta">${p.total_ms.toFixed(2)} ms · ${p.request_id}</div>
          </button>`;
      }).join("");
      root.querySelectorAll(".row").forEach(btn => {
        btn.addEventListener("click", () => {
          selectedId = btn.dataset.id;
          fetchList();
          fetchDetail(selectedId);
        });
      });
    }

    async function fetchDetail(id) {
      const res = await fetch("/profiling/api/requests/" + encodeURIComponent(id));
      if (!res.ok) {
        document.getElementById("detail").innerHTML =
          '<p class="empty">Profile not found.</p>';
        return;
      }
      const p = await res.json();
      const maxStage = Math.max(1, ...p.stages.map(s => s.duration_ms), p.total_ms);
      const stagesHtml = p.stages.length
        ? p.stages.map(s => {
            const pct = Math.min(100, (s.duration_ms / maxStage) * 100);
            return `
              <div class="stage">
                <div class="stage-head">
                  <span>${escapeHtml(s.name)}</span>
                  <span>${s.duration_ms.toFixed(2)} ms</span>
                </div>
                <div class="bar-track"><div class="bar-fill" style="width:${pct}%"></div></div>
              </div>`;
          }).join("")
        : '<p class="empty">No named stages (handler may not be instrumented).</p>';

      const cpHtml = p.cprofile_text
        ? `<h3>cProfile (cumulative)</h3><pre>${escapeHtml(p.cprofile_text)}</pre>`
        : `<h3>cProfile</h3><p class="empty">Not captured. Retry with <code>?profile=1</code>.</p>`;

      document.getElementById("detail").innerHTML = `
        <p>
          <strong>${escapeHtml(p.method)} ${escapeHtml(p.path)}</strong>
          ${p.query ? '<code>?' + escapeHtml(p.query) + '</code>' : ''}
        </p>
        <p class="meta" style="color:var(--muted)">
          id=${escapeHtml(p.request_id)} · status=${p.status_code} · total=${p.total_ms.toFixed(2)} ms
        </p>
        <h3>Stages</h3>
        ${stagesHtml}
        ${cpHtml}
      `;
    }

    function escapeHtml(s) {
      return String(s)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;");
    }

    document.getElementById("refresh").addEventListener("click", fetchList);
    document.getElementById("clear").addEventListener("click", async () => {
      await fetch("/profiling/api/requests", { method: "DELETE" });
      selectedId = null;
      document.getElementById("detail").innerHTML =
        '<p class="empty">Select a request.</p>';
      fetchList();
    });

    fetchList();
    setInterval(fetchList, 4000);
  </script>
</body>
</html>
"""
