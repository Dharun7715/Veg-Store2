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
    conn.commit()
    conn.close()

init_db()

# ---------------- DISTANCE FUNCTION ---------------- #
def get_distance(lat1, lon1, lat2, lon2):
    R = 6371  # Earth radius in KM

    lat1 = float(lat1)
    lon1 = float(lon1)
    lat2 = float(lat2)
    lon2 = float(lon2)

    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)

    a = (math.sin(dlat/2)**2 +
         math.cos(math.radians(lat1)) *
         math.cos(math.radians(lat2)) *
         math.sin(dlon/2)**2)

    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    return R * c

# ---------------- LOGIN ---------------- #
@app.route('/login', methods=['GET','POST'])
def login():
    if request.method == 'POST':
        phone = request.form['phone']
        session['temp_phone'] = phone
        session['otp'] = phone[-4:]  # simple OTP
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

# ---------------- CART (AJAX) ---------------- #
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
    items = []
    total = 0

    for name, qty in cart.items():
        for v in vegetables:
            if v["name"] == name:
                t = v["price"] * qty
                total += t
                items.append({
                    "name": name,
                    "qty": qty,
                    "price": v["price"],
                    "total": t
                })

    return render_template("cart.html", items=items, total=total)

# ---------------- ADDRESS ---------------- #
@app.route('/address', methods=['GET','POST'])
def address():
    if request.method == 'POST':
        lat = float(request.form['lat'])
        lng = float(request.form['lng'])
        addr = request.form.get('address')

        # Allow only Tharamangalam area
        if abs(lat - 11.6943) < 0.03 and abs(lng - 77.9680) < 0.03:
            session['lat'] = lat
            session['lng'] = lng
            session['address'] = addr
            return redirect('/checkout')
        else:
            return "<h2 style='color:red;text-align:center;'>❌ Only Tharamangalam Delivery</h2>"

    return render_template("address.html")

# ---------------- CHECKOUT ---------------- #
@app.route('/checkout')
def checkout():

    # Must select address
    if 'address' not in session:
        return redirect('/address')

    user_lat = session.get("lat")
    user_lng = session.get("lng")

    # Safety check
    if user_lat is None or user_lng is None:
        return redirect('/address')

    cart = session.get("cart", {})
    if not cart:
        return redirect('/')

    total = 0

    for name, qty in cart.items():
        for v in vegetables:
            if v["name"] == name:
                total += v["price"] * qty

    # Store location
    store_lat = 11.6943
    store_lng = 77.9680

    # Distance
    distance = get_distance(store_lat, store_lng, user_lat, user_lng)

    # Delivery charge
    if distance <= 1:
        delivery = 10
    elif distance <= 3:
        delivery = 30
    else:
        delivery = 60

    # Discount
    discount = 0
    if total > 200:
        discount = 20

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
                cur.execute(
                    "INSERT INTO orders (username,item,quantity,total,status) VALUES (?,?,?,?,?)",
                    (session.get("user"), name, qty, v["price"] * qty, "Pending")
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
