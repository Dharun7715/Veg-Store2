from flask import Flask, render_template, request, redirect, session
import sqlite3

app = Flask(__name__)
app.secret_key = "secret123"

# 🥦 PRODUCTS
vegetables = [
    {"name": "Tomato", "price": 20, "mrp": 30},
    {"name": "Potato", "price": 30, "mrp": 40},
    {"name": "Onion", "price": 25, "mrp": 35},
    {"name": "Carrot", "price": 40, "mrp": 55},
    {"name": "Beans", "price": 40, "mrp": 60},
    {"name": "Beetroot", "price": 50, "mrp": 70},
    {"name": "Cabbage", "price": 60, "mrp": 80},
    {"name": "Raw Mango", "price": 120, "mrp": 150},
    {"name": "Lemon", "price": 150, "mrp": 180},
    {"name": "Cucumber", "price": 50, "mrp": 70}
]

# 🗄 DB
def init_db():
    conn = sqlite3.connect("database.db")
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT,
        item TEXT,
        quantity INTEGER,
        total INTEGER,
        status TEXT DEFAULT 'Pending'
    )
    """)

    conn.commit()
    conn.close()

init_db()

# 🔐 LOGIN
@app.route('/login', methods=['GET','POST'])
def login():
    if request.method == 'POST':
        phone = request.form['phone']

        if len(phone) != 10 or not phone.isdigit():
            return "❌ Enter valid number"

        session['otp'] = phone[-4:]
        session['phone'] = phone
        return redirect('/verify')

    return render_template('login.html')

# 🔐 VERIFY
@app.route('/verify', methods=['GET','POST'])
def verify():
    if request.method == 'POST':
        if request.form['otp'] == session.get('otp'):
            session['user'] = session['phone']
            session['cart'] = {}
            return redirect('/')
        else:
            return "❌ Wrong OTP"

    return render_template('verify.html')

# 🏠 HOME
@app.route('/')
def home():
    if "user" not in session:
        return redirect('/login')

    search = request.args.get("search", "").lower()

    if search:
        filtered = [v for v in vegetables if search in v["name"].lower()]
    else:
        filtered = vegetables

    cart = session.get("cart", {})

    return render_template("index.html",
                           vegetables=filtered,
                           cart=cart,
                           cart_count=sum(cart.values()),
                           search=search)

# ➕ ADD
@app.route('/add/<name>')
def add(name):
    cart = session.get("cart", {})
    cart[name] = cart.get(name, 0) + 1
    session["cart"] = cart
    session["msg"] = f"{name} added"
    return redirect('/')

# ➕ INCREASE
@app.route('/increase/<name>')
def increase(name):
    cart = session.get("cart", {})
    cart[name] = cart.get(name, 0) + 1
    session["cart"] = cart
    return redirect('/')

# ➖ DECREASE
@app.route('/decrease/<name>')
def decrease(name):
    cart = session.get("cart", {})
    if name in cart:
        if cart[name] > 1:
            cart[name] -= 1
        else:
            del cart[name]
    session["cart"] = cart
    return redirect('/')

# 🛒 CART
@app.route('/cart')
def cart():
    cart = session.get("cart", {})
    items = []
    total = 0

    for name, qty in cart.items():
        for veg in vegetables:
            if veg["name"] == name:
                t = veg["price"] * qty
                total += t
                items.append({"name": name, "qty": qty, "total": t})

    return render_template("cart.html", items=items, total=total)

# 💳 PAYMENT
@app.route('/payment')
def payment():
    cart = session.get("cart", {})
    total = 0

    for name, qty in cart.items():
        for veg in vegetables:
            if veg["name"] == name:
                total += veg["price"] * qty

    discount = 0
    msg = ""

    conn = sqlite3.connect("database.db")
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM orders WHERE username=?", (session["user"],))
    count = cur.fetchone()[0]
    conn.close()

    if total >= 300:
        discount += 50
        msg += "₹50 discount "

    if count == 0:
        discount += 100
        msg += "+ ₹100 first order"

    final_total = max(total - discount, 0)

    return render_template("payment.html",
                           total=total,
                           discount=discount,
                           final_total=final_total,
                           msg=msg)

# ✅ SUCCESS
@app.route('/success')
def success():
    cart = session.get("cart", {})

    conn = sqlite3.connect("database.db")
    cur = conn.cursor()

    for name, qty in cart.items():
        for veg in vegetables:
            if veg["name"] == name:
                total = veg["price"] * qty
                cur.execute(
                    "INSERT INTO orders (username,item,quantity,total,status) VALUES (?,?,?,?,?)",
                    (session["user"], name, qty, total, "Pending")
                )

    conn.commit()
    conn.close()

    session["cart"] = {}
    return render_template("success.html")

# 📦 ORDERS
@app.route('/orders')
def orders():
    conn = sqlite3.connect("database.db")
    cur = conn.cursor()

    cur.execute(
        "SELECT item, quantity, total, status FROM orders WHERE username=?",
        (session["user"],)
    )
    data = cur.fetchall()
    conn.close()

    return render_template("orders.html", orders=data)

# 👑 ADMIN DASHBOARD
@app.route('/admin', methods=['GET','POST'])
def admin():
    conn = sqlite3.connect("database.db")
    cur = conn.cursor()

    if request.method == 'POST':
        order_id = request.form['id']
        status = request.form['status']
        cur.execute("UPDATE orders SET status=? WHERE id=?", (status, order_id))
        conn.commit()

    cur.execute("SELECT * FROM orders")
    data = cur.fetchall()

    total_orders = len(data)
    total_revenue = sum(row[4] for row in data)

    conn.close()

    return render_template("admin.html",
                           orders=data,
                           total_orders=total_orders,
                           total_revenue=total_revenue)

# 🚪 LOGOUT
@app.route('/logout')
def logout():
    session.clear()
    return redirect('/login')

# ▶ RUN
if __name__ == '__main__':
    app.run(debug=True)
