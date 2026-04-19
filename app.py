from flask import Flask, render_template, request, redirect, session, jsonify
import sqlite3
import math
from datetime import datetime

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

# ---------------- COUPONS ---------------- #
COUPONS = {
    "SAVE10": {"discount": 10, "min_order": 50, "expiry": "2026-12-31", "one_time": False},
    "SAVE50": {"discount": 50, "min_order": 200, "expiry": "2026-12-31", "one_time": True},
    "FREEDEL": {"discount": 0, "free_delivery": True, "min_order": 100, "expiry": "2026-12-31", "one_time": False}
}

USED_COUPONS = {}

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

# ---------------- DISTANCE ---------------- #
def get_distance(lat1, lon1, lat2, lon2):
    R = 6371
    lat1, lon1, lat2, lon2 = map(float, [lat1, lon1, lat2, lon2])

    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)

    a = (math.sin(dlat/2)**2 +
         math.cos(math.radians(lat1)) *
         math.cos(math.radians(lat2)) *
         math.sin(dlon/2)**2)

    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    return R * c

# ---------------- BEST COUPON ---------------- #
def get_best_coupon(total, user):
    best_discount = 0

    for code, c in COUPONS.items():

        if datetime.now().date() > datetime.strptime(c["expiry"], "%Y-%m-%d").date():
            continue

        if total < c.get("min_order", 0):
            continue

        if c.get("one_time"):
            if user in USED_COUPONS and code in USED_COUPONS[user]:
                continue

        discount = c.get("discount", 0)

        if discount > best_discount:
            best_discount = discount

    return best_discount

# ---------------- LOGIN ---------------- #
@app.route('/login', methods=['GET','POST'])
def login():
    if request.method == 'POST':
        phone = request.form['phone']
        session['temp_phone'] = phone
        session['otp'] = phone[-4:]
        return redirect('/otp')
    return render_template("login.html")

# ---------------- OTP ---------------- #
@app.route('/otp', methods=['GET','POST'])
def otp():
    if request.method == 'POST':
        if request.form['otp'] == session.get('otp'):
            user = session.get('temp_phone')
            session['user'] = user
            session['cart'] = {}

            conn = sqlite3.connect("database.db")
            cur = conn.cursor()
            cur.execute("INSERT OR IGNORE INTO wallet (username,balance) VALUES (?,?)", (user,0))
            conn.commit()
            conn.close()

            return redirect('/')
        else:
            return "❌ Wrong OTP"

    return render_template("verify.html", last4=session.get('otp'))

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

# ---------------- ADDRESS ---------------- #
@app.route('/address', methods=['GET','POST'])
def address():
    if request.method == 'POST':
        lat = float(request.form['lat'])
        lng = float(request.form['lng'])
        addr = request.form.get('address')

        if abs(lat - 11.6943) < 0.03 and abs(lng - 77.9680) < 0.03:
            session['lat'] = lat
            session['lng'] = lng
            session['address'] = addr
            return redirect('/checkout')
        else:
            return "❌ Only Tharamangalam Delivery"

    return render_template("address.html")

# ---------------- APPLY COUPON ---------------- #
@app.route('/apply_coupon', methods=['POST'])
def apply_coupon():
    code = request.form['coupon'].upper()
    session['coupon'] = code
    return redirect('/checkout')

# ---------------- CHECKOUT ---------------- #
@app.route('/checkout')
def checkout():

    if 'address' not in session:
        return redirect('/address')

    user = session.get("user")
    user_lat = session.get("lat")
    user_lng = session.get("lng")

    if user_lat is None:
        return redirect('/address')

    cart = session.get("cart", {})
    if not cart:
        return redirect('/')

    total = sum(v["price"] * qty for name, qty in cart.items() for v in vegetables if v["name"] == name)

    distance = get_distance(11.6943, 77.9680, user_lat, user_lng)

    delivery = 10 if distance <= 1 else 30 if distance <= 3 else 60

    discount = get_best_coupon(total, user)

    final_total = total + delivery - discount

    wallet_balance = get_wallet(user)

    return render_template("checkout.html",
        total=total,
        delivery=delivery,
        distance=round(distance,2),
        discount=discount,
        final_total=final_total,
        wallet_balance=wallet_balance
    )

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
    balance = get_wallet(user)

    if balance < 50:
        return "❌ Not enough balance"

    conn = sqlite3.connect("database.db")
    cur = conn.cursor()
    cur.execute("UPDATE wallet SET balance = balance - 50 WHERE username=?", (user,))
    conn.commit()
    conn.close()

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
    data = cur.fetchall()
    conn.close()

    return render_template("admin.html", orders=data)

# ---------------- LOGOUT ---------------- #
@app.route('/logout')
def logout():
    session.clear()
    return redirect('/login')

# ---------------- RUN ---------------- #
if __name__ == '__main__':
    app.run(debug=True)
