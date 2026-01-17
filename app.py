from flask import Flask, render_template, request, redirect, url_for, session, jsonify
import sqlite3
import requests
from requests.auth import HTTPBasicAuth
from datetime import datetime
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
    
    # Updated items list including new Sodas and Afya Juice
    items = [
        ('Soft Chapati', 50, 20), 
        ('Classic Chips', 30, 100), 
        ('Swahili Pilau', 20, 150), 
        ('Fresh Mango (500ml)', 15, 50), 
        ('Passion Fruit (500ml)', 15, 50), 
        ('Pineapple Juice (500ml)', 15, 50),
        ('Coca-Cola (500ml)', 25, 70),
        ('Afya Juice (500ml)', 20, 80),
        ('Coca-Cola (1L)', 15, 110)
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
    stock_map = {row[0]: {"stock": row[1], "price": row[2]} for row in data}
    
    foods = [
        {"name": "Soft Chapati", "price": stock_map.get('Soft Chapati', {}).get('price', 20), "img": "chapati.jpg", "stock": stock_map.get('Soft Chapati', {}).get('stock', 0)},
        {"name": "Classic Chips", "price": stock_map.get('Classic Chips', {}).get('price', 100), "img": "chips.jpg", "stock": stock_map.get('Classic Chips', {}).get('stock', 0)},
        {"name": "Swahili Pilau", "price": stock_map.get('Swahili Pilau', {}).get('price', 150), "img": "pilau.jpg", "stock": stock_map.get('Swahili Pilau', {}).get('stock', 0)}
    ]
    
    # Updated juices list to include Soda and Afya
    juices = [
        {"name": "Fresh Mango (500ml)", "price": 50, "img": "mango.jpg", "stock": stock_map.get('Fresh Mango (500ml)', {}).get('stock', 0)},
        {"name": "Passion Fruit (500ml)", "price": 50, "img": "passion.jpg", "stock": stock_map.get('Passion Fruit (500ml)', {}).get('stock', 0)},
        {"name": "Pineapple Juice (500ml)", "price": 50, "img": "pineapple.jpg", "stock": stock_map.get('Pineapple Juice (500ml)', {}).get('stock', 0)},
        {"name": "Afya Juice (500ml)", "price": 80, "img": "afya.jpg", "stock": stock_map.get('Afya Juice (500ml)', {}).get('stock', 0)},
        {"name": "Coca-Cola (500ml)", "price": 70, "img": "coke500.jpg", "stock": stock_map.get('Coca-Cola (500ml)', {}).get('stock', 0)},
        {"name": "Coca-Cola (1L)", "price": 110, "img": "coke1l.jpg", "stock": stock_map.get('Coca-Cola (1L)', {}).get('stock', 0)}
    ]
    return render_template('index.html', foods=foods, juices=juices)

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
        return f"<h3>Invalid Phone Number: {raw_phone}</h3><p>Please use 07xx, 01xx, or 254xx format.</p><a href='/'>Go Back</a>"

    try:
        amount = int(float(amount))
    except:
        return "Invalid Amount", 400

    token = get_access_token()
    if not token: return "Error Authenticating with M-Pesa", 500

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
        <h2 style="color:#e67e22;">Request Sent to {phone}!</h2>
        <p>Please check your phone for the M-Pesa PIN prompt.</p>
        <p>Once you pay, your order will be updated automatically.</p>
        <a href="/" style="text-decoration:none; color:#333; border:1px solid #ccc; padding:10px; border-radius:5px;">Return to Home</a>
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

@app.route('/complete/<int:order_id>', methods=['POST'])
def complete_order(order_id):
    if not session.get('logged_in'): return redirect(url_for('login'))
    conn = sqlite3.connect('orders.db')
    cursor = conn.cursor()
    cursor.execute("UPDATE orders SET status = 'Completed' WHERE id = ?", (order_id,))
    conn.commit()
    conn.close()
    return redirect(url_for('view_orders'))

@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    return redirect(url_for('home'))

if __name__ == '__main__':
    app.run(debug=True, port=8080)
