"""
Personal Bookmarks & Web Clipper Hub
------------------------------------
Single-file FastAPI + SQLite app.

Install:   pip install fastapi uvicorn jinja2
Run:       uvicorn main:app --reload
Open:      http://127.0.0.1:8000
"""

import sqlite3
from contextlib import asynccontextmanager, contextmanager
from datetime import datetime, timezone
from typing import Optional
from urllib.parse import urlparse

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from jinja2 import Environment
from pydantic import BaseModel, Field

DB_PATH = "bookmarks.db"
CATEGORIES = ["Reading", "Tech", "Recipes", "Tools"]


# --------------------------------------------------------------------------- #
# Database
# --------------------------------------------------------------------------- #
@contextmanager
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    with get_db() as db:
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS bookmarks (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                title         TEXT    NOT NULL,
                url           TEXT    NOT NULL,
                category      TEXT    NOT NULL DEFAULT 'Reading',
                tags          TEXT    NOT NULL DEFAULT '',
                notes         TEXT    NOT NULL DEFAULT '',
                is_read_later INTEGER NOT NULL DEFAULT 0,
                created_at    TEXT    NOT NULL
            )
            """
        )
        db.execute("CREATE INDEX IF NOT EXISTS idx_bookmarks_created ON bookmarks(created_at DESC)")


def row_to_dict(row: sqlite3.Row) -> dict:
    return {
        "id": row["id"],
        "title": row["title"],
        "url": row["url"],
        "category": row["category"],
        "tags": [t for t in row["tags"].split(",") if t],
        "notes": row["notes"],
        "is_read_later": bool(row["is_read_later"]),
        "created_at": row["created_at"],
    }


def fetch_all() -> list[dict]:
    with get_db() as db:
        rows = db.execute("SELECT * FROM bookmarks ORDER BY created_at DESC, id DESC").fetchall()
    return [row_to_dict(r) for r in rows]


# --------------------------------------------------------------------------- #
# Schemas / helpers
# --------------------------------------------------------------------------- #
class BookmarkIn(BaseModel):
    url: str = Field(..., min_length=1, max_length=2048)
    title: Optional[str] = Field(default="", max_length=300)
    category: str = Field(default="Reading", max_length=40)
    tags: str = Field(default="", max_length=300)
    notes: Optional[str] = Field(default="", max_length=4000)
    is_read_later: bool = False


def normalize_url(raw: str) -> str:
    raw = raw.strip()
    if not raw:
        raise HTTPException(status_code=422, detail="URL is required.")
    if "://" not in raw:
        raw = "https://" + raw
    parsed = urlparse(raw)
    if parsed.scheme not in ("http", "https") or not parsed.netloc or "." not in parsed.netloc:
        raise HTTPException(status_code=422, detail="Enter a valid http(s) URL, e.g. https://example.com")
    return raw


def normalize_tags(raw: str) -> str:
    seen, out = set(), []
    for t in raw.replace("#", "").split(","):
        t = " ".join(t.strip().lower().split())
        if t and t not in seen:
            seen.add(t)
            out.append(t[:30])
    return ",".join(out[:12])


def domain_of(url: str) -> str:
    host = urlparse(url).netloc.lower()
    return host[4:] if host.startswith("www.") else host


# --------------------------------------------------------------------------- #
# App
# --------------------------------------------------------------------------- #
@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield


app = FastAPI(title="Bookmarks & Web Clipper Hub", lifespan=lifespan)


@app.get("/api/bookmarks")
def list_bookmarks():
    return fetch_all()


@app.post("/api/bookmarks", status_code=201)
def create_bookmark(payload: BookmarkIn):
    url = normalize_url(payload.url)
    title = (payload.title or "").strip() or domain_of(url)
    category = payload.category.strip() or "Reading"
    tags = normalize_tags(payload.tags)
    notes = (payload.notes or "").strip()
    created_at = datetime.now(timezone.utc).isoformat(timespec="seconds")

    with get_db() as db:
        cur = db.execute(
            """INSERT INTO bookmarks (title, url, category, tags, notes, is_read_later, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (title, url, category, tags, notes, int(payload.is_read_later), created_at),
        )
        row = db.execute("SELECT * FROM bookmarks WHERE id = ?", (cur.lastrowid,)).fetchone()
    return row_to_dict(row)


@app.patch("/api/bookmarks/{bookmark_id}/read-later")
def toggle_read_later(bookmark_id: int):
    with get_db() as db:
        row = db.execute("SELECT * FROM bookmarks WHERE id = ?", (bookmark_id,)).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Bookmark not found.")
        new_state = 0 if row["is_read_later"] else 1
        db.execute("UPDATE bookmarks SET is_read_later = ? WHERE id = ?", (new_state, bookmark_id))
        row = db.execute("SELECT * FROM bookmarks WHERE id = ?", (bookmark_id,)).fetchone()
    return row_to_dict(row)


@app.delete("/api/bookmarks/{bookmark_id}")
def delete_bookmark(bookmark_id: int):
    with get_db() as db:
        cur = db.execute("DELETE FROM bookmarks WHERE id = ?", (bookmark_id,))
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="Bookmark not found.")
    return {"deleted": bookmark_id}


# --------------------------------------------------------------------------- #
# Front-end (Jinja2 string template)
# --------------------------------------------------------------------------- #
INDEX_TEMPLATE = r"""<!DOCTYPE html>
<html lang="en" class="h-full">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Shelf · Bookmarks &amp; Clips</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.1/css/all.min.css">
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Bricolage+Grotesque:opsz,wght@12..96,500;12..96,700;12..96,800&family=Instrument+Sans:wght@400;500;600&display=swap" rel="stylesheet">
  <script>
    tailwind.config = {
      theme: {
        extend: {
          fontFamily: {
            display: ['"Bricolage Grotesque"', 'ui-sans-serif', 'system-ui', 'sans-serif'],
            sans: ['"Instrument Sans"', 'ui-sans-serif', 'system-ui', 'sans-serif'],
          },
          colors: {
            ink: { 950: '#0b1120', 900: '#0f172a', 800: '#162033', 700: '#1e293b', 600: '#334155' },
            clip: { DEFAULT: '#5eead4', dim: '#2dd4bf' },
          },
        },
      },
    };
  </script>
  <style>
    html { color-scheme: dark; }
    body { background:
      radial-gradient(1200px 500px at 85% -10%, rgba(45,212,191,.07), transparent 60%),
      #0b1120; }
    :focus-visible { outline: 2px solid #5eead4; outline-offset: 2px; }
    .masonry { column-gap: 1rem; }
    .card-enter { animation: pop .22s ease-out both; }
    @keyframes pop { from { opacity: 0; transform: scale(.97); } to { opacity: 1; transform: none; } }
    @media (prefers-reduced-motion: reduce) {
      .card-enter { animation: none; }
      * { transition: none !important; }
    }
    ::-webkit-scrollbar { height: 8px; width: 8px; }
    ::-webkit-scrollbar-thumb { background: #334155; border-radius: 8px; }
  </style>
</head>
<body class="min-h-full font-sans text-slate-200 antialiased">

  <!-- Quick add header -->
  <header class="sticky top-0 z-30 border-b border-ink-700 bg-ink-950/85 backdrop-blur">
    <div class="mx-auto max-w-7xl px-4 sm:px-6 py-4">
      <div class="flex items-center justify-between gap-4 mb-4">
        <div class="flex items-center gap-3">
          <div class="h-9 w-9 rounded-xl bg-clip text-ink-950 grid place-items-center">
            <i class="fa-solid fa-bookmark"></i>
          </div>
          <div>
            <h1 class="font-display text-xl font-extrabold tracking-tight leading-none">Shelf</h1>
            <p class="text-xs text-slate-400 mt-1">Save it now, read it later.</p>
          </div>
        </div>
        <p id="stats" class="text-sm text-slate-400 hidden sm:block"></p>
      </div>

      <form id="addForm" class="grid grid-cols-12 gap-2" autocomplete="off">
        <div class="col-span-12 md:col-span-5 relative">
          <i class="fa-solid fa-link absolute left-3 top-1/2 -translate-y-1/2 text-slate-500 text-sm"></i>
          <input id="fUrl" type="text" required placeholder="Paste a URL"
                 class="w-full rounded-lg bg-ink-800 border border-ink-600 pl-9 pr-3 py-2.5 text-sm placeholder-slate-500 focus:border-clip focus:outline-none">
        </div>
        <input id="fTitle" type="text" placeholder="Title (optional)"
               class="col-span-12 sm:col-span-6 md:col-span-4 rounded-lg bg-ink-800 border border-ink-600 px-3 py-2.5 text-sm placeholder-slate-500 focus:border-clip focus:outline-none">
        <select id="fCategory" aria-label="Category"
                class="col-span-12 sm:col-span-6 md:col-span-3 rounded-lg bg-ink-800 border border-ink-600 px-3 py-2.5 text-sm focus:border-clip focus:outline-none">
          {% for c in categories %}<option value="{{ c }}">{{ c }}</option>{% endfor %}
          <option value="__new">New category…</option>
        </select>
        <input id="fNewCat" type="text" placeholder="Category name" maxlength="40"
               class="hidden col-span-12 md:col-span-3 md:col-start-10 rounded-lg bg-ink-800 border border-ink-600 px-3 py-2.5 text-sm placeholder-slate-500 focus:border-clip focus:outline-none">
        <input id="fTags" type="text" placeholder="Tags, comma separated"
               class="col-span-12 sm:col-span-6 md:col-span-4 rounded-lg bg-ink-800 border border-ink-600 px-3 py-2.5 text-sm placeholder-slate-500 focus:border-clip focus:outline-none">
        <input id="fNotes" type="text" placeholder="A note to your future self"
               class="col-span-12 sm:col-span-6 md:col-span-4 rounded-lg bg-ink-800 border border-ink-600 px-3 py-2.5 text-sm placeholder-slate-500 focus:border-clip focus:outline-none">
        <label class="col-span-6 md:col-span-2 flex items-center gap-2 text-sm text-slate-300 cursor-pointer select-none">
          <input id="fLater" type="checkbox" class="h-4 w-4 rounded border-ink-600 bg-ink-800 accent-teal-300">
          Read later
        </label>
        <button type="submit" id="addBtn"
                class="col-span-6 md:col-span-2 rounded-lg bg-clip hover:bg-clip-dim text-ink-950 font-semibold text-sm px-4 py-2.5 transition-colors">
          <i class="fa-solid fa-plus mr-1"></i> Save
        </button>
      </form>
      <p id="formError" class="hidden mt-2 text-sm text-rose-400" role="alert"></p>
    </div>
  </header>

  <main class="mx-auto max-w-7xl px-4 sm:px-6 py-6">

    <!-- Tabs + search -->
    <div class="flex flex-col md:flex-row md:items-center gap-3 md:gap-4">
      <div class="inline-flex rounded-lg bg-ink-800 border border-ink-700 p-1 self-start" role="tablist">
        <button data-tab="all" role="tab" class="tab rounded-md px-4 py-1.5 text-sm font-medium transition-colors">
          All bookmarks <span class="ml-1 text-xs opacity-70" id="countAll">0</span>
        </button>
        <button data-tab="later" role="tab" class="tab rounded-md px-4 py-1.5 text-sm font-medium transition-colors">
          <i class="fa-solid fa-star text-xs mr-1"></i>Read later <span class="ml-1 text-xs opacity-70" id="countLater">0</span>
        </button>
      </div>
      <div class="relative flex-1">
        <i class="fa-solid fa-magnifying-glass absolute left-3 top-1/2 -translate-y-1/2 text-slate-500 text-sm"></i>
        <input id="search" type="search" placeholder="Search titles, links and notes  ( press / )"
               class="w-full rounded-lg bg-ink-800 border border-ink-700 pl-9 pr-3 py-2.5 text-sm placeholder-slate-500 focus:border-clip focus:outline-none">
      </div>
    </div>

    <!-- Pill filters -->
    <div class="mt-4 space-y-2">
      <div id="catPills" class="flex gap-2 overflow-x-auto pb-1" aria-label="Filter by category"></div>
      <div id="tagPills" class="flex gap-2 overflow-x-auto pb-1" aria-label="Filter by tag"></div>
    </div>

    <!-- Grid -->
    <section id="grid" class="masonry columns-1 sm:columns-2 lg:columns-3 2xl:columns-4 mt-5" aria-live="polite"></section>

    <div id="empty" class="hidden text-center py-20">
      <div class="mx-auto h-14 w-14 rounded-2xl bg-ink-800 border border-ink-700 grid place-items-center text-slate-500 text-xl">
        <i class="fa-regular fa-folder-open"></i>
      </div>
      <h2 id="emptyTitle" class="font-display text-lg font-bold mt-4"></h2>
      <p id="emptyText" class="text-sm text-slate-400 mt-1"></p>
    </div>
  </main>

  <!-- Toast -->
  <div id="toast" class="fixed bottom-5 left-1/2 -translate-x-1/2 z-50 hidden rounded-lg bg-ink-700 border border-ink-600 px-4 py-2.5 text-sm shadow-xl"></div>

  <script id="initial-data" type="application/json">{{ bookmarks | tojson }}</script>
  <script>
  (function () {
    const state = {
      items: JSON.parse(document.getElementById('initial-data').textContent),
      tab: 'all',
      q: '',
      cat: null,
      tag: null,
    };

    const $ = (id) => document.getElementById(id);
    const grid = $('grid');

    const CAT_STYLES = {
      Reading: 'bg-sky-400/15 text-sky-300 ring-sky-400/30',
      Tech: 'bg-violet-400/15 text-violet-300 ring-violet-400/30',
      Recipes: 'bg-orange-400/15 text-orange-300 ring-orange-400/30',
      Tools: 'bg-emerald-400/15 text-emerald-300 ring-emerald-400/30',
    };
    const FALLBACK_CAT = [
      'bg-pink-400/15 text-pink-300 ring-pink-400/30',
      'bg-amber-400/15 text-amber-300 ring-amber-400/30',
      'bg-cyan-400/15 text-cyan-300 ring-cyan-400/30',
      'bg-lime-400/15 text-lime-300 ring-lime-400/30',
    ];
    const TAG_STYLES = [
      'bg-rose-500/10 text-rose-300',
      'bg-amber-500/10 text-amber-300',
      'bg-lime-500/10 text-lime-300',
      'bg-teal-500/10 text-teal-300',
      'bg-sky-500/10 text-sky-300',
      'bg-indigo-500/10 text-indigo-300',
      'bg-fuchsia-500/10 text-fuchsia-300',
      'bg-pink-500/10 text-pink-300',
    ];

    function hash(s) {
      let h = 0;
      for (let i = 0; i < s.length; i++) h = (h * 31 + s.charCodeAt(i)) >>> 0;
      return h;
    }
    const catStyle = (c) => CAT_STYLES[c] || FALLBACK_CAT[hash(c) % FALLBACK_CAT.length];
    const tagStyle = (t) => TAG_STYLES[hash(t) % TAG_STYLES.length];

    function esc(s) {
      return String(s).replace(/[&<>"']/g, (ch) => (
        { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[ch]
      ));
    }
    function domain(url) {
      try { return new URL(url).hostname.replace(/^www\./, ''); } catch (e) { return url; }
    }
    function fmtDate(iso) {
      const d = new Date(iso);
      if (isNaN(d)) return '';
      return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' });
    }

    let toastTimer;
    function toast(msg) {
      const t = $('toast');
      t.textContent = msg;
      t.classList.remove('hidden');
      clearTimeout(toastTimer);
      toastTimer = setTimeout(() => t.classList.add('hidden'), 2400);
    }

    async function api(path, opts) {
      const res = await fetch(path, opts);
      if (!res.ok) {
        let msg = 'Something went wrong. Try again.';
        try {
          const data = await res.json();
          if (typeof data.detail === 'string') msg = data.detail;
          else if (Array.isArray(data.detail) && data.detail[0]) msg = data.detail[0].msg;
        } catch (e) { /* keep default */ }
        throw new Error(msg);
      }
      return res.json();
    }

    // ---------- Filtering ----------
    function baseItems() {
      return state.tab === 'later' ? state.items.filter((b) => b.is_read_later) : state.items;
    }

    function visibleItems() {
      const q = state.q.trim().toLowerCase();
      return baseItems().filter((b) => {
        if (state.cat && b.category !== state.cat) return false;
        if (state.tag && !b.tags.includes(state.tag)) return false;
        if (q) {
          const hay = (b.title + ' ' + b.url + ' ' + b.notes).toLowerCase();
          if (!hay.includes(q)) return false;
        }
        return true;
      });
    }

    // ---------- Rendering ----------
    function pill(label, active, attrs, extra) {
      const on = 'bg-clip text-ink-950 border-clip';
      const off = 'bg-ink-800 text-slate-300 border-ink-600 hover:border-slate-500';
      return '<button ' + attrs + ' class="shrink-0 rounded-full border px-3 py-1 text-xs font-medium transition-colors '
        + (active ? on : off) + '">' + label + (extra || '') + '</button>';
    }

    function renderPills() {
      const pool = baseItems();
      const cats = {};
      const tags = {};
      pool.forEach((b) => {
        cats[b.category] = (cats[b.category] || 0) + 1;
        b.tags.forEach((t) => { tags[t] = (tags[t] || 0) + 1; });
      });

      // keep an active filter visible even if the pool has no matches for it
      if (state.cat && !(state.cat in cats)) state.cat = null;
      if (state.tag && !(state.tag in tags)) state.tag = null;

      let html = pill('All categories', !state.cat, 'data-cat=""');
      Object.keys(cats).sort().forEach((c) => {
        html += pill(esc(c), state.cat === c, 'data-cat="' + esc(c) + '"',
          ' <span class="opacity-60">' + cats[c] + '</span>');
      });
      $('catPills').innerHTML = html;

      const tagNames = Object.keys(tags).sort((a, b) => tags[b] - tags[a] || a.localeCompare(b));
      if (tagNames.length) {
        let th = pill('<i class="fa-solid fa-hashtag text-[10px] mr-1"></i>Any tag', !state.tag, 'data-tag=""');
        tagNames.forEach((t) => {
          th += pill('#' + esc(t), state.tag === t, 'data-tag="' + esc(t) + '"');
        });
        $('tagPills').innerHTML = th;
      } else {
        $('tagPills').innerHTML = '';
      }
    }

    function cardHtml(b) {
      const dom = esc(domain(b.url));
      const tagHtml = b.tags.map((t) =>
        '<button type="button" data-tag-chip="' + esc(t) + '" class="rounded-full px-2 py-0.5 text-[11px] font-medium '
        + tagStyle(t) + ' hover:brightness-125">#' + esc(t) + '</button>').join('');
      const notes = b.notes
        ? '<p class="mt-3 text-sm text-slate-400 line-clamp-3 whitespace-pre-line">' + esc(b.notes) + '</p>' : '';
      const star = b.is_read_later
        ? 'text-amber-300 bg-amber-400/10 border-amber-400/30'
        : 'text-slate-400 border-ink-600 hover:text-amber-300 hover:border-amber-400/30';

      return ''
        + '<article class="card-enter break-inside-avoid mb-4 rounded-2xl bg-ink-800 border border-ink-700 hover:border-ink-600 p-4 transition-colors" data-id="' + b.id + '">'
        +   '<div class="flex items-center gap-2 text-xs text-slate-400">'
        +     '<img src="https://www.google.com/s2/favicons?domain=' + encodeURIComponent(domain(b.url)) + '&sz=32" alt="" width="16" height="16" class="rounded-sm" onerror="this.style.display=\'none\'">'
        +     '<span class="truncate">' + dom + '</span>'
        +     '<span class="ml-auto shrink-0 rounded-md px-2 py-0.5 text-[11px] font-medium ring-1 ring-inset ' + catStyle(b.category) + '">' + esc(b.category) + '</span>'
        +   '</div>'
        +   '<h3 class="font-display font-bold text-[17px] leading-snug mt-3 break-words">'
        +     '<a href="' + esc(b.url) + '" target="_blank" rel="noopener noreferrer" class="hover:text-clip transition-colors">' + esc(b.title) + '</a>'
        +   '</h3>'
        +   notes
        +   (tagHtml ? '<div class="mt-3 flex flex-wrap gap-1.5">' + tagHtml + '</div>' : '')
        +   '<div class="mt-4 flex items-center gap-2">'
        +     '<span class="text-xs text-slate-500 mr-auto">' + fmtDate(b.created_at) + '</span>'
        +     '<a href="' + esc(b.url) + '" target="_blank" rel="noopener noreferrer" title="Open link" aria-label="Open link" class="h-8 px-3 grid place-items-center rounded-lg border border-ink-600 text-xs text-slate-200 hover:bg-ink-700 transition-colors"><i class="fa-solid fa-arrow-up-right-from-square mr-1.5"></i>Open</a>'
        +     '<button type="button" data-action="later" title="' + (b.is_read_later ? 'Remove from read later' : 'Add to read later') + '" aria-label="Toggle read later" aria-pressed="' + b.is_read_later + '" class="h-8 w-8 grid place-items-center rounded-lg border transition-colors ' + star + '"><i class="' + (b.is_read_later ? 'fa-solid' : 'fa-regular') + ' fa-star"></i></button>'
        +     '<button type="button" data-action="delete" title="Delete" aria-label="Delete bookmark" class="h-8 w-8 grid place-items-center rounded-lg border border-ink-600 text-slate-400 hover:text-rose-400 hover:border-rose-400/30 transition-colors"><i class="fa-regular fa-trash-can"></i></button>'
        +   '</div>'
        + '</article>';
    }

    function render() {
      $('countAll').textContent = state.items.length;
      $('countLater').textContent = state.items.filter((b) => b.is_read_later).length;
      $('stats').textContent = state.items.length + (state.items.length === 1 ? ' bookmark saved' : ' bookmarks saved');

      document.querySelectorAll('.tab').forEach((btn) => {
        const active = btn.dataset.tab === state.tab;
        btn.classList.toggle('bg-clip', active);
        btn.classList.toggle('text-ink-950', active);
        btn.classList.toggle('text-slate-300', !active);
        btn.setAttribute('aria-selected', active);
      });

      renderPills();

      const list = visibleItems();
      grid.innerHTML = list.map(cardHtml).join('');

      const empty = $('empty');
      if (list.length === 0) {
        empty.classList.remove('hidden');
        if (state.items.length === 0) {
          $('emptyTitle').textContent = 'Nothing saved yet';
          $('emptyText').textContent = 'Paste a link in the bar above to save your first bookmark.';
        } else if (state.tab === 'later' && !state.q && !state.cat && !state.tag) {
          $('emptyTitle').textContent = 'Your read-later list is empty';
          $('emptyText').textContent = 'Tap the star on any card to queue it here.';
        } else {
          $('emptyTitle').textContent = 'No bookmarks match';
          $('emptyText').textContent = 'Clear the search or pick a different category or tag.';
        }
      } else {
        empty.classList.add('hidden');
      }
    }

    // ---------- Events ----------
    $('search').addEventListener('input', (e) => { state.q = e.target.value; render(); });

    document.addEventListener('keydown', (e) => {
      const tag = (document.activeElement && document.activeElement.tagName) || '';
      if (e.key === '/' && !['INPUT', 'TEXTAREA', 'SELECT'].includes(tag)) {
        e.preventDefault();
        $('search').focus();
      }
    });

    document.querySelectorAll('.tab').forEach((btn) => {
      btn.addEventListener('click', () => { state.tab = btn.dataset.tab; render(); });
    });

    $('catPills').addEventListener('click', (e) => {
      const b = e.target.closest('[data-cat]');
      if (!b) return;
      state.cat = b.dataset.cat || null;
      render();
    });
    $('tagPills').addEventListener('click', (e) => {
      const b = e.target.closest('[data-tag]');
      if (!b) return;
      state.tag = b.dataset.tag || null;
      render();
    });

    grid.addEventListener('click', async (e) => {
      const chip = e.target.closest('[data-tag-chip]');
      if (chip) {
        state.tag = state.tag === chip.dataset.tagChip ? null : chip.dataset.tagChip;
        render();
        return;
      }
      const btn = e.target.closest('[data-action]');
      if (!btn) return;
      const card = btn.closest('[data-id]');
      const id = Number(card.dataset.id);

      if (btn.dataset.action === 'later') {
        try {
          const updated = await api('/api/bookmarks/' + id + '/read-later', { method: 'PATCH' });
          const i = state.items.findIndex((b) => b.id === id);
          if (i > -1) state.items[i] = updated;
          toast(updated.is_read_later ? 'Added to read later' : 'Removed from read later');
          render();
        } catch (err) { toast(err.message); }
      }

      if (btn.dataset.action === 'delete') {
        const item = state.items.find((b) => b.id === id);
        if (!confirm('Delete "' + (item ? item.title : 'this bookmark') + '"?')) return;
        try {
          await api('/api/bookmarks/' + id, { method: 'DELETE' });
          state.items = state.items.filter((b) => b.id !== id);
          toast('Bookmark deleted');
          render();
        } catch (err) { toast(err.message); }
      }
    });

    // Category select: allow custom category
    $('fCategory').addEventListener('change', (e) => {
      const isNew = e.target.value === '__new';
      $('fNewCat').classList.toggle('hidden', !isNew);
      if (isNew) $('fNewCat').focus();
    });

    // Add form
    $('addForm').addEventListener('submit', async (e) => {
      e.preventDefault();
      const err = $('formError');
      err.classList.add('hidden');

      let category = $('fCategory').value;
      if (category === '__new') category = $('fNewCat').value.trim() || 'Reading';

      const payload = {
        url: $('fUrl').value,
        title: $('fTitle').value,
        category: category,
        tags: $('fTags').value,
        notes: $('fNotes').value,
        is_read_later: $('fLater').checked,
      };

      const btn = $('addBtn');
      btn.disabled = true;
      btn.classList.add('opacity-60');
      try {
        const created = await api('/api/bookmarks', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload),
        });
        state.items.unshift(created);
        $('addForm').reset();
        $('fNewCat').classList.add('hidden');
        toast('Saved to Shelf');
        render();
        $('fUrl').focus();
      } catch (ex) {
        err.textContent = ex.message;
        err.classList.remove('hidden');
      } finally {
        btn.disabled = false;
        btn.classList.remove('opacity-60');
      }
    });

    render();
  })();
  </script>
</body>
</html>
"""

_jinja = Environment(autoescape=True)
_index_template = _jinja.from_string(INDEX_TEMPLATE)


@app.get("/", response_class=HTMLResponse)
def index():
    html = _index_template.render(categories=CATEGORIES, bookmarks=fetch_all())
    return HTMLResponse(html)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
