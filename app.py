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
    conn.commit()
    conn.close()

init_db()

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
    best_code = None

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
            best_code = code

    return best_code, best_discount

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
            session['user'] = session.get('temp_phone')
            session['cart'] = {}
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
    user = session.get("user")

    if code not in COUPONS:
        session['coupon'] = None
        return redirect('/checkout')

    c = COUPONS[code]

    if datetime.now().date() > datetime.strptime(c["expiry"], "%Y-%m-%d").date():
        return "❌ Coupon expired"

    if c.get("one_time"):
        if user in USED_COUPONS and code in USED_COUPONS[user]:
            return "❌ Already used"

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

    if user_lat is None or user_lng is None:
        return redirect('/address')

    cart = session.get("cart", {})
    if not cart:
        return redirect('/')

    total = sum(v["price"] * qty for name, qty in cart.items() for v in vegetables if v["name"] == name)

    store_lat, store_lng = 11.6943, 77.9680
    distance = get_distance(store_lat, store_lng, user_lat, user_lng)

    delivery = 10 if distance <= 1 else 30 if distance <= 3 else 60

    coupon_code = session.get("coupon")
    discount = 0

    if not coupon_code:
        best_code, best_discount = get_best_coupon(total, user)
        if best_code:
            discount = best_discount
    else:
        c = COUPONS.get(coupon_code)
        if c and total >= c.get("min_order", 0):
            discount = c.get("discount", 0)
            if c.get("free_delivery"):
                delivery = 0

    final_total = total + delivery - discount

    return render_template("checkout.html",
        total=total,
        delivery=delivery,
        distance=round(distance,2),
        discount=discount,
        final_total=final_total
    )

# ---------------- SUCCESS ---------------- #
@app.route('/success')
def success():
    cart = session.get("cart", {})
    if not cart:
        return "Cart empty ❌"

    conn = sqlite3.connect("database.db")
    cur = conn.cursor()

    for name, qty in cart.items():
        for v in vegetables:
            if v["name"] == name:
                cur.execute("INSERT INTO orders (username,item,quantity,total,status) VALUES (?,?,?,?,?)",
                            (session.get("user"), name, qty, v["price"] * qty, "Pending"))

    conn.commit()
    conn.close()

    # mark coupon used
    coupon = session.get("coupon")
    user = session.get("user")

    if coupon:
        USED_COUPONS.setdefault(user, []).append(coupon)

    session["cart"] = {}
    session["coupon"] = None

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
@app.route('/admin', methods=['GET','POST'])
def admin():
    if session.get("user") != ADMIN_PHONE:
        return "Access Denied ❌"

    conn = sqlite3.connect("database.db")
    cur = conn.cursor()

    if request.method == 'POST':
        cur.execute("UPDATE orders SET status=? WHERE id=?", (request.form['status'], request.form['id']))
        conn.commit()

    cur.execute("SELECT * FROM orders")
    data = cur.fetchall()

    return render_template("admin.html",
        orders=data,
        total_orders=len(data),
        total_revenue=sum(i[4] for i in data)
    )

# ---------------- LOGOUT ---------------- #
@app.route('/logout')
def logout():
    session.clear()
    return redirect('/login')

# ---------------- RUN ---------------- #
if __name__ == '__main__':
    app.run(debug=True)
