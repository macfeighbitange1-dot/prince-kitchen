from flask import Flask, render_template, request, redirect, url_for, session, jsonify
import sqlite3
import requests
from requests.auth import HTTPBasicAuth
from datetime import datetime, timedelta
import base64

app = Flask(__name__)
app.secret_key = 'prince_fast_foods_secure_key_2026' 

# --- MPESA CONFIG (Get these from developers.safaricom.co.ke) ---
MPESA_CONSUMER_KEY = 'YOUR_KEY_HERE'
MPESA_CONSUMER_SECRET = 'YOUR_SECRET_HERE'
MPESA_SHORTCODE = '174379' # This is the Sandbox Paybill
MPESA_PASSKEY = 'bfb279f9aa9bdbcf158e97dd71a467cd2e0c893059b10f78e6b72ada1ed2c919'

# --- DATABASE SETUP ---
def init_db():
    conn = sqlite3.connect('orders.db')
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS orders 
        (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, email TEXT, message TEXT, order_date TEXT)''')
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
        {"name": "Soft Chapati", "price": stock_map.get('Soft Chapati')['price'], "img": "chapati.jpg", "desc": "Hand-rolled.", "stock": stock_map.get('Soft Chapati')['stock']},
        {"name": "Classic Chips", "price": stock_map.get('Classic Chips')['price'], "img": "chips.jpg", "desc": "Crispy golden.", "stock": stock_map.get('Classic Chips')['stock']},
        {"name": "Swahili Pilau", "price": stock_map.get('Swahili Pilau')['price'], "img": "pilau.jpg", "desc": "Fragrant beef.", "stock": stock_map.get('Swahili Pilau')['stock']}
    ]
    juices = [
        {"name": "Fresh Mango (500ml)", "price": 50, "img": "mango.jpg", "desc": "Sun-ripened.", "stock": stock_map.get('Fresh Mango (500ml)')['stock']},
        {"name": "Passion Fruit (500ml)", "price": 50, "img": "passion.jpg", "desc": "Tangy delight.", "stock": stock_map.get('Passion Fruit (500ml)')['stock']},
        {"name": "Pineapple Juice (500ml)", "price": 50, "img": "pineapple.jpg", "desc": "Freshly squeezed.", "stock": stock_map.get('Pineapple Juice (500ml)')['stock']}
    ]
    return render_template('index.html', foods=foods, juices=juices)

# --- M-PESA PAYMENT ROUTE ---
@app.route('/pay', methods=['POST'])
def pay():
    phone = request.form.get('phone') # Expected: 2547XXXXXXXX
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
        "CallBackURL": "https://yourdomain.com/callback", # Change this to your Render URL later
        "AccountReference": "PrinceFastFoods",
        "TransactionDesc": "Food Payment"
    }

    headers = {"Authorization": f"Bearer {token}"}
    response = requests.post('https://sandbox.safaricom.co.ke/mpesa/stkpush/v1/processrequest', json=payload, headers=headers)
    
    return f"<h3>Processing Payment...</h3><p>Check your phone for the M-Pesa PIN prompt.</p><a href='/'>Return to Home</a>"

# --- EXISTING ADMIN ROUTES (KEEP THESE AS IS) ---
# ... [Include login, logout, view_orders, complete_order, update_stock from your previous code] ...

if __name__ == '__main__':
    app.run(debug=True, port=8080)
