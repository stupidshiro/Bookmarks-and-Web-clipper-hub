# Shelf: Personal Bookmarks & Web Clipper Hub

A single-file bookmark manager built with **FastAPI** and **SQLite**. Paste a link, tag it, and find it again later with instant search and filters, all in a dark slate dashboard that runs locally with one command.

## Features

- **Quick add bar:** save a URL with an optional title, category, tags, and a note. Leave the title blank and the domain is used instead.
- **Read Later queue:** star any card, then switch to the Read Later tab to see only those.
- **Live search:** filters titles, URLs, and notes as you type. Press `/` to jump to the search box.
- **Category and tag pills:** one-click filtering with no page reloads.
- **Masonry card grid:** each card shows the favicon and domain, clickable title, category badge, colored tag pills, notes preview, and date saved.
- **Custom categories:** four defaults (Reading, Tech, Recipes, Tools), plus any new category you type in.
- **Zero build step:** Tailwind CSS and Font Awesome load from a CDN, and data is stored in a local SQLite file.

## Tech stack

| Layer    | Tool                                          |
|----------|-----------------------------------------------|
| Backend  | FastAPI, Uvicorn                              |
| Database | SQLite (`sqlite3` from the standard library)  |
| Template | Jinja2 (string template inside `main.py`)     |
| Frontend | Tailwind CSS (CDN), Font Awesome (CDN), vanilla JS |

## Getting started

### Prerequisites

- Python 3.9 or newer

### Install and run

```bash
git clone https://github.com/stupidshiro/Bookmarks-and-Web-Clipper-Hub.git
cd Bookmarks-and-Web-Clipper-Hub

# optional but recommended
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

pip install fastapi uvicorn jinja2
uvicorn main:app --reload
```

Open <http://127.0.0.1:8000> in your browser. The database file `bookmarks.db` is created automatically on first launch.

> The page loads Tailwind, Font Awesome, Google Fonts, and site favicons from the internet, so you need to be online for the full look.

## API

FastAPI also provides interactive docs at <http://127.0.0.1:8000/docs>.

| Method   | Endpoint                              | Description                         |
|----------|---------------------------------------|-------------------------------------|
| `GET`    | `/api/bookmarks`                      | List all bookmarks, newest first    |
| `POST`   | `/api/bookmarks`                      | Create a bookmark                   |
| `PATCH`  | `/api/bookmarks/{id}/read-later`      | Toggle the Read Later flag          |
| `DELETE` | `/api/bookmarks/{id}`                 | Delete a bookmark                   |

### Example

```bash
curl -X POST http://127.0.0.1:8000/api/bookmarks \
  -H "Content-Type: application/json" \
  -d '{
        "url": "https://fastapi.tiangolo.com",
        "title": "FastAPI docs",
        "category": "Tech",
        "tags": "python, api",
        "notes": "Check the dependency injection section.",
        "is_read_later": true
      }'
```

### Database schema

```sql
CREATE TABLE bookmarks (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    title         TEXT    NOT NULL,
    url           TEXT    NOT NULL,
    category      TEXT    NOT NULL DEFAULT 'Reading',
    tags          TEXT    NOT NULL DEFAULT '',   -- comma-separated
    notes         TEXT    NOT NULL DEFAULT '',
    is_read_later INTEGER NOT NULL DEFAULT 0,    -- 0 or 1
    created_at    TEXT    NOT NULL               -- ISO 8601, UTC
);
```

## Project structure

```
Bookmarks and Web clipper hub/
├── main.py          # backend, database, and frontend in one file
├── README.md
└── bookmarks.db     # created on first run (add to .gitignore)
```

## Customizing

- **Default categories:** edit the `CATEGORIES` list near the top of `main.py`.
- **Database location:** change `DB_PATH` in `main.py`.
- **Colors and fonts:** adjust the `tailwind.config` block and the `<style>` section inside `INDEX_TEMPLATE`.

## Suggested `.gitignore`

```
bookmarks.db
__pycache__/
venv/
```

## Ideas for later

- Edit an existing bookmark
- Import and export (JSON or browser bookmark HTML)
- Automatic title fetching from the page
- Browser bookmarklet for one-click clipping

## License

Released under the MIT License. Feel free to use, modify, and share.

---

Made by [stupidshiro](https://github.com/stupidshiro)
