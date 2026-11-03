# AGENTS.md

Guidance for AI coding agents (and humans) working in this repository.

## 1. Project Overview

**FreshMart** is a complete, production-ready grocery-store e-commerce web application.

- **Backend**: a single-file Python **Flask** application (`app.py`, ~1,375 lines) using the **standard-library `sqlite3`** module directly (no ORM, no migrations framework).
- **Frontend**: server-rendered **Jinja2** templates on top of **Bootstrap 5** (CDN), Font Awesome 6 (CDN) and Google Fonts *Poppins*, progressively enhanced with vanilla JS that talks to the AJAX cart endpoints.
- **Storage**: SQLite database file `grocery.db` in the repository root. It is created, migrated and seeded automatically when `app.py` is imported/started.
- **Domain**: 8 product categories and 34 seeded products with ₹ (INR) pricing, cart, checkout (UPI / Card / COD), order tracking, admin analytics + inventory CRUD, and a staff fulfillment pipeline.
- **Roles**: `customer`, `staff`, `admin` — enforced by session-based auth plus two decorators (`@login_required`, `@role_required`).

Currency is Indian Rupees, formatted as `₹` in templates. Delivery is free above ₹500, otherwise ₹40; a flat 5% GST is added on the subtotal.

## 2. Tech Stack

| Layer | Choice | Notes |
| --- | --- | --- |
| Language | Python 3.9+ (deployed on 3.11.9) | No type hints used; triple-quoted docstrings per function |
| Web framework | Flask >= 3.0 | Single module, no blueprints, no app factory |
| Templating | Jinja2 (Flask default) | `templates/` with `base.html` inheritance |
| Database | SQLite3 via `sqlite3` stdlib | `row_factory = sqlite3.Row`, `PRAGMA foreign_keys = ON` |
| Auth | Flask `session` + `werkzeug.security` hashes | PBKDF2/SHA-256 via `generate_password_hash` |
| CSS | Bootstrap 5.3 CDN + `static/css/style.css` (custom, ~1,300 lines) | Custom emerald theme, no Sass/build step |
| JS | Vanilla ES5/ES6 in `static/js/main.js` | `fetch()` AJAX, no bundler, no npm |
| Deployment | Gunicorn via `Procfile` / `render.yaml` | Render blueprint, `gunicorn app:app` |

There is **no** `package.json`, no npm/node toolchain, no test suite, no linter/formatter config, and no CI workflow. Do not introduce new frameworks, ORMs, build tools, or dependencies unless explicitly requested.

## 3. Quick Start

```powershell
# 1. Install dependencies (flask, werkzeug, gunicorn)
pip install -r requirements.txt

# 2. Run the development server (creates + seeds grocery.db on first run)
python app.py
# -> http://127.0.0.1:5000/
```

- Port: `PORT` env var, default `5000`; binds `0.0.0.0` with `debug=False` (change locally only if needed, never commit a `debug=True`).
- Production entry point: `gunicorn app:app`.
- `grocery.db`, `__pycache__/`, `*.log`, `.env` are gitignored — never commit database files.

### Seeded demo accounts

| Role | Username | Password | Lands on |
| --- | --- | --- | --- |
| Admin | `admin` | `admin123` | `/admin/dashboard` |
| Staff | `staff1` | `staff123` | `/staff/dashboard` (pre-approved) |
| Customer | `customer1` | `cust123` | `/shop` |

The login page has one-click quick-fill buttons for these (`initDemoCredentials()` in `main.js`).

## 4. Repository Layout

```
grocery-store/
├── app.py                     # Everything server-side: config, DB helpers, schema,
│                              # seeding, migrations, auth decorators, all routes
├── requirements.txt           # flask, werkzeug, gunicorn
├── Procfile                   # web: gunicorn app:app
├── render.yaml                # Render blueprint (free plan, PYTHON_VERSION 3.11.9)
├── README.md                  # Human-facing documentation (features, routes, setup)
├── AGENTS.md                  # This file
├── .gitignore                 # __pycache__, *.pyc, *.db, .env, *.log
├── grocery.db                 # Generated at runtime — gitignored
├── templates/
│   ├── base.html              # Master layout: top bar, navbar, flash toasts, footer,
│   │                          # {% block title/extra_head/content/scripts %}
│   ├── index.html             # Storefront: hero, category pills, search, product grid
│   ├── cart.html              # Cart table + bill summary
│   ├── checkout.html          # Address form + UPI / Card / COD selectors
│   ├── order_success.html     # Receipt / invoice
│   ├── my_orders.html         # Customer order history
│   ├── login.html             # Customer + admin sign-in, demo quick-fill buttons
│   ├── register.html          # Customer registration
│   ├── staff_login.html       # Dedicated staff portal sign-in
│   ├── staff_register.html    # Staff access request (pending admin approval)
│   ├── admin/
│   │   ├── dashboard.html     # Revenue / order / stock KPI cards + recent orders
│   │   ├── manage_items.html  # Product table, client-side filter, delete confirm
│   │   ├── add_item.html      # Add-product form
│   │   ├── edit_item.html     # Edit-product form (with image preview)
│   │   ├── transactions.html  # Store-wide order ledger + status filter
│   │   └── manage_users.html  # Staff approvals, revoke, blacklist/restore modal
│   └── staff/
│       ├── dashboard.html     # Pipeline counters + active order queue
│       └── manage_orders.html # Status dispatcher table
└── static/
    ├── css/style.css          # All custom styling, CSS variables, keyframes
    └── js/main.js             # AJAX cart, toasts, live badge, search filter, helpers
```

## 5. Architecture & Request Flow

1. `app.py` is imported → module-level `with app.app_context(): init_db()` runs **immediately** (creates tables, applies `migrate_db()`, seeds users/categories/products if empty).
2. `@app.before_request enforce_account_status()` re-reads the signed-in user on every request and force-logs-out accounts that were blacklisted, or staff whose approval was revoked (exempt endpoints listed in `ACCESS_CONTROL_EXEMPT_ENDPOINTS`).
3. `@app.context_processor inject_global_vars()` injects `current_user`, `global_cart_count` and `pending_approvals` into every template — `base.html` relies on `current_user` for role-aware navigation.
4. Routes query SQLite through `get_db()` (connection cached on Flask `g`), render a Jinja template, or return `jsonify({...})` for AJAX endpoints.
5. `calculate_cart_totals(user_id)` is the single source of truth for cart math: returns `items`, `subtotal`, `delivery_fee`, `gst`, `total`, `cart_count`.
6. Checkout (`POST /checkout`) validates address + stock, inserts `orders`, inserts `order_items` with `price_at_purchase`, decrements `products.stock`, clears the cart, then redirects to the receipt. Every write path calls `db.commit()`.
7. `static/js/main.js` enhances the UI: `addToCart()`, `updateCartQty()`, `removeFromCart()`, `updateLiveCartCount()`, `renderOrderSummary()`, `showToast()`. AJAX handlers expect a JSON body (see each route) and fall back to a redirect when the session expired.

## 6. Data Model (`grocery.db`)

| Table | Key columns | Notes |
| --- | --- | --- |
| `users` | `id`, `username` (unique), `password` (hashed), `role` CHECK(`admin`/`staff`/`customer`), `full_name`, `email`, `is_approved`, `is_blacklisted`, `blacklist_reason`, `created_at` | Access-control columns default to approved / not blacklisted |
| `categories` | `id`, `name` (unique), `icon` (emoji) | 8 seeded rows |
| `products` | `id`, `name`, `category_id` → `categories.id` (ON DELETE SET NULL), `price`, `stock`, `unit`, `description`, `image_url`, `created_at` | 34 seeded rows, Unsplash image URLs |
| `cart` | `id`, `user_id`, `product_id`, `quantity`, UNIQUE(`user_id`,`product_id`) | One row per user/product pair |
| `orders` | `id`, `user_id`, `total_amount`, `payment_method`, `status` CHECK(`Pending`,`Processing`,`Out for Delivery`,`Delivered`,`Cancelled`), `address`, `created_at` | Status is the staff pipeline |
| `order_items` | `id`, `order_id`, `product_id`, `quantity`, `price_at_purchase` | Price snapshot at purchase time |

Schema changes must be made in **two** places: the `CREATE TABLE` script inside `init_db()` and, for existing databases, an `ALTER TABLE` guard inside `migrate_db()` (the pattern uses `PRAGMA table_info` + a set of existing column names). Existing DBs are upgraded in place — never drop user data.

## 7. Route Map

Auth & general
- `GET /` → role-aware redirect (customer → `/shop`, staff → `/staff/dashboard`, admin → `/admin/dashboard`, guest → `/login`)
- `GET|POST /login`, `GET /logout`, `GET|POST /register`
- `GET|POST /staff/login` (approved, non-blacklisted staff only), `GET|POST /staff/register` (creates pending staff)

Customer shopping
- `GET /shop` (`?category=` and `?q=` filters), `GET /cart`, `GET /checkout` / `POST /checkout`
- `POST /cart/add/<int:product_id>`, `POST /cart/update/<int:product_id>`, `POST /cart/remove/<int:product_id>` → JSON (`@login_required`)
- `GET /cart/count` → JSON `{ "count": N }`
- `GET /order/success/<int:order_id>`, `GET /my-orders`

Admin (`@role_required(['admin'])`)
- `GET /admin/dashboard`, `GET /admin/items`, `GET|POST /admin/items/add`, `GET|POST /admin/items/edit/<int:id>`, `POST /admin/items/delete/<int:id>`, `GET /admin/transactions`
- `GET /admin/users`, `POST /admin/users/approve/<int:id>`, `POST /admin/users/revoke/<int:id>`, `POST /admin/users/blacklist/<int:id>`, `POST /admin/users/restore/<int:id>`

Staff (`@role_required(['staff', 'admin'])`)
- `GET /staff/dashboard`, `GET /staff/orders`, `POST /staff/orders/update/<int:id>`

Errors: `@app.errorhandler(404)` and `@app.errorhandler(500)` both re-render `base.html` with a `not_found` / `server_error` flag and the proper status code.

## 8. Coding Conventions

**Python (`app.py`)**
- Keep the single-module layout and section banners:
  ```python
  # ---------------------------------------------------------
  # Section Name
  # ---------------------------------------------------------
  ```
- Every function gets a short triple-quoted docstring describing intent.
- Import Flask helpers from the existing top-level `from flask import (...)` block; add a new stdlib/third-party import only when necessary.
- Use `get_db()` / `g`, never create ad-hoc `sqlite3.connect()` inside routes; always parameterise SQL with `?` placeholders (no f-strings in SQL).
- Use `sqlite3.Row` access by column name (`row['price']`), not numeric indexes.
- Guard routes with the existing decorators: `@app.route(...)` + `@login_required` or `@role_required([...])` (order matters: route first, then auth decorator).
- Feedback uses `flash(message, 'success' | 'danger' | 'warning' | 'info')` followed by `redirect(...)`; AJAX routes return `jsonify({...})` with `success`, a message, and updated totals/count.
- Read request input with `request.form.get(...)` / `request.get_json(silent=True)` and always `.strip()` and validate before writing.

**Templates (Jinja2)**
- Always extend `base.html` and override `{% block title %}`, `{% block content %}`, and `{% block scripts %}` (page-level JS goes in the `scripts` block).
- Use `url_for('endpoint_name')` for every link/form action and `url_for('static', filename='...')` for assets — never hardcode paths.
- Reuse the established CSS classes (`fresh-navbar`, `product-card`, `btn-primary-fresh`, `btn-secondary-fresh`, `stat-card`, `status-pill` + `status-pending|processing|delivered|cancelled`, `badge-admin|staff|customer`) instead of inline styles; small one-off styles are acceptable as `style="..."` like elsewhere.
- Role-conditional markup uses `{% if current_user and current_user.role == 'admin' %}`.
- Bootstrap 5 utility classes are already available via CDN.

**JavaScript (`static/js/main.js`)**
- No build step and no modules: plain functions attached to `window` (e.g. `window.fillDemoLogin`, `addToCart`, `confirmItemDelete`) so inline `onclick=` handlers in templates can call them.
- Use `fetch()` with `X-Requested-With: XMLHttpRequest`, parse JSON, then call `showToast(message, 'success'|'danger'|'info')` and `setCartBadge(count)`.
- Handle the "session expired" path: if the response redirects / is not JSON, fall back to `window.location.href = '/login'`.
- Feature-detect elements (`if (!searchInput) return;`) so the single script can be loaded on every page.

**CSS (`static/css/style.css`)**
- Theme tokens live in `:root` CSS variables: `--primary: #1a6b3c`, `--primary-dark: #0d4a28`, `--accent: #f0c040`.
- Append new component styles near related blocks with a comment banner; keep the mobile-first responsive rules (`@media (max-width: ...)`) at the end of the file.

## 9. Business Rules That Must Not Break

- **Money**: prices are stored as `REAL` in INR; totals are rounded with `round(..., 2)`. Delivery is `0` when `subtotal >= 500` or the cart is empty, otherwise `40`. GST is always `round(subtotal * 0.05, 2)`.
- **Stock**: `POST /checkout` re-validates every cart line against `products.stock` and returns the customer to `/cart` on a shortfall; on success it decrements stock and snapshots `price_at_purchase`.
- **Cart uniqueness**: `UNIQUE(user_id, product_id)` — adding an existing product must `UPDATE` quantity, never `INSERT` a second row.
- **Order status enum**: only `Pending`, `Processing`, `Out for Delivery`, `Delivered`, `Cancelled` are valid (enforced by a CHECK constraint and by the staff dropdown).
- **Access control**: staff authenticate only through `/staff/login` (the shared `/login` flashes a notice and redirects them there) and must satisfy `role = 'staff' AND is_approved = 1 AND is_blacklisted = 0`; admins and customers are never subject to the staff-approval rule. Blacklisted users are rejected at login *and* signed out mid-session by `enforce_account_status`.
- **Roles**: customers must never reach `/admin/*` or `/staff/*` handlers — always keep the `@role_required` decorators when adding routes.

## 10. Common Tasks

**Add a product field (e.g. `brand`)**
1. `init_db()` → add the column to `CREATE TABLE products`.
2. `migrate_db()` → add an `ALTER TABLE products ADD COLUMN brand TEXT` guard using the same `PRAGMA table_info` pattern.
3. Update `admin_add_item` / `admin_edit_item` handlers (`request.form.get('brand')`), their INSERT/UPDATE statements, and the `templates/admin/add_item.html` + `edit_item.html` forms.
4. Show it where relevant (`templates/index.html`, cart, receipts) using `url_for`-based markup and existing classes.

**Add a page / route**
1. Add the handler in the matching section banner of `app.py` with `@app.route(...)` then `@login_required` or `@role_required([...])`.
2. Create the template under `templates/` (or `templates/admin|staff/`) extending `base.html`.
3. Add navigation in `templates/base.html` inside the role-specific `{% if current_user and current_user.role == ... %}` block.
4. If it is called with `fetch()`, return `jsonify(...)` and handle it in `static/js/main.js`; verify the "not logged in → redirect to `/login`" branch.

**Change the theme**
- Edit the `:root` variables at the top of `static/css/style.css` (`--primary`, `--primary-dark`, `--accent`, ...) — do not hardcode hex values in new components.

**Reset the demo data**
- Stop the server, delete `grocery.db`, restart `python app.py`. The schema, demo accounts, 8 categories and 34 products are recreated. Never commit the DB.

## 11. Gotchas

- `init_db()` executes at **import time** (`with app.app_context()` before any route is defined), so simply importing `app` creates/seeds `grocery.db`. Account for this in scripts and tests.
- Templates receive `current_user` as a **dict**, not a model instance: use `current_user['role']`-style Jinja attribute access (`current_user.role` works in Jinja) but never call methods on it.
- `base.html` renders the 404/500 pages via `not_found` / `server_error` flags instead of separate templates.
- The `SECRET_KEY` is currently hardcoded in `app.py`; `render.yaml` defines a generated `SECRET_KEY` env var that the app does **not** read yet — if you touch auth/config, prefer `os.environ.get('SECRET_KEY', ...)`.
- `debug=False` is intentional in the entrypoint; use Flask's CLI (`flask --app app run --debug`) or an env toggle for local debugging instead of committing `debug=True`.
- Session keys in use: `user_id`, `username`, `role`, `full_name`. Logout is `session.clear()` + redirect.
- Images are remote Unsplash URLs (`image_url`), not local assets — there is no `static/images/` folder.
- Amounts must stay floats/`REAL`; formatting for display (₹, `:.2f`) happens in Jinja templates, not in the database.

## 12. Validation Checklist (no automated tests)

There is no test suite, so validate changes manually:

```powershell
# 1. Syntax / import check (also initialises the DB)
python -c "import app; print('ok')"

# 2. Start the server and exercise the flows
python app.py

# 3. Smoke-test the JSON endpoints (after signing in via the browser cookie jar)
#    /cart/count  -> {"count": N}
#    /cart/add/<id>, /cart/update/<id>, /cart/remove/<id> -> {"success": true, ...}
```

Manual regression path: sign in as `customer1` → filter/search the shop → add/update/remove cart items (badge must update) → checkout with UPI, Card and COD → open the receipt and `/my-orders`; sign in as `admin` → dashboard KPIs, add/edit/delete a product, approve/revoke/blacklist a user; sign in as `staff1` (or a newly approved staff account) → move an order through the status pipeline. Confirm a blacklisted account is signed out on the next request.

## 13. Deployment

- **Render**: `render.yaml` defines a free Python web service (`pip install -r requirements.txt` build, `gunicorn app:app` start, generated `SECRET_KEY`, `PYTHON_VERSION=3.11.9`).
- **Heroku-style**: `Procfile` → `web: gunicorn app:app`.
- Local `python app.py` reads `PORT` (default `5000`) and binds `0.0.0.0`.
- The SQLite file lives next to `app.py`; on hosts with ephemeral filesystems the database (and its data) is recreated on each deploy — that is acceptable for the demo, but flag it before promising persistence.

## 14. Documentation Duties

- `README.md` is the user-facing document (features, schema, demo accounts, full route reference). Update it whenever routes, roles, seeded data or setup steps change.
- Keep this `AGENTS.md` in sync with architectural changes (new tables, decorators, endpoints, tooling).
- Commit messages: short imperative summaries (e.g. `Add staff blacklist reason column`, `Fix cart badge count on logout`).



