from flask import Flask, render_template, request, redirect, url_for, session
import sqlite3
from datetime import datetime, timedelta

app = Flask(__name__)
app.secret_key = 'prince_fast_foods_secure_key_2026' 

# --- DATABASE SETUP ---
def init_db():
    conn = sqlite3.connect('orders.db')
    cursor = conn.cursor()
    # Active Orders
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL,
            message TEXT NOT NULL,
            order_date TEXT
        )
    ''')
    # Inventory Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS inventory (
            item_name TEXT PRIMARY KEY,
            stock_count INTEGER DEFAULT 0,
            unit_price INTEGER DEFAULT 0
        )
    ''')
    # Sales Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS sales (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            amount INTEGER NOT NULL,
            sale_date TEXT NOT NULL
        )
    ''')
    
    items = [
        ('Soft Chapati', 50, 20), 
        ('Classic Chips', 30, 100), 
        ('Swahili Pilau', 20, 150), 
        ('Fresh Mango (500ml)', 15, 50), 
        ('Passion Fruit (500ml)', 15, 50), 
        ('Pineapple Juice (500ml)', 15, 50)
    ]
    cursor.executemany('INSERT OR IGNORE INTO inventory VALUES (?, ?, ?)', items)
    conn.commit()
    conn.close()

init_db()

# --- LOGIN PROTECTION ---
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        password = request.form.get('password')
        if password == 'Prince2026': 
            session['logged_in'] = True
            return redirect(url_for('view_orders'))
        else:
            return "Invalid Password! <a href='/login'>Try again</a>"
    
    return '''
        <div style="text-align:center; margin-top:100px; font-family:sans-serif;">
            <h2>👑 Prince Admin Login</h2>
            <form method="post">
                <input type="password" name="password" placeholder="Admin Password" style="padding:10px;" required>
                <button type="submit" style="padding:10px; background:#ffc107; border:none; cursor:pointer;">Login</button>
            </form>
            <br><a href="/">Back to Website</a>
        </div>
    '''

@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    return redirect(url_for('home'))

# --- MAIN ROUTES ---
@app.route('/')
def home():
    conn = sqlite3.connect('orders.db')
    cursor = conn.cursor()
    cursor.execute('SELECT item_name, stock_count FROM inventory')
    stock_data = {row[0]: row[1] for row in cursor.fetchall()}
    conn.close()

    foods = [
        {"name": "Soft Chapati", "price": "Ksh 20", "img": "chapati.jpg", "desc": "Hand-rolled.", "stock": stock_data.get('Soft Chapati', 0)},
        {"name": "Classic Chips", "price": "Ksh 100", "img": "chips.jpg", "desc": "Crispy golden.", "stock": stock_data.get('Classic Chips', 0)},
        {"name": "Swahili Pilau", "price": "Ksh 150", "img": "pilau.jpg", "desc": "Fragrant beef.", "stock": stock_data.get('Swahili Pilau', 0)}
    ]
    
    juices = [
        {"name": "Fresh Mango (500ml)", "price": "Ksh 50", "img": "mango.jpg", "desc": "Sun-ripened.", "stock": stock_data.get('Fresh Mango (500ml)', 0)},
        {"name": "Passion Fruit (500ml)", "price": "Ksh 50", "img": "passion.jpg", "desc": "Tangy delight.", "stock": stock_data.get('Passion Fruit (500ml)', 0)},
        {"name": "Pineapple Juice (500ml)", "price": "Ksh 50", "img": "pineapple.jpg", "desc": "Freshly squeezed.", "stock": stock_data.get('Pineapple Juice (500ml)', 0)}
    ]
    
    return render_template('index.html', foods=foods, juices=juices)

@app.route('/contact', methods=['POST'])
def contact():
    name = request.form.get('name')
    email = request.form.get('email')
    message = request.form.get('message')
    date_sent = datetime.now().strftime("%Y-%m-%d %I:%M %p") 
    
    conn = sqlite3.connect('orders.db')
    cursor = conn.cursor()
    cursor.execute('INSERT INTO orders (name, email, message, order_date) VALUES (?, ?, ?, ?)', 
                   (name, email, message, date_sent))
    conn.commit()
    conn.close()
    return render_template('success.html', name=name)

# --- ADMIN ROUTES ---
@app.route('/admin/orders')
def view_orders():
    if not session.get('logged_in'):
        return redirect(url_for('login'))

    conn = sqlite3.connect('orders.db')
    cursor = conn.cursor()
    
    # 1. Fetch Active Orders
    cursor.execute('SELECT id, name, email, message, order_date FROM orders ORDER BY id DESC')
    all_orders = cursor.fetchall()
    
    # 2. Fetch Inventory
    cursor.execute('SELECT * FROM inventory')
    inventory_levels = cursor.fetchall()

    # 3. Calculate Daily Total
    today_str = datetime.now().strftime("%Y-%m-%d")
    cursor.execute('SELECT SUM(amount) FROM sales WHERE sale_date = ?', (today_str,))
    daily_total = cursor.fetchone()[0] or 0

    # 4. NEW: Calculate Weekly Stats for the Chart
    weekly_stats = []
    # Loop back through the last 7 days
    for i in range(6, -1, -1):
        day_date = (datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d")
        cursor.execute('SELECT SUM(amount) FROM sales WHERE sale_date = ?', (day_date,))
        val = cursor.fetchone()[0] or 0
        weekly_stats.append(val)
    
    weekly_total = sum(weekly_stats)
    
    conn.close()
    return render_template('admin.html', 
                           orders=all_orders, 
                           inventory=inventory_levels, 
                           daily_total=daily_total,
                           weekly_stats=weekly_stats, 
                           weekly_total=weekly_total)

@app.route('/complete/<int:order_id>', methods=['POST'])
def complete_order(order_id):
    if not session.get('logged_in'):
        return redirect(url_for('login'))
        
    amount = request.form.get('amount', 0)
    today = datetime.now().strftime("%Y-%m-%d")

    conn = sqlite3.connect('orders.db')
    cursor = conn.cursor()
    cursor.execute('INSERT INTO sales (amount, sale_date) VALUES (?, ?)', (amount, today))
    cursor.execute('DELETE FROM orders WHERE id = ?', (order_id,))
    conn.commit()
    conn.close()
    return redirect(url_for('view_orders'))

@app.route('/admin/update_stock', methods=['POST'])
def update_stock():
    if not session.get('logged_in'):
        return redirect(url_for('login'))

    item_name = request.form.get('item_name')
    new_count = request.form.get('new_count')
    
    conn = sqlite3.connect('orders.db')
    cursor = conn.cursor()
    cursor.execute('UPDATE inventory SET stock_count = ? WHERE item_name = ?', (new_count, item_name))
    conn.commit()
    conn.close()
    return redirect(url_for('view_orders'))

@app.route('/delete/<int:order_id>')
def delete_order(order_id):
    if not session.get('logged_in'):
        return redirect(url_for('login'))

    conn = sqlite3.connect('orders.db')
    cursor = conn.cursor()
    cursor.execute('DELETE FROM orders WHERE id = ?', (order_id,))
    conn.commit()
    conn.close()
    return redirect(url_for('view_orders'))

if __name__ == '__main__':
    app.run(debug=True, port=8080)