from flask import Flask, render_template, redirect, request, session
import sqlite3
import random

app = Flask(__name__)
app.secret_key = "secret123"

# PRODUCTS
vegetables = [
    {"name": "Tomato", "price": 20},
    {"name": "Potato", "price": 30},
    {"name": "Onion", "price": 25},
    {"name": "Carrot", "price": 40}
]

# DATABASE INIT
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

# 🏠 HOME
@app.route('/')
def home():
    if "user" not in session:
        return redirect('/login')

    cart = session.get("cart", {})
    cart_count = sum(cart.values())

    return render_template("index.html",
                           vegetables=vegetables,
                           cart=cart,
                           cart_count=cart_count)

# 🔐 LOGIN
@app.route('/login', methods=['GET','POST'])
def login():
    if request.method == "POST":
        phone = request.form["phone"]
        otp = str(random.randint(1000,9999))

        session["otp"] = otp
        session["temp_user"] = phone

        print("OTP:", otp)

        return redirect('/verify')

    return render_template("login.html")

# 🔐 VERIFY
@app.route('/verify', methods=['GET','POST'])
def verify():
    if request.method == "POST":
        if request.form["otp"] == session.get("otp"):
            session["user"] = session.get("temp_user")
            session["cart"] = {}
            return redirect('/')
        else:
            return "Wrong OTP ❌"

    return render_template("verify.html")

# ➕ ADD
@app.route('/add/<name>')
def add(name):
    cart = session.get("cart", {})
    cart[name] = cart.get(name, 0) + 1
    session["cart"] = cart
    return redirect('/')

# ➕ INCREASE
@app.route('/increase/<name>')
def increase(name):
    cart = session.get("cart", {})
    cart[name] += 1
    session["cart"] = cart
    return redirect('/')

# ➖ DECREASE
@app.route('/decrease/<name>')
def decrease(name):
    cart = session.get("cart", {})
    if cart[name] > 1:
        cart[name] -= 1
    else:
        del cart[name]
    session["cart"] = cart
    return redirect('/')

# ❌ REMOVE
@app.route('/remove/<name>')
def remove(name):
    cart = session.get("cart", {})
    if name in cart:
        del cart[name]
    session["cart"] = cart
    return redirect('/cart')

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
                items.append({
                    "name": name,
                    "price": veg["price"],
                    "qty": qty,
                    "total": t
                })

    return render_template("cart.html", items=items, total=total)

# 💳 CHECKOUT → PAYMENT
@app.route('/checkout')
def checkout():
    return redirect('/payment')

# 💳 PAYMENT
@app.route('/payment')
def payment():
    cart = session.get("cart", {})
    total = 0

    for name, qty in cart.items():
        for veg in vegetables:
            if veg["name"] == name:
                total += veg["price"] * qty

    return render_template("payment.html", total=total)

# 🎉 SUCCESS (SAVE ORDER)
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

# 📦 USER ORDERS
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

# 👤 PROFILE
@app.route('/profile', methods=['GET','POST'])
def profile():
    if request.method == "POST":
        session["name"] = request.form["name"]
        session["address"] = request.form["address"]

    return render_template(
        "profile.html",
        user=session.get("user"),
        name=session.get("name", ""),
        address=session.get("address", "")
    )

# 👑 ADMIN DASHBOARD
@app.route('/admin', methods=['GET','POST'])
def admin():
    conn = sqlite3.connect("database.db")
    cur = conn.cursor()

    if request.method == "POST":
        order_id = request.form["id"]
        status = request.form["status"]

        cur.execute("UPDATE orders SET status=? WHERE id=?", (status, order_id))
        conn.commit()

    # FETCH ORDERS
    cur.execute("SELECT id, username, item, quantity, total, status FROM orders")
    orders = cur.fetchall()

    # TOTAL ORDERS
    total_orders = len(orders)

    # TOTAL REVENUE
    cur.execute("SELECT SUM(total) FROM orders")
    total_revenue = cur.fetchone()[0] or 0

    conn.close()

    return render_template("admin.html",
                           orders=orders,
                           total_orders=total_orders,
                           total_revenue=total_revenue)

# 🚪 LOGOUT
@app.route('/logout')
def logout():
    session.clear()
    return redirect('/login')

# RUN
if __name__ == '__main__':
    app.run(debug=True)