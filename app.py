from flask import Flask, render_template, request, redirect, session, jsonify
import sqlite3
import math

app = Flask(__name__)
app.secret_key = "secret123"

ADMIN_PHONE = "8838145515"

# ---------------- PRODUCTS ---------------- #
vegetables = [
    {"name": "Tomato", "price": 20},
    {"name": "Potato", "price": 30},
    {"name": "Onion", "price": 25},
    {"name": "Carrot", "price": 40},
    {"name": "Beans", "price": 40},
    {"name": "Beetroot", "price": 50},
    {"name": "Cabbage", "price": 60}
]

# ---------------- DATABASE ---------------- #
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

    cur.execute("""
    CREATE TABLE IF NOT EXISTS wallet (
        username TEXT PRIMARY KEY,
        balance INTEGER DEFAULT 0
    )
    """)

    conn.commit()
    conn.close()

init_db()

# ---------------- WALLET ---------------- #
def get_wallet(user):
    conn = sqlite3.connect("database.db")
    cur = conn.cursor()
    cur.execute("SELECT balance FROM wallet WHERE username=?", (user,))
    bal = cur.fetchone()
    conn.close()
    return bal[0] if bal else 0

# ---------------- LOGIN ---------------- #
@app.route('/login', methods=['GET','POST'])
def login():
    if request.method == 'POST':
        phone = request.form['phone']
        session['user'] = phone
        session['cart'] = {}

        conn = sqlite3.connect("database.db")
        cur = conn.cursor()
        cur.execute("INSERT OR IGNORE INTO wallet (username,balance) VALUES (?,0)", (phone,))
        conn.commit()
        conn.close()

        return redirect('/')
    return render_template("login.html")

# ---------------- HOME ---------------- #
@app.route('/')
def home():
    if 'user' not in session:
        return redirect('/login')

    return render_template("index.html",
        vegetables=vegetables,
        cart=session.get("cart", {}),
        cart_count=sum(session.get("cart", {}).values()),
        is_admin=(session.get("user") == ADMIN_PHONE)
    )

# ---------------- CART ---------------- #
@app.route('/add/<name>')
def add(name):
    cart = session.get("cart", {})
    cart[name] = cart.get(name, 0) + 1
    session["cart"] = cart
    return jsonify({"qty": cart[name], "cart_count": sum(cart.values())})

@app.route('/increase/<name>')
def increase(name):
    cart = session.get("cart", {})
    cart[name] += 1
    session["cart"] = cart
    return jsonify({"qty": cart[name], "cart_count": sum(cart.values())})

@app.route('/decrease/<name>')
def decrease(name):
    cart = session.get("cart", {})
    if cart[name] > 1:
        cart[name] -= 1
    else:
        cart.pop(name)
    session["cart"] = cart
    return jsonify({"qty": cart.get(name, 0), "cart_count": sum(cart.values())})

# ---------------- CART PAGE ---------------- #
@app.route('/cart')
def cart():
    cart = session.get("cart", {})
    items, total = [], 0

    for name, qty in cart.items():
        for v in vegetables:
            if v["name"] == name:
                t = v["price"] * qty
                total += t
                items.append({"name": name, "qty": qty, "price": v["price"], "total": t})

    return render_template("cart.html", items=items, total=total)

# ---------------- CHECKOUT ---------------- #
@app.route('/checkout')
def checkout():
    cart = session.get("cart", {})
    if not cart:
        return redirect('/')

    total = sum(v["price"] * qty for name, qty in cart.items() for v in vegetables if v["name"] == name)
    delivery = 30
    final_total = total + delivery

    return render_template("checkout.html",
        total=total,
        delivery=delivery,
        final_total=final_total,
        wallet_balance=get_wallet(session.get("user"))
    )

# ---------------- SUCCESS ---------------- #
@app.route('/success')
def success():
    user = session.get("user")
    cart = session.get("cart", {})

    conn = sqlite3.connect("database.db")
    cur = conn.cursor()

    for name, qty in cart.items():
        for v in vegetables:
            if v["name"] == name:
                cur.execute(
                    "INSERT INTO orders (username,item,quantity,total,status) VALUES (?,?,?,?,?)",
                    (user, name, qty, v["price"] * qty, "Paid")
                )

    conn.commit()
    conn.close()

    session["cart"] = {}
    return render_template("success.html")

# ---------------- WALLET ---------------- #
@app.route('/wallet')
def wallet():
    return render_template("wallet.html", balance=get_wallet(session.get("user")))

@app.route('/add_money', methods=['POST'])
def add_money():
    amount = int(request.form['amount'])
    user = session.get("user")

    conn = sqlite3.connect("database.db")
    cur = conn.cursor()
    cur.execute("UPDATE wallet SET balance = balance + ? WHERE username=?", (amount, user))
    conn.commit()
    conn.close()

    return redirect('/wallet')

# ---------------- PAY WALLET ---------------- #
@app.route('/pay_wallet')
def pay_wallet():
    user = session.get("user")
    cart = session.get("cart", {})

    total = sum(v["price"] * qty for name, qty in cart.items() for v in vegetables if v["name"] == name)
    final = total + 30

    balance = get_wallet(user)

    if balance < final:
        return "❌ Not enough balance"

    conn = sqlite3.connect("database.db")
    cur = conn.cursor()

    cur.execute("UPDATE wallet SET balance = balance - ? WHERE username=?", (final, user))

    for name, qty in cart.items():
        for v in vegetables:
            if v["name"] == name:
                cur.execute(
                    "INSERT INTO orders (username,item,quantity,total,status) VALUES (?,?,?,?,?)",
                    (user, name, qty, v["price"] * qty, "Paid")
                )

    conn.commit()
    conn.close()

    session["cart"] = {}
    return render_template("success.html")

# ---------------- ORDERS ---------------- #
@app.route('/orders')
def orders():
    conn = sqlite3.connect("database.db")
    cur = conn.cursor()
    cur.execute("SELECT item,quantity,total,status FROM orders WHERE username=?", (session.get("user"),))
    data = cur.fetchall()
    conn.close()
    return render_template("orders.html", orders=data)

# ---------------- PROFILE ---------------- #
@app.route('/profile')
def profile():
    return render_template("profile.html", user=session.get("user"))

# ---------------- ADMIN ---------------- #
@app.route('/admin')
def admin():

    if session.get("user") != ADMIN_PHONE:
        return "Access Denied ❌"

    conn = sqlite3.connect("database.db")
    cur = conn.cursor()

    cur.execute("SELECT * FROM orders")
    orders = cur.fetchall()

    cur.execute("SELECT SUM(total) FROM orders WHERE status='Paid' OR status='Delivered'")
    revenue = cur.fetchone()[0] or 0

    conn.close()

    return render_template("admin.html", orders=orders, revenue=revenue)

# ---------------- GRAPH DATA ---------------- #
@app.route('/admin_data')
def admin_data():

    if session.get("user") != ADMIN_PHONE:
        return jsonify({})

    conn = sqlite3.connect("database.db")
    cur = conn.cursor()

    cur.execute("SELECT item, SUM(quantity) FROM orders GROUP BY item")
    items = cur.fetchall()

    labels = [i[0] for i in items]
    values = [i[1] for i in items]

    cur.execute("SELECT SUM(total) FROM orders WHERE status='Paid' OR status='Delivered'")
    revenue = cur.fetchone()[0] or 0

    conn.close()

    return jsonify({
        "labels": labels,
        "values": values,
        "revenue": revenue
    })

# ---------------- LOGOUT ---------------- #
@app.route('/logout')
def logout():
    session.clear()
    return redirect('/login')

# ---------------- RUN ---------------- #
if __name__ == '__main__':
    app.run(debug=True)
