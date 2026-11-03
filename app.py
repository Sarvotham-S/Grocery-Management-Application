import os
import sqlite3
from functools import wraps
from flask import (
    Flask, render_template, request, redirect, url_for,
    session, flash, jsonify, g, abort
)
from werkzeug.security import generate_password_hash, check_password_hash

# ---------------------------------------------------------
# App Initialization & Configuration
# ---------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE = os.path.join(BASE_DIR, 'grocery.db')

app = Flask(__name__)
app.config['SECRET_KEY'] = 'freshmart_secure_production_secret_key_2026_xyz!'
app.config['DATABASE'] = DATABASE

# ---------------------------------------------------------
# Database Helpers
# ---------------------------------------------------------
def get_db():
    """Opens a new database connection if there is none yet for the current application context."""
    if 'db' not in g:
        g.db = sqlite3.connect(app.config['DATABASE'])
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db

@app.teardown_appcontext
def close_db(error=None):
    """Closes the database at the end of the request."""
    db = g.pop('db', None)
    if db is not None:
        db.close()

def migrate_db(db):
    """Adds the admin access-control columns to databases created by earlier versions."""
    cursor = db.cursor()
    cursor.execute("PRAGMA table_info(users)")
    existing_columns = {row['name'] for row in cursor.fetchall()}

    if 'is_approved' not in existing_columns:
        cursor.execute("ALTER TABLE users ADD COLUMN is_approved INTEGER NOT NULL DEFAULT 1")
    if 'is_blacklisted' not in existing_columns:
        cursor.execute("ALTER TABLE users ADD COLUMN is_blacklisted INTEGER NOT NULL DEFAULT 0")
    if 'blacklist_reason' not in existing_columns:
        cursor.execute("ALTER TABLE users ADD COLUMN blacklist_reason TEXT")
    db.commit()

def init_db():
    """Initializes schema and seeds default data if tables are empty."""
    with app.app_context():
        db = get_db()
        cursor = db.cursor()

        # Create tables
        cursor.executescript('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role TEXT NOT NULL CHECK(role IN ('admin','staff','customer')),
            full_name TEXT,
            email TEXT,
            is_approved INTEGER NOT NULL DEFAULT 1,
            is_blacklisted INTEGER NOT NULL DEFAULT 0,
            blacklist_reason TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            icon TEXT
        );

        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            category_id INTEGER REFERENCES categories(id) ON DELETE SET NULL,
            price REAL NOT NULL,
            stock INTEGER NOT NULL DEFAULT 0,
            unit TEXT DEFAULT 'piece',
            description TEXT,
            image_url TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS cart (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
            product_id INTEGER REFERENCES products(id) ON DELETE CASCADE,
            quantity INTEGER NOT NULL DEFAULT 1,
            UNIQUE(user_id, product_id)
        );

        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
            total_amount REAL NOT NULL,
            payment_method TEXT NOT NULL,
            status TEXT DEFAULT 'Pending' CHECK(status IN ('Pending','Processing','Out for Delivery','Delivered','Cancelled')),
            address TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS order_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id INTEGER REFERENCES orders(id) ON DELETE CASCADE,
            product_id INTEGER REFERENCES products(id) ON DELETE CASCADE,
            quantity INTEGER NOT NULL,
            price_at_purchase REAL NOT NULL
        );
        ''')
        db.commit()

        # Apply lightweight migrations for databases created before access control existed
        migrate_db(db)

        # Seed Users
        cursor.execute("SELECT COUNT(*) as count FROM users")
        if cursor.fetchone()['count'] == 0:
            demo_users = [
                ('admin', generate_password_hash('admin123'), 'admin', 'Store Administrator', 'admin@freshmart.local'),
                ('staff1', generate_password_hash('staff123'), 'staff', 'Ramesh Kumar (Store Operations)', 'staff1@freshmart.local'),
                ('customer1', generate_password_hash('cust123'), 'customer', 'Priya Sharma', 'priya@example.com')
            ]
            cursor.executemany(
                "INSERT INTO users (username, password, role, full_name, email) VALUES (?, ?, ?, ?, ?)",
                demo_users
            )
            db.commit()

        # Seed Categories
        cursor.execute("SELECT COUNT(*) as count FROM categories")
        if cursor.fetchone()['count'] == 0:
            seed_categories = [
                ('Fruits', '🍎'),
                ('Vegetables', '🥦'),
                ('Dairy & Eggs', '🧀'),
                ('Bakery', '🍞'),
                ('Beverages', '🥤'),
                ('Snacks & Munchies', '🍿'),
                ('Meat & Fish', '🐟'),
                ('Household Essentials', '🧹')
            ]
            cursor.executemany("INSERT INTO categories (name, icon) VALUES (?, ?)", seed_categories)
            db.commit()

        # Seed Products (30+ products spread across the 8 categories)
        cursor.execute("SELECT COUNT(*) as count FROM products")
        if cursor.fetchone()['count'] == 0:
            # Map category name to ID
            cursor.execute("SELECT id, name FROM categories")
            cats = {row['name']: row['id'] for row in cursor.fetchall()}

            seed_products = [
                # Fruits
                ('Shimla Fresh Apples', cats['Fruits'], 160.00, 45, 'kg', 'Crisp, sweet, hand-picked royal gala apples from Himachal orchards.', 'https://images.unsplash.com/photo-1560806887-1e4cd0b6cbd6?w=600&auto=format&fit=crop&q=80'),
                ('Robusta Organic Bananas', cats['Fruits'], 45.00, 80, 'dozen', 'Rich in potassium and naturally ripened farm-fresh bananas.', 'https://images.unsplash.com/photo-1571771894821-ce9b6c11b08e?w=600&auto=format&fit=crop&q=80'),
                ('Nagpur Sweet Oranges', cats['Fruits'], 90.00, 35, 'kg', 'Juicy, tangy and vitamin C rich citrus oranges from Nagpur.', 'https://images.unsplash.com/photo-1611080626919-7cf5a9dbab5b?w=600&auto=format&fit=crop&q=80'),
                ('Thompson Seedless Grapes', cats['Fruits'], 110.00, 25, '500g', 'Plump, sweet green seedless grapes packed under hygienic cooling.', 'https://images.unsplash.com/photo-1537640538966-79f369143f8f?w=600&auto=format&fit=crop&q=80'),
                ('Alphonso Mango Box', cats['Fruits'], 480.00, 15, 'box (6 pcs)', 'The king of mangoes with unmatched aroma and velvet pulp.', 'https://images.unsplash.com/photo-1553279768-865429fa0078?w=600&auto=format&fit=crop&q=80'),

                # Vegetables
                ('Farm Fresh Potatoes', cats['Vegetables'], 32.00, 120, 'kg', 'Starchy all-purpose earthen potatoes, ideal for curries and snacks.', 'https://images.unsplash.com/photo-1518977676601-b53f82aba655?w=600&auto=format&fit=crop&q=80'),
                ('Nasik Red Onions', cats['Vegetables'], 38.00, 100, 'kg', 'Pungent, high-grade onions direct from Nasik farmers cooperative.', 'https://images.unsplash.com/photo-1618512496248-a07fe83aa8cb?w=600&auto=format&fit=crop&q=80'),
                ('Vine-Ripened Hybrid Tomatoes', cats['Vegetables'], 42.00, 75, 'kg', 'Firm red juicy tomatoes for gravies, fresh salads, and soups.', 'https://images.unsplash.com/photo-1592924357228-91a4daadcfea?w=600&auto=format&fit=crop&q=80'),
                ('Organic Spinach (Palak)', cats['Vegetables'], 25.00, 40, 'bunch', 'Tender dark green spinach leaves thoroughly washed and pesticide-free.', 'https://images.unsplash.com/photo-1576045057995-568f588f82fb?w=600&auto=format&fit=crop&q=80'),
                ('Green Bell Peppers (Capsicum)', cats['Vegetables'], 65.00, 30, 'kg', 'Crunchy bell peppers packed with antioxidants and vitamins.', 'https://images.unsplash.com/photo-1563565375-f3fdfdbefa83?w=600&auto=format&fit=crop&q=80'),
                ('Fresh Cauliflower', cats['Vegetables'], 40.00, 20, 'piece', 'Snowy white tightly bunched florets fresh from the dawn harvest.', 'https://images.unsplash.com/photo-1568584711075-3d021a7c3ca3?w=600&auto=format&fit=crop&q=80'),

                # Dairy & Eggs
                ('Amul Taaza Homogenised Toned Milk', cats['Dairy & Eggs'], 54.00, 60, '1 Litre', 'Wholesome pasteurized toned milk fortified with vitamins A & D.', 'https://images.unsplash.com/photo-1550583724-b2692b85b150?w=600&auto=format&fit=crop&q=80'),
                ('Farm Fresh Brown Eggs', cats['Dairy & Eggs'], 95.00, 50, 'pack of 6', 'Nutrient-rich protein brown eggs from free-range poultry.', 'https://images.unsplash.com/photo-1582722872445-44dc5f7e3c8f?w=600&auto=format&fit=crop&q=80'),
                ('Fresh Malai Paneer', cats['Dairy & Eggs'], 115.00, 28, '200g', 'Ultra-soft, creamy cottage cheese made from 100% cow milk.', 'https://images.unsplash.com/photo-1631452180519-c014fe946bc7?w=600&auto=format&fit=crop&q=80'),
                ('Amul Pasteurised Salted Butter', cats['Dairy & Eggs'], 58.00, 40, '100g', 'The legendary taste of India butter for bread, toasts, and parathas.', 'https://images.unsplash.com/photo-1589985270826-4b7bb135bc9d?w=600&auto=format&fit=crop&q=80'),
                ('Greek Style Plain Curd (Dahi)', cats['Dairy & Eggs'], 60.00, 35, '400g', 'Thick probiotic natural curd cultured using traditional methods.', 'https://images.unsplash.com/photo-1488477181946-6428a0291777?w=600&auto=format&fit=crop&q=80'),

                # Bakery
                ('100% Whole Wheat Brown Bread', cats['Bakery'], 48.00, 30, '400g', 'Fiber-dense artisanal sliced bread with zero maida and zero trans fats.', 'https://images.unsplash.com/photo-1509440159596-0249088772ff?w=600&auto=format&fit=crop&q=80'),
                ('Multi-grain Garlic Baguette', cats['Bakery'], 75.00, 18, 'piece', 'Stone-baked crispy crust baguette topped with herbs and roasted garlic.', 'https://images.unsplash.com/photo-1586444248902-2f64eddc13df?w=600&auto=format&fit=crop&q=80'),
                ('Flaky Butter Croissants', cats['Bakery'], 120.00, 22, 'pack of 2', 'Golden, layered authentic French style butter croissants.', 'https://images.unsplash.com/photo-1555507036-ab1f4038808a?w=600&auto=format&fit=crop&q=80'),
                ('Sweet Fruit Buns (Pav)', cats['Bakery'], 35.00, 40, 'pack of 4', 'Soft bakery buns dotted with sweet candied fruits and raisins.', 'https://images.unsplash.com/photo-1509440159596-0249088772ff?w=600&auto=format&fit=crop&q=80'),

                # Beverages
                ('Tata Tea Gold Premium Leaves', cats['Beverages'], 240.00, 35, '500g', 'A blend of fine Assam teas with gently rolled aromatic long leaves.', 'https://images.unsplash.com/photo-1594631252845-29fc4cc8cde9?w=600&auto=format&fit=crop&q=80'),
                ('Nescafe Classic Instant Coffee', cats['Beverages'], 195.00, 25, '100g jar', 'Rich and smooth roasted robusta coffee beans for your morning kick.', 'https://images.unsplash.com/photo-1514432324607-a09d9b4aefdd?w=600&auto=format&fit=crop&q=80'),
                ('Tender Coconut Water', cats['Beverages'], 55.00, 60, '200ml pack', '100% pure tender coconut water with naturally balanced electrolytes.', 'https://images.unsplash.com/photo-1525385133512-2f3bdd039054?w=600&auto=format&fit=crop&q=80'),
                ('Raw Cold-Pressed Orange Juice', cats['Beverages'], 110.00, 20, '300ml', 'Unpasteurized fresh Valencia orange juice with zero added sugar.', 'https://images.unsplash.com/photo-1600271886742-f049cd451bba?w=600&auto=format&fit=crop&q=80'),

                # Snacks & Munchies
                ('Haldiram Aloo Bhujia', cats['Snacks & Munchies'], 90.00, 45, '400g', 'Crunchy spiced potato and chickpea flour noodles with mint zest.', 'https://images.unsplash.com/photo-1566478989037-eec170784d0b?w=600&auto=format&fit=crop&q=80'),
                ('Act II Classic Salted Microwave Popcorn', cats['Snacks & Munchies'], 40.00, 70, 'pack of 3', 'Buttery, theatre-style fluffy popcorn pops hot in 3 minutes.', 'https://images.unsplash.com/photo-1578849278619-e73505e9610f?w=600&auto=format&fit=crop&q=80'),
                ('Roasted Salted California Almonds', cats['Snacks & Munchies'], 280.00, 30, '250g', 'Gourmet handpicked almonds roasted to crunchy perfection.', 'https://images.unsplash.com/photo-1508061257971-83269b231050?w=600&auto=format&fit=crop&q=80'),
                ('Dark Chocolate Cookies Box', cats['Snacks & Munchies'], 125.00, 35, '200g', 'Decadent cookies packed with rich Belgian dark chocolate chunks.', 'https://images.unsplash.com/photo-1499636136210-6f4ee915583e?w=600&auto=format&fit=crop&q=80'),

                # Meat & Fish
                ('Fresh Chicken Breast Fillet', cats['Meat & Fish'], 260.00, 18, '500g', 'Skinless, boneless tender antibiotic-free chicken breasts.', 'https://images.unsplash.com/photo-1604503468506-a8da13d82791?w=600&auto=format&fit=crop&q=80'),
                ('Cleaned White Prawns (Jhinga)', cats['Meat & Fish'], 390.00, 12, '500g', 'Freshwater medium prawns, peeled, deveined and ready to cook.', 'https://images.unsplash.com/photo-1565680018434-b513d5e5fd47?w=600&auto=format&fit=crop&q=80'),
                ('Fresh Rohu Fish Steaks', cats['Meat & Fish'], 220.00, 15, '1 kg', 'Neatly cut bone-in steaks of freshwater Rohu fish for curries.', 'https://images.unsplash.com/photo-1534948216015-843149f72be3?w=600&auto=format&fit=crop&q=80'),

                # Household Essentials
                ('Surf Excel Matic Liquid Detergent', cats['Household Essentials'], 235.00, 30, '1 Litre', 'Superior stain removal formula designed for front and top load washing.', 'https://images.unsplash.com/photo-1585421514738-01798e348b17?w=600&auto=format&fit=crop&q=80'),
                ('Vim Lemon Dishwash Gel', cats['Household Essentials'], 105.00, 50, '750ml', 'Cuts tough grease instantly with the power of 100 lemons.', 'https://images.unsplash.com/photo-1583947215259-38e31be8751f?w=600&auto=format&fit=crop&q=80'),
                ('Dettol Disinfectant Antibacterial Liquid', cats['Household Essentials'], 180.00, 40, '500ml', 'Proven household germ protection for laundry, bathing, and floor cleaning.', 'https://images.unsplash.com/photo-1584308666744-24d5c474f2ae?w=600&auto=format&fit=crop&q=80'),
                ('Soft Touch 2-Ply Kitchen Paper Towels', cats['Household Essentials'], 130.00, 45, 'pack of 2 rolls', 'Super-absorbent paper towels for wiping counters and absorbing oil.', 'https://images.unsplash.com/photo-1584556812952-905ffd0c611a?w=600&auto=format&fit=crop&q=80')
            ]

            cursor.executemany(
                '''INSERT INTO products (name, category_id, price, stock, unit, description, image_url)
                   VALUES (?, ?, ?, ?, ?, ?, ?)''',
                seed_products
            )
            db.commit()

# Ensure database is initialized on server startup (local & WSGI/Render)
with app.app_context():
    init_db()

# ---------------------------------------------------------
# Authentication & Authorization Decorators
# ---------------------------------------------------------
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in to access this page.', 'warning')
            return redirect(url_for('login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function

def role_required(roles):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'user_id' not in session:
                flash('Please log in to continue.', 'warning')
                return redirect(url_for('login', next=request.url))
            if session.get('role') not in roles:
                flash('Access denied. You do not have permission for that area.', 'danger')
                return redirect(url_for('index'))
            return f(*args, **kwargs)
        return decorated_function
    return decorator

# ---------------------------------------------------------
# Context Processors & Template Globals
# ---------------------------------------------------------
@app.context_processor
def inject_global_vars():
    """Injects user authentication state and live cart count into all templates."""
    user = None
    cart_count = 0
    pending_approvals = 0
    if 'user_id' in session:
        user = {
            'id': session.get('user_id'),
            'username': session.get('username'),
            'role': session.get('role'),
            'full_name': session.get('full_name')
        }
        # Customer cart count
        db = get_db()
        cur = db.cursor()
        cur.execute("SELECT SUM(quantity) as total_qty FROM cart WHERE user_id = ?", (session['user_id'],))
        row = cur.fetchone()
        if row and row['total_qty']:
            cart_count = row['total_qty']

        # Admin: number of staff accounts still waiting for approval
        if session.get('role') == 'admin':
            cur.execute('''
                SELECT COUNT(*) as count FROM users
                WHERE role = 'staff' AND is_approved = 0 AND is_blacklisted = 0
            ''')
            row = cur.fetchone()
            if row:
                pending_approvals = row['count']

    return {
        'current_user': user,
        'global_cart_count': cart_count,
        'pending_approvals': pending_approvals
    }

# ---------------------------------------------------------
# Account Access Control (Admin-managed blacklist & staff approval)
# ---------------------------------------------------------
# Endpoints that must stay reachable for signed-in users so a blocked account
# can still sign out or move to the correct sign-in portal.
ACCESS_CONTROL_EXEMPT_ENDPOINTS = (
    'static', 'login', 'staff_login', 'register', 'staff_register', 'logout'
)

def get_account_status_message(user):
    """Returns a (message, category) tuple when an account may not use the store, else None."""
    if user is None:
        return ('Your account could not be found. Please sign in again.', 'danger')

    if user['is_blacklisted']:
        reason = (user['blacklist_reason'] or '').strip()
        detail = f' Reason given: {reason}.' if reason else ''
        return (
            'Your account has been blacklisted by the store administrator and can no longer be used.'
            f'{detail} Please contact support@freshmart.local for assistance.',
            'danger'
        )

    if user['role'] == 'staff' and not user['is_approved']:
        return (
            'Your staff account is awaiting administrator approval. '
            'You will be able to sign in once an admin approves your request.',
            'warning'
        )

    return None

@app.before_request
def enforce_account_status():
    """Ends the session of any blacklisted user or staff member whose approval was revoked."""
    if request.endpoint in ACCESS_CONTROL_EXEMPT_ENDPOINTS:
        return None

    if 'user_id' not in session:
        return None

    db = get_db()
    cursor = db.cursor()
    cursor.execute("SELECT * FROM users WHERE id = ?", (session['user_id'],))
    user = cursor.fetchone()

    status = get_account_status_message(user)
    if not status:
        return None

    role = session.get('role')
    session.clear()
    flash(status[0], status[1])
    if role == 'staff':
        return redirect(url_for('staff_login'))
    return redirect(url_for('login'))

# ---------------------------------------------------------
# Common Helpers
# ---------------------------------------------------------
def calculate_cart_totals(user_id):
    """Calculates subtotal, delivery fee, GST (5%), and grand total for a user's cart."""
    db = get_db()
    cursor = db.cursor()
    cursor.execute('''
        SELECT c.id as cart_id, c.quantity, p.id as product_id, p.name, p.price, p.stock, p.unit, p.image_url,
               (c.quantity * p.price) as item_total
        FROM cart c
        JOIN products p ON c.product_id = p.id
        WHERE c.user_id = ?
    ''', (user_id,))
    items = cursor.fetchall()

    subtotal = sum(item['item_total'] for item in items)
    # Delivery fee: ₹40 if subtotal < 500, else Free (0)
    if subtotal == 0:
        delivery_fee = 0.0
    elif subtotal >= 500.0:
        delivery_fee = 0.0
    else:
        delivery_fee = 40.0

    gst = round(subtotal * 0.05, 2)  # 5% GST
    total = round(subtotal + delivery_fee + gst, 2)
    cart_count = sum(item['quantity'] for item in items)

    return {
        'items': items,
        'cart_items': items,
        'subtotal': round(subtotal, 2),
        'delivery_fee': round(delivery_fee, 2),
        'gst': gst,
        'total': total,
        'cart_count': cart_count
    }

# ---------------------------------------------------------
# Public & Auth Routes
# ---------------------------------------------------------
@app.route('/')
def index():
    """Redirect to role-specific dashboard if logged in, else redirect to login."""
    if 'user_id' in session:
        role = session.get('role')
        if role == 'admin':
            return redirect(url_for('admin_dashboard'))
        elif role == 'staff':
            return redirect(url_for('staff_dashboard'))
        else:
            return redirect(url_for('shop'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()

        if not username or not password:
            flash('Please provide both username and password.', 'danger')
            return render_template('login.html', username=username)

        db = get_db()
        cursor = db.cursor()
        cursor.execute("SELECT * FROM users WHERE username = ?", (username,))
        user = cursor.fetchone()

        if user and check_password_hash(user['password'], password):
            # Staff members have their own dedicated sign-in portal
            if user['role'] == 'staff':
                flash('Staff members must sign in through the dedicated Staff Login portal.', 'info')
                return redirect(url_for('staff_login'))

            status = get_account_status_message(user)
            if status:
                flash(status[0], status[1])
                return render_template('login.html', username=username)

            session['user_id'] = user['id']
            session['username'] = user['username']
            session['role'] = user['role']
            session['full_name'] = user['full_name']
            flash(f"Welcome back, {user['full_name'] or user['username']}!", 'success')

            # Route by role or redirected next parameter
            next_url = request.args.get('next')
            if next_url:
                return redirect(next_url)

            if user['role'] == 'admin':
                return redirect(url_for('admin_dashboard'))
            else:
                return redirect(url_for('shop'))
        else:
            flash('Invalid username or password. Please try again.', 'danger')

    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out successfully.', 'info')
    return redirect(url_for('login'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        full_name = request.form.get('full_name', '').strip()
        email = request.form.get('email', '').strip()
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        confirm_password = request.form.get('confirm_password', '').strip()

        if not full_name or not email or not username or not password:
            flash('All fields are required.', 'danger')
            return render_template('register.html')

        if password != confirm_password:
            flash('Passwords do not match.', 'danger')
            return render_template('register.html', full_name=full_name, email=email, username=username)

        if len(password) < 6:
            flash('Password must be at least 6 characters.', 'warning')
            return render_template('register.html', full_name=full_name, email=email, username=username)

        db = get_db()
        cursor = db.cursor()
        cursor.execute("SELECT id FROM users WHERE username = ?", (username,))
        if cursor.fetchone():
            flash('Username is already taken. Please choose another.', 'danger')
            return render_template('register.html', full_name=full_name, email=email)

        cursor.execute("SELECT id FROM users WHERE email = ?", (email,))
        if cursor.fetchone():
            flash('Email is already registered. Please login or use a different email.', 'danger')
            return render_template('register.html', full_name=full_name, username=username)

        # Register customer
        hashed_pw = generate_password_hash(password)
        cursor.execute(
            "INSERT INTO users (username, password, role, full_name, email) VALUES (?, ?, 'customer', ?, ?)",
            (username, hashed_pw, full_name, email)
        )
        db.commit()

        flash('Registration successful! You can now log in with your credentials.', 'success')
        return redirect(url_for('login'))

    return render_template('register.html')

# ---------------------------------------------------------
# Staff Authentication (Dedicated Portal + Admin Approval)
# ---------------------------------------------------------
@app.route('/staff/login', methods=['GET', 'POST'])
def staff_login():
    """Dedicated sign-in portal for staff accounts approved by an administrator."""
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()

        if not username or not password:
            flash('Please provide both your staff username and password.', 'danger')
            return render_template('staff_login.html', username=username)

        db = get_db()
        cursor = db.cursor()
        cursor.execute("SELECT * FROM users WHERE username = ?", (username,))
        user = cursor.fetchone()

        if not user or not check_password_hash(user['password'], password):
            flash('Invalid staff credentials. Please try again.', 'danger')
            return render_template('staff_login.html', username=username)

        if user['role'] != 'staff':
            flash(
                'This portal is reserved for staff accounts. Customers and administrators '
                'must sign in through the main login page.',
                'danger'
            )
            return render_template('staff_login.html', username=username)

        status = get_account_status_message(user)
        if status:
            flash(status[0], status[1])
            return render_template('staff_login.html', username=username)

        session['user_id'] = user['id']
        session['username'] = user['username']
        session['role'] = user['role']
        session['full_name'] = user['full_name']
        flash(f"Welcome back, {user['full_name'] or user['username']}! Staff access granted.", 'success')

        next_url = request.args.get('next')
        if next_url:
            return redirect(next_url)
        return redirect(url_for('staff_dashboard'))

    return render_template('staff_login.html')

@app.route('/staff/register', methods=['GET', 'POST'])
def staff_register():
    """Staff self-registration. New accounts stay unapproved until an admin approves them."""
    if request.method == 'POST':
        full_name = request.form.get('full_name', '').strip()
        email = request.form.get('email', '').strip()
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        confirm_password = request.form.get('confirm_password', '').strip()

        form_values = {'full_name': full_name, 'email': email, 'username': username}

        if not full_name or not email or not username or not password:
            flash('All fields are required.', 'danger')
            return render_template('staff_register.html', **form_values)

        if password != confirm_password:
            flash('Passwords do not match.', 'danger')
            return render_template('staff_register.html', **form_values)

        if len(password) < 6:
            flash('Password must be at least 6 characters.', 'warning')
            return render_template('staff_register.html', **form_values)

        db = get_db()
        cursor = db.cursor()
        cursor.execute("SELECT id FROM users WHERE username = ?", (username,))
        if cursor.fetchone():
            flash('Username is already taken. Please choose another.', 'danger')
            return render_template('staff_register.html', **form_values)

        cursor.execute("SELECT id FROM users WHERE email = ?", (email,))
        if cursor.fetchone():
            flash('Email is already registered. Please login or use a different email.', 'danger')
            return render_template('staff_register.html', **form_values)

        hashed_pw = generate_password_hash(password)
        cursor.execute(
            '''INSERT INTO users (username, password, role, full_name, email, is_approved)
               VALUES (?, ?, 'staff', ?, ?, 0)''',
            (username, hashed_pw, full_name, email)
        )
        db.commit()

        flash(
            'Staff registration submitted! An administrator must approve your account '
            'before you can sign in to the staff portal.',
            'info'
        )
        return redirect(url_for('staff_login'))

    return render_template('staff_register.html')

# ---------------------------------------------------------
# Customer Shop & Browse
# ---------------------------------------------------------
@app.route('/shop')
def shop():
    """Customer storefront displaying products with search & category filtering."""
    db = get_db()
    cursor = db.cursor()

    # Load all categories
    cursor.execute("SELECT * FROM categories ORDER BY id ASC")
    categories = cursor.fetchall()

    # Filter parameters
    cat_id = request.args.get('category', type=int)
    search_query = request.args.get('q', '').strip()

    sql = '''
        SELECT p.*, c.name as category_name, c.icon as category_icon
        FROM products p
        LEFT JOIN categories c ON p.category_id = c.id
        WHERE 1=1
    '''
    params = []

    if cat_id:
        sql += " AND p.category_id = ?"
        params.append(cat_id)

    if search_query:
        sql += " AND (p.name LIKE ? OR p.description LIKE ?)"
        wildcard = f"%{search_query}%"
        params.extend([wildcard, wildcard])

    sql += " ORDER BY p.id DESC"
    cursor.execute(sql, params)
    products = cursor.fetchall()

    return render_template(
        'index.html',
        categories=categories,
        products=products,
        selected_category=cat_id,
        search_query=search_query
    )

# ---------------------------------------------------------
# Cart Endpoints (AJAX & Page)
# ---------------------------------------------------------
@app.route('/cart/add/<int:product_id>', methods=['POST'])
@login_required
def add_to_cart(product_id):
    """Add product to cart or increment quantity."""
    user_id = session['user_id']
    db = get_db()
    cursor = db.cursor()

    # Verify product and stock
    cursor.execute("SELECT * FROM products WHERE id = ?", (product_id,))
    product = cursor.fetchone()
    if not product:
        return jsonify({'success': False, 'message': 'Product not found.'}), 404

    if product['stock'] <= 0:
        return jsonify({'success': False, 'message': f"Sorry, '{product['name']}' is out of stock."}), 400

    # Check existing cart item
    cursor.execute("SELECT * FROM cart WHERE user_id = ? AND product_id = ?", (user_id, product_id))
    cart_item = cursor.fetchone()

    if cart_item:
        new_qty = cart_item['quantity'] + 1
        if new_qty > product['stock']:
            return jsonify({'success': False, 'message': f"Only {product['stock']} units available in stock."}), 400
        cursor.execute("UPDATE cart SET quantity = ? WHERE id = ?", (new_qty, cart_item['id']))
    else:
        cursor.execute("INSERT INTO cart (user_id, product_id, quantity) VALUES (?, ?, 1)", (user_id, product_id))

    db.commit()

    # Calculate new cart count
    cursor.execute("SELECT SUM(quantity) as total FROM cart WHERE user_id = ?", (user_id,))
    cart_count = cursor.fetchone()['total'] or 0

    return jsonify({
        'success': True,
        'message': f"Added '{product['name']}' to your cart!",
        'cart_count': cart_count
    })

@app.route('/cart/update/<int:product_id>', methods=['POST'])
@login_required
def update_cart_quantity(product_id):
    """Update cart quantity for a specific product."""
    user_id = session['user_id']
    data = request.get_json(silent=True) or request.form
    try:
        new_qty = int(data.get('quantity', 1))
    except (TypeError, ValueError):
        new_qty = 1

    db = get_db()
    cursor = db.cursor()

    cursor.execute("SELECT * FROM products WHERE id = ?", (product_id,))
    product = cursor.fetchone()
    if not product:
        return jsonify({'success': False, 'message': 'Product not found.'}), 404

    if new_qty <= 0:
        cursor.execute("DELETE FROM cart WHERE user_id = ? AND product_id = ?", (user_id, product_id))
        db.commit()
    else:
        if new_qty > product['stock']:
            return jsonify({
                'success': False,
                'message': f"Only {product['stock']} items available in stock."
            }), 400
        cursor.execute(
            "UPDATE cart SET quantity = ? WHERE user_id = ? AND product_id = ?",
            (new_qty, user_id, product_id)
        )
        db.commit()

    totals = calculate_cart_totals(user_id)
    item_subtotal = round(product['price'] * new_qty, 2) if new_qty > 0 else 0.0

    return jsonify({
        'success': True,
        'new_qty': new_qty,
        'item_subtotal': item_subtotal,
        'subtotal': totals['subtotal'],
        'delivery_fee': totals['delivery_fee'],
        'gst': totals['gst'],
        'total': totals['total'],
        'cart_count': totals['cart_count']
    })

@app.route('/cart/remove/<int:product_id>', methods=['POST'])
@login_required
def remove_from_cart(product_id):
    """Remove item from cart."""
    user_id = session['user_id']
    db = get_db()
    cursor = db.cursor()
    cursor.execute("DELETE FROM cart WHERE user_id = ? AND product_id = ?", (user_id, product_id))
    db.commit()

    totals = calculate_cart_totals(user_id)
    return jsonify({
        'success': True,
        'message': 'Item removed from your cart.',
        'subtotal': totals['subtotal'],
        'delivery_fee': totals['delivery_fee'],
        'gst': totals['gst'],
        'total': totals['total'],
        'cart_count': totals['cart_count']
    })

@app.route('/cart')
@login_required
def view_cart():
    """Render customer cart page."""
    user_id = session['user_id']
    cart_data = calculate_cart_totals(user_id)
    return render_template('cart.html', cart_data=cart_data)

@app.route('/cart/count')
def cart_count():
    """Returns live JSON badge count for current user."""
    if 'user_id' not in session:
        return jsonify({'count': 0})
    db = get_db()
    cursor = db.cursor()
    cursor.execute("SELECT SUM(quantity) as total FROM cart WHERE user_id = ?", (session['user_id'],))
    row = cursor.fetchone()
    count = row['total'] if row and row['total'] else 0
    return jsonify({'count': count})

# ---------------------------------------------------------
# Checkout & Order Placement
# ---------------------------------------------------------
@app.route('/checkout', methods=['GET', 'POST'])
@login_required
def checkout():
    user_id = session['user_id']
    cart_data = calculate_cart_totals(user_id)

    if not cart_data['items']:
        flash('Your cart is empty. Add items before checking out.', 'info')
        return redirect(url_for('shop'))

    db = get_db()
    cursor = db.cursor()

    if request.method == 'POST':
        address = request.form.get('address', '').strip()
        payment_method = request.form.get('payment_method', 'COD').strip()

        if not address:
            flash('Please provide a complete delivery address.', 'danger')
            return render_template('checkout.html', cart_data=cart_data)

        # Validate stock availability
        for item in cart_data['items']:
            if item['quantity'] > item['stock']:
                flash(f"Insufficient stock for '{item['name']}'. Please adjust your cart.", 'danger')
                return redirect(url_for('view_cart'))

        # Create Order
        cursor.execute(
            '''INSERT INTO orders (user_id, total_amount, payment_method, status, address)
               VALUES (?, ?, ?, 'Pending', ?)''',
            (user_id, cart_data['total'], payment_method, address)
        )
        order_id = cursor.lastrowid

        # Insert Order Items & Deduct Stock
        for item in cart_data['items']:
            cursor.execute(
                '''INSERT INTO order_items (order_id, product_id, quantity, price_at_purchase)
                   VALUES (?, ?, ?, ?)''',
                (order_id, item['product_id'], item['quantity'], item['price'])
            )
            cursor.execute(
                "UPDATE products SET stock = stock - ? WHERE id = ?",
                (item['quantity'], item['product_id'])
            )

        # Empty Cart
        cursor.execute("DELETE FROM cart WHERE user_id = ?", (user_id,))
        db.commit()

        flash('Your order has been placed successfully!', 'success')
        return redirect(url_for('order_success', order_id=order_id))

    # Retrieve user info for pre-filling address or phone if desired
    cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
    user = cursor.fetchone()

    return render_template('checkout.html', cart_data=cart_data, user=user)

@app.route('/order/success/<int:order_id>')
@login_required
def order_success(order_id):
    user_id = session['user_id']
    db = get_db()
    cursor = db.cursor()

    # Admin/staff can view any order; customer only their own
    if session.get('role') in ['admin', 'staff']:
        cursor.execute("SELECT o.*, u.full_name, u.email FROM orders o JOIN users u ON o.user_id = u.id WHERE o.id = ?", (order_id,))
    else:
        cursor.execute("SELECT o.*, u.full_name, u.email FROM orders o JOIN users u ON o.user_id = u.id WHERE o.id = ? AND o.user_id = ?", (order_id, user_id))

    order = cursor.fetchone()
    if not order:
        flash('Order not found or access denied.', 'danger')
        return redirect(url_for('shop'))

    cursor.execute('''
        SELECT oi.*, p.name, p.unit, p.image_url
        FROM order_items oi
        JOIN products p ON oi.product_id = p.id
        WHERE oi.order_id = ?
    ''', (order_id,))
    items = cursor.fetchall()

    return render_template('order_success.html', order=order, items=items)

@app.route('/my-orders')
@login_required
def my_orders():
    """Customer order history."""
    user_id = session['user_id']
    db = get_db()
    cursor = db.cursor()

    cursor.execute('''
        SELECT * FROM orders
        WHERE user_id = ?
        ORDER BY created_at DESC
    ''', (user_id,))
    orders = cursor.fetchall()

    # Fetch items for each order
    orders_with_items = []
    for ord_row in orders:
        cursor.execute('''
            SELECT oi.*, p.name, p.unit, p.image_url
            FROM order_items oi
            JOIN products p ON oi.product_id = p.id
            WHERE oi.order_id = ?
        ''', (ord_row['id'],))
        order_items = cursor.fetchall()
        orders_with_items.append({
            'order': ord_row,
            'items': order_items,
            'order_items': order_items
        })

    return render_template('my_orders.html', orders=orders_with_items)

# ---------------------------------------------------------
# Admin Routes
# ---------------------------------------------------------
@app.route('/admin/dashboard')
@role_required(['admin'])
def admin_dashboard():
    db = get_db()
    cursor = db.cursor()

    # Product count
    cursor.execute("SELECT COUNT(*) as count FROM products")
    total_products = cursor.fetchone()['count']

    # Total orders
    cursor.execute("SELECT COUNT(*) as count FROM orders")
    total_orders = cursor.fetchone()['count']

    # Total Revenue (only delivered or non-cancelled orders)
    cursor.execute("SELECT SUM(total_amount) as total FROM orders WHERE status != 'Cancelled'")
    revenue_row = cursor.fetchone()
    total_revenue = round(revenue_row['total'], 2) if revenue_row and revenue_row['total'] else 0.0

    # Low stock items (stock <= 5)
    cursor.execute("SELECT COUNT(*) as count FROM products WHERE stock <= 5")
    low_stock_count = cursor.fetchone()['count']

    # Recent 5 Orders
    cursor.execute('''
        SELECT o.*, u.username, u.full_name
        FROM orders o
        JOIN users u ON o.user_id = u.id
        ORDER BY o.created_at DESC
        LIMIT 5
    ''')
    recent_orders = cursor.fetchall()

    # Low stock products list
    cursor.execute('''
        SELECT p.*, c.name as category_name
        FROM products p
        LEFT JOIN categories c ON p.category_id = c.id
        WHERE p.stock <= 5
        ORDER BY p.stock ASC
        LIMIT 5
    ''')
    low_stock_products = cursor.fetchall()

    return render_template(
        'admin/dashboard.html',
        total_products=total_products,
        total_orders=total_orders,
        total_revenue=total_revenue,
        low_stock_count=low_stock_count,
        recent_orders=recent_orders,
        low_stock_products=low_stock_products
    )

@app.route('/admin/items')
@role_required(['admin'])
def admin_items():
    db = get_db()
    cursor = db.cursor()
    cursor.execute('''
        SELECT p.*, c.name as category_name, c.icon as category_icon
        FROM products p
        LEFT JOIN categories c ON p.category_id = c.id
        ORDER BY p.id DESC
    ''')
    products = cursor.fetchall()
    return render_template('admin/manage_items.html', products=products)

@app.route('/admin/items/add', methods=['GET', 'POST'])
@role_required(['admin'])
def admin_add_item():
    db = get_db()
    cursor = db.cursor()

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        category_id = request.form.get('category_id', type=int)
        price = request.form.get('price', type=float)
        stock = request.form.get('stock', type=int)
        unit = request.form.get('unit', 'piece').strip()
        description = request.form.get('description', '').strip()
        image_url = request.form.get('image_url', '').strip()

        if not name or price is None or stock is None:
            flash('Name, price and stock are required fields.', 'danger')
            cursor.execute("SELECT * FROM categories ORDER BY name ASC")
            categories = cursor.fetchall()
            return render_template('admin/add_item.html', categories=categories)

        if not image_url:
            image_url = 'https://images.unsplash.com/photo-1542838132-92c53300491e?w=600&auto=format&fit=crop&q=80'

        cursor.execute(
            '''INSERT INTO products (name, category_id, price, stock, unit, description, image_url)
               VALUES (?, ?, ?, ?, ?, ?, ?)''',
            (name, category_id, price, stock, unit, description, image_url)
        )
        db.commit()

        flash(f"Product '{name}' added successfully!", 'success')
        return redirect(url_for('admin_items'))

    cursor.execute("SELECT * FROM categories ORDER BY name ASC")
    categories = cursor.fetchall()
    return render_template('admin/add_item.html', categories=categories)

@app.route('/admin/items/edit/<int:id>', methods=['GET', 'POST'])
@role_required(['admin'])
def admin_edit_item(id):
    db = get_db()
    cursor = db.cursor()

    cursor.execute("SELECT * FROM products WHERE id = ?", (id,))
    product = cursor.fetchone()
    if not product:
        flash('Product not found.', 'danger')
        return redirect(url_for('admin_items'))

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        category_id = request.form.get('category_id', type=int)
        price = request.form.get('price', type=float)
        stock = request.form.get('stock', type=int)
        unit = request.form.get('unit', 'piece').strip()
        description = request.form.get('description', '').strip()
        image_url = request.form.get('image_url', '').strip()

        if not name or price is None or stock is None:
            flash('Name, price and stock are required fields.', 'danger')
        else:
            if not image_url:
                image_url = product['image_url']

            cursor.execute(
                '''UPDATE products
                   SET name = ?, category_id = ?, price = ?, stock = ?, unit = ?, description = ?, image_url = ?
                   WHERE id = ?''',
                (name, category_id, price, stock, unit, description, image_url, id)
            )
            db.commit()
            flash(f"Product '{name}' updated successfully!", 'success')
            return redirect(url_for('admin_items'))

    cursor.execute("SELECT * FROM categories ORDER BY name ASC")
    categories = cursor.fetchall()
    return render_template('admin/edit_item.html', product=product, categories=categories)

@app.route('/admin/items/delete/<int:id>', methods=['POST'])
@role_required(['admin'])
def admin_delete_item(id):
    db = get_db()
    cursor = db.cursor()
    cursor.execute("SELECT name FROM products WHERE id = ?", (id,))
    prod = cursor.fetchone()
    if prod:
        cursor.execute("DELETE FROM products WHERE id = ?", (id,))
        db.commit()
        flash(f"Product '{prod['name']}' was removed from store inventory.", 'success')
    else:
        flash('Product not found.', 'danger')
    return redirect(url_for('admin_items'))

@app.route('/admin/transactions')
@role_required(['admin'])
def admin_transactions():
    """All store transactions with filters."""
    db = get_db()
    cursor = db.cursor()

    status_filter = request.args.get('status', '').strip()
    sql = '''
        SELECT o.*, u.username, u.full_name, u.email,
               (SELECT COUNT(*) FROM order_items WHERE order_id = o.id) as item_count
        FROM orders o
        JOIN users u ON o.user_id = u.id
        WHERE 1=1
    '''
    params = []
    if status_filter:
        sql += " AND o.status = ?"
        params.append(status_filter)

    sql += " ORDER BY o.created_at DESC"
    cursor.execute(sql, params)
    orders = cursor.fetchall()

    return render_template('admin/transactions.html', orders=orders, current_filter=status_filter)

# ---------------------------------------------------------
# Admin User Access Control (Approvals & Blacklist)
# ---------------------------------------------------------
@app.route('/admin/users')
@role_required(['admin'])
def admin_users():
    """Lists every account so the admin can approve staff or blacklist users."""
    db = get_db()
    cursor = db.cursor()

    role_filter = request.args.get('role', '').strip()
    status_filter = request.args.get('status', '').strip()
    search_query = request.args.get('q', '').strip()

    sql = "SELECT * FROM users WHERE 1=1"
    params = []

    if role_filter in ('admin', 'staff', 'customer'):
        sql += " AND role = ?"
        params.append(role_filter)

    if status_filter == 'pending':
        sql += " AND role = 'staff' AND is_approved = 0 AND is_blacklisted = 0"
    elif status_filter == 'approved':
        sql += " AND is_blacklisted = 0 AND (role != 'staff' OR is_approved = 1)"
    elif status_filter == 'blacklisted':
        sql += " AND is_blacklisted = 1"

    if search_query:
        wildcard = f"%{search_query}%"
        sql += " AND (username LIKE ? OR full_name LIKE ? OR email LIKE ?)"
        params.extend([wildcard, wildcard, wildcard])

    sql += '''
        ORDER BY CASE role WHEN 'admin' THEN 0 WHEN 'staff' THEN 1 ELSE 2 END,
                 is_blacklisted DESC, is_approved ASC, id ASC
    '''
    cursor.execute(sql, params)
    users = cursor.fetchall()

    # Summary counters always reflect the whole user table
    cursor.execute("SELECT COUNT(*) as count FROM users")
    total_users = cursor.fetchone()['count']

    cursor.execute('''
        SELECT COUNT(*) as count FROM users
        WHERE role = 'staff' AND is_approved = 0 AND is_blacklisted = 0
    ''')
    pending_staff_count = cursor.fetchone()['count']

    cursor.execute('''
        SELECT COUNT(*) as count FROM users
        WHERE role = 'staff' AND is_approved = 1 AND is_blacklisted = 0
    ''')
    active_staff_count = cursor.fetchone()['count']

    cursor.execute("SELECT COUNT(*) as count FROM users WHERE is_blacklisted = 1")
    blacklisted_count = cursor.fetchone()['count']

    return render_template(
        'admin/manage_users.html',
        users=users,
        total_users=total_users,
        pending_staff_count=pending_staff_count,
        active_staff_count=active_staff_count,
        blacklisted_count=blacklisted_count,
        role_filter=role_filter,
        status_filter=status_filter,
        search_query=search_query
    )

@app.route('/admin/users/approve/<int:id>', methods=['POST'])
@role_required(['admin'])
def admin_approve_staff(id):
    """Approves a pending staff account so it can use the staff portal."""
    db = get_db()
    cursor = db.cursor()
    cursor.execute("SELECT * FROM users WHERE id = ?", (id,))
    user = cursor.fetchone()

    if not user:
        flash('Account not found.', 'danger')
    elif user['role'] != 'staff':
        flash('Only staff accounts require administrator approval.', 'warning')
    elif user['is_blacklisted']:
        flash('This account is blacklisted. Restore it before approving.', 'warning')
    elif user['is_approved']:
        flash(f"Staff account '{user['username']}' is already approved.", 'info')
    else:
        cursor.execute("UPDATE users SET is_approved = 1 WHERE id = ?", (id,))
        db.commit()
        flash(
            f"Staff account '{user['full_name'] or user['username']}' approved. "
            'They can now sign in to the staff portal.',
            'success'
        )

    return redirect(url_for('admin_users'))

@app.route('/admin/users/revoke/<int:id>', methods=['POST'])
@role_required(['admin'])
def admin_revoke_staff(id):
    """Sends an approved staff member back to pending approval."""
    db = get_db()
    cursor = db.cursor()
    cursor.execute("SELECT * FROM users WHERE id = ?", (id,))
    user = cursor.fetchone()

    if not user:
        flash('Account not found.', 'danger')
    elif user['role'] != 'staff':
        flash('Only staff accounts can have their approval revoked.', 'warning')
    elif not user['is_approved']:
        flash(f"Staff account '{user['username']}' is already pending approval.", 'info')
    else:
        cursor.execute("UPDATE users SET is_approved = 0 WHERE id = ?", (id,))
        db.commit()
        flash(
            f"Approval revoked for '{user['full_name'] or user['username']}'. "
            'They can no longer sign in until re-approved.',
            'success'
        )

    return redirect(url_for('admin_users'))

@app.route('/admin/users/blacklist/<int:id>', methods=['POST'])
@role_required(['admin'])
def admin_blacklist_user(id):
    """Blacklists a customer or staff account, blocking all store access."""
    reason = request.form.get('reason', '').strip()
    db = get_db()
    cursor = db.cursor()
    cursor.execute("SELECT * FROM users WHERE id = ?", (id,))
    user = cursor.fetchone()

    if not user:
        flash('Account not found.', 'danger')
    elif user['role'] == 'admin':
        flash('Administrator accounts cannot be blacklisted.', 'danger')
    elif user['id'] == session.get('user_id'):
        flash('You cannot blacklist your own account.', 'danger')
    elif user['is_blacklisted']:
        flash(f"'{user['username']}' is already blacklisted.", 'info')
    else:
        cursor.execute(
            "UPDATE users SET is_blacklisted = 1, blacklist_reason = ? WHERE id = ?",
            (reason or None, id)
        )
        db.commit()
        flash(
            f"'{user['full_name'] or user['username']}' has been blacklisted and can no longer sign in.",
            'success'
        )

    return redirect(url_for('admin_users'))

@app.route('/admin/users/restore/<int:id>', methods=['POST'])
@role_required(['admin'])
def admin_restore_user(id):
    """Lifts a blacklist so the account can sign in again (staff still need approval)."""
    db = get_db()
    cursor = db.cursor()
    cursor.execute("SELECT * FROM users WHERE id = ?", (id,))
    user = cursor.fetchone()

    if not user:
        flash('Account not found.', 'danger')
    elif not user['is_blacklisted']:
        flash(f"'{user['username']}' is not blacklisted.", 'info')
    else:
        cursor.execute(
            "UPDATE users SET is_blacklisted = 0, blacklist_reason = NULL WHERE id = ?",
            (id,)
        )
        db.commit()
        flash(f"'{user['full_name'] or user['username']}' has been restored to active status.", 'success')

    return redirect(url_for('admin_users'))

# ---------------------------------------------------------
# Staff Routes
# ---------------------------------------------------------
@app.route('/staff/dashboard')
@role_required(['staff', 'admin'])
def staff_dashboard():
    db = get_db()
    cursor = db.cursor()

    # Orders status distribution
    cursor.execute("SELECT status, COUNT(*) as count FROM orders GROUP BY status")
    status_counts = {row['status']: row['count'] for row in cursor.fetchall()}

    # Recent active orders needing attention (Pending or Processing)
    cursor.execute('''
        SELECT o.*, u.full_name, u.username
        FROM orders o
        JOIN users u ON o.user_id = u.id
        WHERE o.status IN ('Pending', 'Processing', 'Out for Delivery')
        ORDER BY o.created_at ASC
        LIMIT 10
    ''')
    active_orders = cursor.fetchall()

    return render_template('staff/dashboard.html', status_counts=status_counts, active_orders=active_orders)

@app.route('/staff/orders')
@role_required(['staff', 'admin'])
def staff_orders():
    db = get_db()
    cursor = db.cursor()

    status_filter = request.args.get('status', '').strip()
    sql = '''
        SELECT o.*, u.full_name, u.username, u.email
        FROM orders o
        JOIN users u ON o.user_id = u.id
        WHERE 1=1
    '''
    params = []
    if status_filter:
        sql += " AND o.status = ?"
        params.append(status_filter)

    sql += " ORDER BY o.created_at DESC"
    cursor.execute(sql, params)
    orders = cursor.fetchall()

    # Preload order items for fast expand view
    orders_data = []
    for o in orders:
        cursor.execute('''
            SELECT oi.*, p.name, p.unit
            FROM order_items oi
            JOIN products p ON oi.product_id = p.id
            WHERE oi.order_id = ?
        ''', (o['id'],))
        items = cursor.fetchall()
        orders_data.append({
            'order': o,
            'items': items,
            'order_items': items
        })

    return render_template('staff/manage_orders.html', orders_data=orders_data, current_filter=status_filter)

@app.route('/staff/orders/update/<int:id>', methods=['POST'])
@role_required(['staff', 'admin'])
def staff_update_order(id):
    new_status = request.form.get('status', '').strip()
    valid_statuses = ['Pending', 'Processing', 'Out for Delivery', 'Delivered', 'Cancelled']

    if new_status not in valid_statuses:
        flash('Invalid order status selected.', 'danger')
        return redirect(url_for('staff_orders'))

    db = get_db()
    cursor = db.cursor()
    cursor.execute("UPDATE orders SET status = ? WHERE id = ?", (new_status, id))
    db.commit()

    flash(f"Order #{id} status updated to '{new_status}'.", 'success')
    return redirect(url_for('staff_orders'))

# ---------------------------------------------------------
# Error Handlers
# ---------------------------------------------------------
@app.errorhandler(404)
def page_not_found(e):
    return render_template('base.html', not_found=True), 404

@app.errorhandler(500)
def server_error(e):
    return render_template('base.html', server_error=True), 500

# ---------------------------------------------------------
# Entry Point
# ---------------------------------------------------------
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    print(f"Database initialized and ready. Starting FreshMart Server on port {port}...")
    app.run(host='0.0.0.0', port=port, debug=False)
