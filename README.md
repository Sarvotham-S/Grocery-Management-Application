# 🛒 FreshMart - Production-Ready Grocery Store Web Application

A full-featured, responsive, production-ready e-commerce grocery store web application built using **Python Flask**, **SQLite3**, **Bootstrap 5**, and modern asynchronous JavaScript.

---

## 🌟 Key Features

### 🛍️ Customer Experience
- **Interactive Storefront**: Browse 30+ farm-fresh products across 8 categories with high-resolution imagery and Indian Rupee (₹) pricing.
- **Fast Client-Side & Server-Side Filtering**: Instant live search by keyword and single-click category pill filters (Fruits, Vegetables, Dairy & Eggs, Bakery, Beverages, Snacks, Meat & Fish, Household).
- **Asynchronous Cart Management**: Real-time Add-to-Cart, quantity increment/decrement, and item removal via AJAX with instant feedback toasts and animated header badge counters.
- **Dynamic Delivery & Tax Calculator**: Automatic free delivery on orders over ₹500 (or ₹40 standard fee), along with 5% GST calculation.
- **Multi-Option Checkout**: Seamless simulation of three payment modes:
  - **UPI Instant Transfer**: VPA address validation (Google Pay / PhonePe / Paytm / BHIM).
  - **Credit/Debit Card**: Card number, expiry, and CVV simulation.
  - **Cash on Delivery (COD)**: Cash or rider QR scan upon doorstep delivery.
- **Order Tracking & Receipts**: Detailed post-checkout receipts and complete historical customer order ledger (`/my-orders`).

### ⚙️ Admin Control Center (`/admin/dashboard`)
- **Key Metrics Overview**: Real-time tally of total revenue from completed orders, total order count, active catalog size, and low-stock alerts.
- **Inventory Management (`/admin/items`)**: Full CRUD operations for products (Add, Edit, Delete) with image preview and category assignments.
- **Store-Wide Transaction Ledger (`/admin/transactions`)**: Searchable and filterable master list of all customer transactions with direct link to receipts.
- **User Access & Approvals (`/admin/users`)**: Administrator-only access-control console. Approve new staff accounts before their first sign-in, revoke an approval at any time, and blacklist (or restore) any customer or staff account.

### 🚚 Staff Fulfillment Hub (`/staff/dashboard`)
- **Dedicated Staff Portal (`/staff/login`)**: Separate sign-in page reserved for staff accounts. Staff can request access at `/staff/register`, and each new account stays pending until an administrator approves it.
- **Order Pipeline Workflow**: Visual count of orders across five operational stages:
  - `Pending` → `Processing` → `Out for Delivery` → `Delivered` / `Cancelled`
- **Rapid Status Dispatcher (`/staff/orders`)**: Dedicated table for fulfillment teams to update order statuses in real-time as items are packed and handed to riders.

---

## 🗂️ Project Structure

```
grocery_store/
├── app.py                      # Core Flask application, SQLite schema & routes
├── README.md                   # Project documentation & setup instructions
├── templates/
│   ├── base.html               # Master layout (Navbar, Footer, Toasts, Cart badge)
│   ├── login.html              # Sign-in portal with quick-fill demo accounts
│   ├── staff_login.html        # Dedicated staff sign-in portal
│   ├── staff_register.html     # Staff access request form (pending approval)
│   ├── register.html           # Customer registration form
│   ├── index.html              # Customer storefront (hero banner, search, grid)
│   ├── cart.html               # Shopping cart table & order summary
│   ├── checkout.html           # 2-column checkout with UPI, Card & COD options
│   ├── order_success.html      # Confirmation receipt & invoice details
│   ├── my_orders.html          # Customer past order history
│   ├── admin/
│   │   ├── dashboard.html      # Admin stats cards & low stock warnings
│   │   ├── manage_items.html   # Product catalog table with search & actions
│   │   ├── add_item.html       # Add product form
│   │   ├── edit_item.html      # Edit product form with preview
│   │   ├── transactions.html   # Storewide orders table with status filter
│   │   └── manage_users.html   # Staff approvals & blacklist controls
│   └── staff/
│       ├── dashboard.html      # Staff order stage analytics
│       └── manage_orders.html  # Staff order status update table
└── static/
    ├── css/
    │   └── style.css           # 600+ lines of custom responsive styling & animations
    └── js/
        └── main.js             # AJAX cart operations, toasts, search filter & helpers
```

---

## 💾 Database Schema (SQLite)

The application automatically creates and seeds `grocery.db` on first execution using pure Python `sqlite3`:

1. **`users`**: User credentials, full name, email, role (`admin`, `staff`, `customer`), creation timestamp. Passwords securely hashed with `werkzeug.security`.
2. **`categories`**: Category ID, name, and visual emoji icon.
3. **`products`**: Product ID, foreign key `category_id`, name, price (₹), stock quantity, unit (`kg`, `500g`, `dozen`, `pack`, etc.), description, and image URL.
4. **`cart`**: User cart items linking `user_id` and `product_id` with unique constraint and item quantity.
5. **`orders`**: Order ID, `user_id`, total amount, payment method (`UPI`, `Card`, `COD`), delivery address, timestamp, and status (`Pending`, `Processing`, `Out for Delivery`, `Delivered`, `Cancelled`).
6. **`order_items`**: Order line items linking `order_id`, `product_id`, purchase quantity, and unit price at moment of purchase.

---

## 🔑 Pre-Seeded Demo Accounts

The application automatically initializes with three test accounts for each role. You can also click the quick-fill buttons directly on the login page:

| Role | Username | Password | Access / Capabilities |
| :--- | :--- | :--- | :--- |
| **Admin** | `admin` | `admin123` | Full access to revenue analytics, inventory CRUD, transactions |
| **Staff** | `staff1` | `staff123` | Order fulfillment hub, dispatch management & status updates |
| **Customer** | `customer1` | `cust123` | Product browsing, cart operations, checkout, order history |

*New customers can also register at `/register` at any time. Staff members sign in through the dedicated portal at `/staff/login`; the seeded `staff1` account is pre-approved, while self-registered staff stay pending until the admin approves them in `/admin/users`.*

---

## 🚀 Quickstart & Installation

### 1. Requirements
- Python 3.9+
- Flask and Werkzeug (standard dependencies)

### 2. Install Dependencies
```bash
pip install flask werkzeug
```

### 3. Run the Application
Navigate to the project root and launch `app.py`:
```bash
python app.py
```

Open your browser and navigate to:
```
http://127.0.0.1:5000/
```

On first launch, FreshMart will automatically create `grocery.db`, establish all tables, and seed 8 categories and 34 realistic products. Existing databases are upgraded automatically with the new staff-approval and blacklist columns.

---

## 📡 API & Route Reference

### Authentication & General
- `GET /` - Root redirector (sends guests to `/login`, customers to `/shop`, staff/admin to their respective dashboards)
- `GET /login`, `POST /login` - Customer & administrator authentication (staff are redirected to the staff portal)
- `GET /staff/login`, `POST /staff/login` - Dedicated staff sign-in portal (approved, non-blacklisted staff only)
- `GET /staff/register`, `POST /staff/register` - Staff access request; creates a staff account pending admin approval
- `GET /logout` - Terminates session
- `GET /register`, `POST /register` - Customer registration

### Customer Shopping & Cart
- `GET /shop` - Grocery catalog with `?category=` and `?q=` filtering
- `POST /cart/add/<product_id>` - AJAX endpoint to add item or increment count
- `POST /cart/update/<product_id>` - AJAX endpoint to adjust quantity or remove if 0
- `POST /cart/remove/<product_id>` - AJAX endpoint to delete item from cart
- `GET /cart` - View shopping basket and bill breakdown
- `GET /cart/count` - AJAX endpoint returning live cart count `{ count: N }`
- `GET /checkout`, `POST /checkout` - Address verification and order placement
- `GET /order/success/<order_id>` - Detailed order confirmation invoice
- `GET /my-orders` - Customer's past orders history

### Admin Operations
- `GET /admin/dashboard` - Business analytics, revenue totals, recent orders, low stock warnings
- `GET /admin/items` - Inventory management catalog table
- `GET /admin/items/add`, `POST /admin/items/add` - Add new product form
- `GET /admin/items/edit/<id>`, `POST /admin/items/edit/<id>` - Edit product form
- `POST /admin/items/delete/<id>` - Delete product from inventory
- `GET /admin/transactions` - Master transaction ledger with status filters
- `GET /admin/users` - User access console with search, role and status filters
- `POST /admin/users/approve/<id>` - Approve a pending staff account
- `POST /admin/users/revoke/<id>` - Revoke a staff member's approval
- `POST /admin/users/blacklist/<id>` - Blacklist a customer or staff account (optional reason)
- `POST /admin/users/restore/<id>` - Lift a blacklist and restore account access

### Staff Operations
- `GET /staff/dashboard` - Order fulfillment stage overview and priority queue
- `GET /staff/orders` - Order dispatch table with fast status changer
- `POST /staff/orders/update/<id>` - Update order pipeline status

---

## 🎨 UI & Design Highlights

- **Custom Typography**: Clean Google Fonts *Poppins* styling.
- **Deep Emerald Palette**: High-contrast, fresh grocery palette (`#1a6b3c` primary, `#0d4a28` primary-dark, `#f0c040` accent).
- **Responsive Layout**: Designed mobile-first for smartphones, tablets, and wide desktop displays.
- **Micro-Interactions**: Hover lifts on product cards, animated gradient hero banners, badge pops on cart updates, and slide-in toast notifications.

---

## 🛡️ Security & Reliability

- **Password Hashing**: Uses Werkzeug's PBKDF2/SHA-256 password hashing.
- **Role-Based Access Control**: Flask route decorators `@login_required` and `@role_required` prevent unauthorized view access.
- **Admin-Managed Account Access**: Staff accounts require explicit administrator approval before first sign-in. Blacklisted accounts are rejected at login and signed out mid-session by a request-level guard.
- **Foreign Key Enforcement**: SQLite PRAGMA `foreign_keys = ON` ensures relational integrity across orders, carts, and items.
- **Inventory Concurrency Guard**: Stock availability is validated at time of checkout to prevent overselling.
