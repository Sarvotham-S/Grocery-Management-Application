from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from datetime import datetime,timedelta 
import os

app = Flask(__name__)
app.secret_key = 'super_secret_demo_key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///gms.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)



# ==========================================
# DATABASE MODELS
# ==========================================

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(250), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False) # Admin / Owner / Customer
    is_blacklisted = db.Column(db.Boolean, default=False)
    
    # Relationships
    cart = db.relationship('Cart', backref='user', uselist=False, lazy=True) # 1-to-1 relationship
    orders = db.relationship('Order', backref='customer', lazy=True)

class Category(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    description = db.Column(db.String(255))
    products = db.relationship('Product', backref='category', lazy=True)

class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    price = db.Column(db.Numeric(10, 2), nullable=False)
    stock = db.Column(db.Integer, nullable=False)
    units = db.Column(db.String(20), nullable=False) # kg, litre, etc.
    expiry_date = db.Column(db.Date, nullable=True)
    category_id = db.Column(db.Integer, db.ForeignKey('category.id'), nullable=False)

class Cart(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), unique=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationship to CartItem
    items = db.relationship('CartItem', backref='cart', lazy=True)

class CartItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    cart_id = db.Column(db.Integer, db.ForeignKey('cart.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    
    # Relationship to get product details easily
    product = db.relationship('Product')

class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    order_date = db.Column(db.DateTime, default=datetime.utcnow)
    total_amount = db.Column(db.Numeric(10, 2), nullable=False)
    status = db.Column(db.String(50), default='Pending') # Pending/Confirmed/Delivered/Cancelled
    
    # Relationships
    items = db.relationship('OrderItem', backref='order', lazy=True)
    payment = db.relationship('Payment', backref='order', uselist=False, lazy=True) # 1-to-1

class OrderItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('order.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    unit_price = db.Column(db.Numeric(10, 2), nullable=False)

class Payment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('order.id'), unique=True, nullable=False)
    amount = db.Column(db.Numeric(10, 2), nullable=False)
    method = db.Column(db.String(50), nullable=False) # UPI/Card/COD
    status = db.Column(db.String(20), default='Pending') # Success/Failed/Pending
    payment_date = db.Column(db.DateTime, default=datetime.utcnow)

# ==========================================
# UTILITY: ROLE-BASED ACCESS CONTROL
# ==========================================
def login_required(role=None):
    def wrapper(fn):
        @wraps(fn)
        def decorated_view(*args, **kwargs):
            if 'user_id' not in session:
                flash('Please log in to access this page.')
                return redirect(url_for('login'))
            if role and session.get('role') != role:
                flash('Access denied. Unauthorized role.')
                return redirect(url_for('login'))
            return fn(*args, **kwargs)
        return decorated_view
    return wrapper


# ==========================================
# ROUTES
# ==========================================

@app.route('/')
def index():
    if 'user_id' in session:
        role = session.get('role')
        if role == 'Admin': return redirect(url_for('admin_dashboard'))
        elif role == 'Staff': return redirect(url_for('staff_dashboard'))
        else: return redirect(url_for('customer_dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        user = User.query.filter_by(email=email).first()
        
        if user and check_password_hash(user.password_hash, password):
            if user.is_blacklisted:
                flash('Your account has been blacklisted.')
                return redirect(url_for('login'))
                
            # UPDATED: We now use user.id instead of user.user_id
            session['user_id'] = user.id
            session['role'] = user.role
            session['name'] = user.name
            return redirect(url_for('index'))
        flash('Invalid email or password.')
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        password = request.form['password']
        role = request.form.get('role', 'Customer') # Default to customer
        
        if User.query.filter_by(email=email).first():
            flash('Email already registered.')
            return redirect(url_for('register'))
            
        hashed_pw = generate_password_hash(password, method='pbkdf2:sha256')
        new_user = User(name=name, email=email, password_hash=hashed_pw, role=role)
        db.session.add(new_user)
        db.session.commit()
        flash('Registration successful! Please log in.')
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# --- Dashboards ---

@app.route('/admin')
@login_required(role='Admin')
def admin_dashboard():
    categories = Category.query.all()
    users = User.query.all()
    return render_template('admin_dashboard.html', categories=categories, users=users)

# ==========================================
# FUNCTIONAL ROUTES (Add these below your dashboard routes)
# ==========================================

@app.route('/admin/add_category', methods=['POST'])
@login_required(role='Admin')
def add_category():
    name = request.form.get('name')
    description = request.form.get('description')
    
    if name:
        new_category = Category(name=name, description=description)
        db.session.add(new_category)
        db.session.commit()
        flash('Category added successfully!')
    else:
        flash('Category name is required.')
        
    return redirect(url_for('admin_dashboard'))
@app.route('/admin/edit_category/<int:id>', methods=['POST'])
@login_required(role='Admin')
def edit_category(id):
    category = Category.query.get(id)
    if category:
        category.name = request.form.get('name')
        category.description = request.form.get('description')
        db.session.commit()
        flash(f'Category updated to "{category.name}" successfully!')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/delete_category/<int:id>', methods=['POST'])
@login_required(role='Admin')
def delete_category(id):
    category = Category.query.get(id)
    if category:
        # Check if there are products in this category before deleting
        if category.products:
            flash(f'Cannot delete category "{category.name}" because it contains products. Please delete or move the products first.')
        else:
            db.session.delete(category)
            db.session.commit()
            flash(f'Category "{category.name}" deleted.')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/toggle_blacklist/<int:id>', methods=['POST'])
@login_required(role='Admin')
def toggle_blacklist(id):
    user = User.query.get(id)
    # Prevent the Admin from accidentally blacklisting themselves!
    if user and user.role != 'Admin':
        user.is_blacklisted = not user.is_blacklisted
        db.session.commit()
        status = "blacklisted" if user.is_blacklisted else "whitelisted"
        flash(f'User {user.name} has been {status}.')
    return redirect(url_for('admin_dashboard'))

@app.route('/staff/add_product', methods=['POST'])
@login_required(role='Staff')
def add_product():
    name = request.form.get('name')
    price = request.form.get('price')
    stock_quantity = request.form.get('stock_quantity')
    unit = request.form.get('unit')
    category_id = request.form.get('category_id')
    
    # Catch the new expiry date from the form
    expiry_date_str = request.form.get('expiry_date') 
    expiry_date = None
    if expiry_date_str:
        # Convert the HTML string 'YYYY-MM-DD' into a Python Date object
        expiry_date = datetime.strptime(expiry_date_str, '%Y-%m-%d').date()
    
    if name and price and stock_quantity and category_id:
        new_product = Product(
            name=name, 
            price=float(price), 
            stock=int(stock_quantity), # Updated to match ER Diagram 'stock'
            units=unit,                # Updated to match ER Diagram 'units'
            category_id=int(category_id),
            expiry_date=expiry_date    # Save the new expiry date
        )
        db.session.add(new_product)
        db.session.commit()
        flash('Product added successfully!')
    else:
        flash('Essential fields are required to add a product.')
        
    return redirect(url_for('staff_dashboard'))

@app.route('/staff/edit_product/<int:id>', methods=['POST'])
@login_required(role='Staff')
def edit_product(id):
    product = Product.query.get(id)
    if product:
        stock = request.form.get('stock')
        price = request.form.get('price')
        if stock is not None:
            product.stock = int(stock)
        if price is not None:
            product.price = float(price)
        db.session.commit()
        flash(f'Product "{product.name}" updated successfully!')
    return redirect(url_for('staff_dashboard'))

@app.route('/staff/delete_product/<int:id>', methods=['POST'])
@login_required(role='Staff')
def delete_product(id):
    product = Product.query.get(id)
    if product:
        try:
            db.session.delete(product)
            db.session.commit()
            flash(f'Product "{product.name}" deleted.')
        except Exception as e:
            # If the product is already in an Order, deleting it will crash the DB.
            db.session.rollback()
            flash(f'Cannot delete "{product.name}" because it is part of customer order history. Please update its stock to 0 instead.')
    return redirect(url_for('staff_dashboard'))

@app.route('/add_to_cart/<int:product_id>', methods=['POST'])
@login_required(role='Customer')
def add_to_cart(product_id):
    quantity = int(request.form.get('quantity', 1))
    product = Product.query.get(product_id)
    
    if product and product.stock >= quantity:
        # 1. Get or create the user's database cart
        cart = Cart.query.filter_by(user_id=session['user_id']).first()
        if not cart:
            cart = Cart(user_id=session['user_id'])
            db.session.add(cart)
            db.session.flush() # Flush to generate the cart ID
            
        # 2. Check if product is already in the cart to update quantity
        cart_item = CartItem.query.filter_by(cart_id=cart.id, product_id=product.id).first()
        if cart_item:
            cart_item.quantity += quantity
        else:
            cart_item = CartItem(cart_id=cart.id, product_id=product.id, quantity=quantity)
            db.session.add(cart_item)
            
        db.session.commit()
        flash(f'Added {quantity} x {product.name} to your cart.')
    else:
        flash('Not enough stock available.')
        
    return redirect(url_for('customer_dashboard'))

@app.route('/cart')
@login_required(role='Customer')
def view_cart():
    cart = Cart.query.filter_by(user_id=session['user_id']).first()
    cart_items = cart.items if cart else []
    total_price = sum(item.product.price * item.quantity for item in cart_items)
            
    return render_template('cart.html', cart_items=cart_items, total_price=total_price)

@app.route('/checkout', methods=['POST'])
@login_required(role='Customer')
def checkout():
    cart = Cart.query.filter_by(user_id=session['user_id']).first()
    if not cart or not cart.items:
        flash("Your cart is empty.")
        return redirect(url_for('customer_dashboard'))
        
    payment_method = request.form.get('payment_method')
    total_amount = sum(item.product.price * item.quantity for item in cart.items)
    
    # 1. Create the Order
    new_order = Order(user_id=session['user_id'], total_amount=total_amount, status='Confirmed')
    db.session.add(new_order)
    db.session.flush() 
    
    # 2. Process Items and Payment
    for item in cart.items:
        item.product.stock -= item.quantity # Deduct stock
        
        # Create OrderItem
        order_item = OrderItem(
            order_id=new_order.id,
            product_id=item.product_id,
            quantity=item.quantity,
            unit_price=item.product.price
        )
        db.session.add(order_item)
        db.session.delete(item) # Remove item from cart after processing
        
    # 3. Create standalone Payment record
    new_payment = Payment(
        order_id=new_order.id,
        amount=total_amount,
        method=payment_method,
        status='Success'
    )
    db.session.add(new_payment)
    
    db.session.commit()
    flash(f"Checkout successful! Paid via {payment_method}.")
    return redirect(url_for('customer_dashboard'))
# ==========================================
# CUSTOMER FEATURES (IST Time & Cancel)
# ==========================================

# 1. Custom Jinja Filter for IST Conversion
@app.template_filter('to_ist')
def to_ist_filter(dt):
    if dt is None:
        return ""
    # IST is 5 hours and 30 minutes ahead of UTC
    ist_time = dt + timedelta(hours=5, minutes=30)
    # Format: DD-MM-YYYY HH:MM AM/PM
    return ist_time.strftime('%d-%m-%Y %I:%M %p')

# 2. Cancel Order Route
@app.route('/customer/cancel_order/<int:order_id>', methods=['POST'])
@login_required(role='Customer')
def cancel_order(order_id):
    order = Order.query.get(order_id)
    
    # Security: Ensure the order exists, belongs to the logged-in user, and isn't already delivered
    if order and order.user_id == session.get('user_id'):
        if order.status in ['Pending', 'Confirmed']:
            order.status = 'Cancelled'
            
            # RESTORE STOCK: Give the items back to the inventory
            for item in order.items:
                product = Product.query.get(item.product_id)
                if product:
                    product.stock += item.quantity
                    
            db.session.commit()
            flash(f'Order #{order.id} has been cancelled successfully. Stock has been restored.')
        else:
            flash('Cannot cancel an order that is already out for delivery or completed.')
    return redirect(url_for('customer_dashboard'))

@app.route('/staff')
@login_required(role='Staff')
def staff_dashboard():
    products = Product.query.all()
    categories = Category.query.all()
    orders = Order.query.all() # FETCH ALL ORDERS FOR STAFF
    return render_template('staff_dashboard.html', products=products, categories=categories, orders=orders)

@app.route('/customer')
@login_required(role='Customer')
def customer_dashboard():
    products = Product.query.all()
    # FETCH ONLY ORDERS FOR THIS SPECIFIC CUSTOMER
    orders = Order.query.filter_by(user_id=session['user_id']).order_by(Order.order_date.desc()).all() 
    return render_template('customer_dashboard.html', products=products, orders=orders)

# ==========================================
# NEW FUNCTIONAL ROUTE 
# ==========================================
@app.route('/staff/update_order/<int:order_id>', methods=['POST'])
@login_required(role='Staff')
def update_order(order_id):
    order = Order.query.get(order_id)
    if order:
        order.status = request.form.get('status')
        db.session.commit()
        flash(f'Order #{order_id} status updated to {order.status}.')
    return redirect(url_for('staff_dashboard'))

# ==========================================
# INIT SCRIPT (Runs on startup)
# ==========================================
with app.app_context():
    db.create_all()
    # Create a default admin if none exists
    if not User.query.filter_by(role='Admin').first():
        admin_pw = generate_password_hash('admin123', method='pbkdf2:sha256')
        admin = User(name='Super Admin', email='admin@gms.com', password_hash=admin_pw, role='Admin')
        db.session.add(admin)
        db.session.commit()
        print("Default Admin created: admin@gms.com / admin123")

if __name__ == '__main__':
    app.run(debug=True)