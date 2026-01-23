from flask import Flask, render_template, request, redirect, url_for, session, jsonify
import sqlite3
import requests
from requests.auth import HTTPBasicAuth
from datetime import datetime
import base64
import json

app = Flask(__name__)
app.secret_key = 'spring_on_the_go_secure_key_2026' 

# --- MPESA CONFIG ---
MPESA_CONSUMER_KEY = 'tebgdbs5GY2cAgzQo8S4FbAtGEfJoFGvRtGLGFApdYfAJLqm'
MPESA_CONSUMER_SECRET = 'fgqRJ6Qi0AAjsfkNW6dD39Vs7EGhgzSGG9Rz5dgKxWHbP5KCkhqb43ICBg5jAgzb'
MPESA_SHORTCODE = '174379'
MPESA_PASSKEY = 'bfb279f9aa9bdbcf158e97dd71a467cd2e0c893059b10f78e6b72ada1ed2c919'

# --- DATABASE SETUP ---
def init_db():
    conn = sqlite3.connect('orders.db')
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS orders 
        (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, email TEXT, message TEXT, order_date TEXT, status TEXT DEFAULT 'Pending')''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS inventory 
        (item_name TEXT PRIMARY KEY, stock_count INTEGER DEFAULT 0, unit_price INTEGER DEFAULT 0)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS sales 
        (id INTEGER PRIMARY KEY AUTOINCREMENT, amount INTEGER, sale_date TEXT)''')
    
    # Rebranded Inventory: Convenience Store Edition
    # Format: (Item Name, Initial Stock, Price)
    items = [
        # Snacks & Hot Beverages
        ('Hot Coffee / Tea', 50, 100), 
        ('Freshly Baked Pie', 20, 150), 
        ('Assorted Crisps', 40, 50), 
        # Cold Drinks
        ('Coca-Cola (500ml)', 25, 70),
        ('Coca-Cola (1L)', 15, 110),
        ('Afya Juice (500ml)', 20, 80),
        ('Fresh Mango Juice', 15, 120),
        # Household & Convenience
        ('Milk (500ml)', 30, 65),
        ('Loaf of Bread', 20, 65),
        ('Detergent Packet', 15, 250)
    ]
    cursor.executemany('INSERT OR IGNORE INTO inventory VALUES (?, ?, ?)', items)
    conn.commit()
    conn.close()

init_db()

# --- MPESA AUTH HELPER ---
def get_access_token():
    try:
        res = requests.get(
            'https://sandbox.safaricom.co.ke/oauth/v1/generate?grant_type=client_credentials',
            auth=HTTPBasicAuth(MPESA_CONSUMER_KEY, MPESA_CONSUMER_SECRET)
        )
        return res.json().get('access_token')
    except Exception as e:
        print(f"Error getting token: {e}")
        return None

# --- MAIN ROUTES ---
@app.route('/')
def home():
    conn = sqlite3.connect('orders.db')
    cursor = conn.cursor()
    cursor.execute('SELECT item_name, stock_count, unit_price FROM inventory')
    data = cursor.fetchall()
    conn.close()
    
    # Map database values to UI
    stock_map = {row[0]: {"stock": row[1], "price": row[2]} for row in data}
    
    # Logic for Snacks & Essentials
    snacks_essentials = [
        {"name": "Hot Coffee / Tea", "price": stock_map.get('Hot Coffee / Tea', {}).get('price', 100), "img": "coffee.jpg", "stock": stock_map.get('Hot Coffee / Tea', {}).get('stock', 0)},
        {"name": "Freshly Baked Pie", "price": stock_map.get('Freshly Baked Pie', {}).get('price', 150), "img": "pie.jpg", "stock": stock_map.get('Freshly Baked Pie', {}).get('stock', 0)},
        {"name": "Assorted Crisps", "price": stock_map.get('Assorted Crisps', {}).get('price', 50), "img": "snacks.jpg", "stock": stock_map.get('Assorted Crisps', {}).get('stock', 0)},
        {"name": "Loaf of Bread", "price": stock_map.get('Loaf of Bread', {}).get('price', 65), "img": "bread.jpg", "stock": stock_map.get('Loaf of Bread', {}).get('stock', 0)}
    ]
    
    # Logic for Cold Drinks & Juices
    drinks = [
        {"name": "Coca-Cola (500ml)", "price": 70, "img": "coke500.jpg", "stock": stock_map.get('Coca-Cola (500ml)', {}).get('stock', 0)},
        {"name": "Coca-Cola (1L)", "price": 110, "img": "coke1l.jpg", "stock": stock_map.get('Coca-Cola (1L)', {}).get('stock', 0)},
        {"name": "Afya Juice (500ml)", "price": 80, "img": "afya.jpg", "stock": stock_map.get('Afya Juice (500ml)', {}).get('stock', 0)},
        {"name": "Milk (500ml)", "price": 65, "img": "milk.jpg", "stock": stock_map.get('Milk (500ml)', {}).get('stock', 0)}
    ]
    
    return render_template('index.html', snacks=snacks_essentials, drinks=drinks)

@app.route('/pay', methods=['POST'])
def pay():
    raw_phone = request.form.get('phone').strip()
    amount = request.form.get('amount')
    
    phone = raw_phone.replace("+", "").replace(" ", "")
    if phone.startswith('0'):
        phone = '254' + phone[1:]
    elif len(phone) == 9 and (phone.startswith('7') or phone.startswith('1')):
        phone = '254' + phone
    
    if not (phone.startswith('254') and len(phone) == 12):
        return f"<h3>Invalid Phone: {raw_phone}</h3><p>Use 07xx, 01xx, or 254xx format.</p><a href='/'>Go Back</a>"

    try:
        amount = int(float(amount))
    except:
        return "Invalid Amount", 400

    token = get_access_token()
    if not token: return "Authentication Failed", 500

    timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
    password = base64.b64encode((MPESA_SHORTCODE + MPESA_PASSKEY + timestamp).encode()).decode()

    payload = {
        "BusinessShortCode": MPESA_SHORTCODE,
        "Password": password,
        "Timestamp": timestamp,
        "TransactionType": "CustomerPayBillOnline",
        "Amount": amount,
        "PartyA": phone,
        "PartyB": MPESA_SHORTCODE,
        "PhoneNumber": phone,
        "CallBackURL": "https://prince-kitchen.onrender.com/callback",
        "AccountReference": "SpringOnTheGo",
        "TransactionDesc": "Convenience Store Payment"
    }

    headers = {"Authorization": f"Bearer {token}"}
    requests.post('https://sandbox.safaricom.co.ke/mpesa/stkpush/v1/processrequest', json=payload, headers=headers)
    
    return f"""
    <div style="text-align:center; margin-top:100px; font-family:sans-serif; background:#f8f9fa; padding:20px;">
        <h2 style="color:#2ecc71;">Spring on the Go: Request Sent!</h2>
        <p>Confirm the M-Pesa prompt on your phone (254***{phone[-3:]}).</p>
        <a href="/" style="text-decoration:none; background:#34495e; color:white; padding:10px 20px; border-radius:5px;">Return to Shop</a>
    </div>
    """

@app.route('/callback', methods=['POST'])
def mpesa_callback():
    data = request.get_json()
    result_code = data['Body']['stkCallback']['ResultCode']
    if result_code == 0:
        amount = data['Body']['stkCallback']['CallbackMetadata']['Item'][0]['Value']
        today = datetime.now().strftime("%Y-%m-%d")
        conn = sqlite3.connect('orders.db')
        cursor = conn.cursor()
        cursor.execute('INSERT INTO sales (amount, sale_date) VALUES (?, ?)', (amount, today))
        conn.commit()
        conn.close()
    return jsonify({"ResultCode": 0, "ResultDesc": "Accepted"})

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        if request.form.get('password') == 'Prince2026':
            session['logged_in'] = True
            return redirect(url_for('view_orders'))
        return "Invalid! <a href='/login'>Try again</a>"
    return '''
        <div style="text-align:center; margin-top:100px; font-family:sans-serif;">
            <h2>🏪 Spring Admin Portal</h2>
            <form method="post">
                <input type="password" name="password" placeholder="Admin Key" style="padding:10px; border-radius:5px;" required>
                <button type="submit" style="padding:10px 20px; background:#2c3e50; color:white; border:none; border-radius:5px;">Unlock</button>
            </form>
        </div>
    '''

@app.route('/admin/orders')
def view_orders():
    if not session.get('logged_in'): return redirect(url_for('login'))
    conn = sqlite3.connect('orders.db')
    cursor = conn.cursor()
    cursor.execute('SELECT id, name, email, message, order_date, status FROM orders ORDER BY id DESC')
    all_orders = cursor.fetchall()
    cursor.execute('SELECT * FROM inventory')
    inventory = cursor.fetchall()
    today = datetime.now().strftime("%Y-%m-%d")
    cursor.execute('SELECT SUM(amount) FROM sales WHERE sale_date = ?', (today,))
    daily_total = cursor.fetchone()[0] or 0
    conn.close()
    return render_template('admin.html', orders=all_orders, inventory=inventory, daily_total=daily_total)

@app.route('/admin/update_stock', methods=['POST'])
def update_stock():
    if not session.get('logged_in'): return redirect(url_for('login'))
    item_name = request.form.get('item_name')
    new_count = request.form.get('new_count')
    conn = sqlite3.connect('orders.db')
    cursor = conn.cursor()
    cursor.execute('UPDATE inventory SET stock_count = ? WHERE item_name = ?', (new_count, item_name))
    conn.commit()
    conn.close()
    return redirect(url_for('view_orders'))

@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    return redirect(url_for('home'))

if __name__ == '__main__':
    app.run(debug=True, port=8080)