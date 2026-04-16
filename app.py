from flask import Flask, render_template, request, redirect, session
import sqlite3

app = Flask(__name__)
app.secret_key = "secret123"

ADMIN_PHONE = "8838145515"

# PRODUCTS
vegetables = [
    {"name": "Tomato", "price": 20},
    {"name": "Potato", "price": 30},
    {"name": "Onion", "price": 25},
    {"name": "Carrot", "price": 40},
    {"name": "Beans", "price": 40},
    {"name": "Beetroot", "price": 50},
    {"name": "Cabbage", "price": 60}
]

# DB INIT
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

# LOGIN → HOME
@app.route('/login', methods=['GET','POST'])
def login():
    if request.method == 'POST':
        phone = request.form['phone']
        session['user'] = phone
        session['cart'] = {}
        return redirect('/')   # ✅ HOME

    return render_template("login.html")

# HOME
@app.route('/')
def home():
    cart = session.get("cart", {})
    return render_template("index.html",
        vegetables=vegetables,
        cart=cart,
        cart_count=sum(cart.values()),
        is_admin=(session.get("user")==ADMIN_PHONE)
    )

# ADD CART
@app.route('/add/<name>')
def add(name):
    cart = session.get("cart", {})
    cart[name] = cart.get(name, 0) + 1
    session["cart"] = cart
    return redirect('/')

# INCREASE
@app.route('/increase/<name>')
def increase(name):
    cart = session.get("cart", {})
    cart[name] += 1
    session["cart"] = cart
    return redirect('/')

# DECREASE
@app.route('/decrease/<name>')
def decrease(name):
    cart = session.get("cart", {})
    if cart[name] > 1:
        cart[name] -= 1
    else:
        del cart[name]
    session["cart"] = cart
    return redirect('/')

# REMOVE
@app.route('/remove/<name>')
def remove(name):
    cart = session.get("cart", {})
    cart.pop(name, None)
    session["cart"] = cart
    return redirect('/cart')

# CART
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

# ADDRESS (MAP PAGE - OPTIONAL)
@app.route('/address', methods=['GET','POST'])
def address():
    if request.method == 'POST':
        lat = float(request.form['lat'])
        lng = float(request.form['lng'])

        # Tharamangalam restriction
        center_lat = 11.6943
        center_lng = 77.9680

        if abs(lat - center_lat) < 0.03 and abs(lng - center_lng) < 0.03:
            session['address'] = f"{lat},{lng}"
            return redirect('/payment')
        else:
            return "❌ Delivery only in Tharamangalam"

    return render_template("address.html")

# PAYMENT
@app.route('/payment')
@app.route('/checkout')
def payment():

    cart = session.get("cart", {})
    total = 0

    for name, qty in cart.items():
        for v in vegetables:
            if v["name"] == name:
                total += v["price"] * qty

    discount = 0

    if total >= 300:
        discount += 50

    # first order bonus
    conn = sqlite3.connect("database.db")
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM orders WHERE username=?", (session.get("user"),))
    count = cur.fetchone()[0]
    conn.close()

    if count == 0:
        discount += 100

    final_total = max(total - discount, 0)

    return render_template("payment.html",
        total=total,
        discount=discount,
        final_total=final_total
    )

# SUCCESS
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

# ORDERS
@app.route('/orders')
def orders():
    conn = sqlite3.connect("database.db")
    cur = conn.cursor()
    cur.execute("SELECT item,quantity,total,status FROM orders WHERE username=?", (session.get("user"),))
    data = cur.fetchall()
    conn.close()
    return render_template("orders.html", orders=data)

# PROFILE
@app.route('/profile')
def profile():
    return render_template("profile.html", user=session.get("user"))

# ADMIN
@app.route('/admin', methods=['GET','POST'])
def admin():
    if session.get("user") != ADMIN_PHONE:
        return "Access Denied"

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

# LOGOUT
@app.route('/logout')
def logout():
    session.clear()
    return redirect('/login')

if __name__ == '__main__':
    app.run(debug=True)
