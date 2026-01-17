from flask import Flask, render_template, request, redirect, url_for, session, jsonify
import sqlite3
import requests
from requests.auth import HTTPBasicAuth
from datetime import datetime, timedelta
import base64
import json

app = Flask(__name__)
app.secret_key = 'prince_fast_foods_secure_key_2026' 

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
    
    items = [
        ('Soft Chapati', 50, 20), ('Classic Chips', 30, 100), ('Swahili Pilau', 20, 150), 
        ('Fresh Mango (500ml)', 15, 50), ('Passion Fruit (500ml)', 15, 50), ('Pineapple Juice (500ml)', 15, 50)
    ]
    cursor.executemany('INSERT OR IGNORE INTO inventory VALUES (?, ?, ?)', items)
    conn.commit()
    conn.close()

init_db()

# --- MPESA AUTH HELPER ---
def get_access_token():
    res = requests.get(
        'https://sandbox.safaricom.co.ke/oauth/v1/generate?grant_type=client_credentials',
        auth=HTTPBasicAuth(MPESA_CONSUMER_KEY, MPESA_CONSUMER_SECRET)
    )
    return res.json().get('access_token')

# --- MAIN ROUTES ---
@app.route('/')
def home():
    conn = sqlite3.connect('orders.db')
    cursor = conn.cursor()
    cursor.execute('SELECT item_name, stock_count, unit_price FROM inventory')
    data = cursor.fetchall()
    conn.close()
    stock_map = {row[0]: {"stock": row[1], "price": row[2]} for row in data}
    
    foods = [
        {"name": "Soft Chapati", "price": stock_map.get('Soft Chapati', {}).get('price', 20), "img": "chapati.jpg", "desc": "Hand-rolled.", "stock": stock_map.get('Soft Chapati', {}).get('stock', 0)},
        {"name": "Classic Chips", "price": stock_map.get('Classic Chips', {}).get('price', 100), "img": "chips.jpg", "desc": "Crispy golden.", "stock": stock_map.get('Classic Chips', {}).get('stock', 0)},
        {"name": "Swahili Pilau", "price": stock_map.get('Swahili Pilau', {}).get('price', 150), "img": "pilau.jpg", "desc": "Fragrant beef.", "stock": stock_map.get('Swahili Pilau', {}).get('stock', 0)}
    ]
    juices = [
        {"name": "Fresh Mango (500ml)", "price": 50, "img": "mango.jpg", "desc": "Sun-ripened.", "stock": stock_map.get('Fresh Mango (500ml)', {}).get('stock', 0)},
        {"name": "Passion Fruit (500ml)", "price": 50, "img": "passion.jpg", "desc": "Tangy delight.", "stock": stock_map.get('Passion Fruit (500ml)', {}).get('stock', 0)},
        {"name": "Pineapple Juice (500ml)", "price": 50, "img": "pineapple.jpg", "desc": "Freshly squeezed.", "stock": stock_map.get('Pineapple Juice (500ml)', {}).get('stock', 0)}
    ]
    return render_template('index.html', foods=foods, juices=juices)

@app.route('/pay', methods=['POST'])
def pay():
    phone = request.form.get('phone')
    amount = request.form.get('amount')
    
    token = get_access_token()
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
        "AccountReference": "PrinceFastFoods",
        "TransactionDesc": "Food Payment"
    }

    headers = {"Authorization": f"Bearer {token}"}
    requests.post('https://sandbox.safaricom.co.ke/mpesa/stkpush/v1/processrequest', json=payload, headers=headers)
    
    return f"""
    <div style="text-align:center; margin-top:100px; font-family:sans-serif;">
        <h2>Processing Payment...</h2>
        <p>Please check your phone for the M-Pesa PIN prompt.</p>
        <p>Once you enter your PIN, your order will be processed.</p>
        <a href="/" style="text-decoration:none; color:orange;">Back to Home</a>
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
        print("Payment Successful and logged!")
        
    return jsonify({"ResultCode": 0, "ResultDesc": "Accepted"})

# --- ADMIN ROUTES ---
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        if request.form.get('password') == 'Prince2026':
            session['logged_in'] = True
            return redirect(url_for('view_orders'))
        else:
            return "Invalid Password! <a href='/login'>Try again</a>"
    
    return '''
        <div style="text-align:center; margin-top:100px; font-family:sans-serif;">
            <h2>👑 Prince Admin Login</h2>
            <form method="post">
                <input type="password" name="password" placeholder="Password" style="padding:10px; border-radius:5px; border:1px solid #ccc;" required>
                <button type="submit" style="padding:10px 20px; background:orange; color:white; border:none; border-radius:5px; cursor:pointer;">Login</button>
            </form>
        </div>
    '''

@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    return redirect(url_for('home'))

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

if __name__ == '__main__':
    app.run(debug=True, port=8080)
