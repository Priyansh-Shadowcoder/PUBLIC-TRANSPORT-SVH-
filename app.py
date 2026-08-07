from flask import Flask, render_template, request, redirect, url_for, session, g
import sqlite3
import os
import subprocess
import os
import sys
from flask import jsonify

app = Flask(__name__)
app.secret_key = 'your_secure_secret_key_here'
DATABASE = 'traffic.db'


def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
        db.row_factory = sqlite3.Row
    return db

@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

def init_db():
    with app.app_context():
        db = get_db()
        cursor = db.cursor()
        # Initialize Core Tables
        cursor.executescript('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                role TEXT NOT NULL, -- 'user' or 'gov'
                name TEXT NOT NULL,
                email TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS routes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source TEXT NOT NULL,
                destination TEXT NOT NULL,
                distance_km REAL
            );
            CREATE TABLE IF NOT EXISTS buses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                route_id INTEGER,
                bus_number TEXT UNIQUE,
                capacity INTEGER,
                data_usage_mb REAL DEFAULT 0.0,
                status TEXT, -- 'On Time', 'Delayed', 'Disconnected'
                FOREIGN KEY (route_id) REFERENCES routes(id)
            );
            CREATE TABLE IF NOT EXISTS transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                pass_type TEXT, -- 'Seasonal', 'One-way'
                amount REAL,
                rating INTEGER,
                FOREIGN KEY (user_id) REFERENCES users(id)
            );
        ''')
        db.commit()

# --- ROUTES ---

@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        role = request.form['role']
        
        
        db = get_db()
        user = db.execute('SELECT * FROM users WHERE email = ? AND password = ? AND role = ?', 
                          (email, password, role)).fetchone()
        
        if user:
            session['user_id'] = user['id']
            session['role'] = user['role']
            if role == 'gov':
                return redirect(url_for('gov_dashboard'))
            return redirect(url_for('user_dashboard'))
        else:
            return "Invalid credentials or role mismatch.", 401
            
    return render_template('login.html')

@app.route('/user_dashboard')
def user_dashboard():
    if 'user_id' not in session or session['role'] != 'user':
        return redirect(url_for('login'))
        
    db = get_db()
    
    transactions = db.execute('SELECT * FROM transactions WHERE user_id = ?', (session['user_id'],)).fetchall()
    buses = db.execute('SELECT * FROM buses').fetchall()
    
    return render_template('user_dashboard.html', transactions=transactions, buses=buses)

@app.route('/api/buy_pass', methods=['POST'])
def buy_pass():
    
    if 'user_id' not in session or session.get('role') != 'user':
        return "Unauthorized", 403
    
    pass_type = request.form['pass_type']
    amount = float(request.form['amount'])
    
    db = get_db()
    
    db.execute('INSERT INTO transactions (user_id, pass_type, amount, rating) VALUES (?, ?, ?, ?)',
               (session['user_id'], pass_type, amount, 5))
    db.commit()
    
    
    return redirect(url_for('user_dashboard'))

@app.route('/gov_dashboard')
def gov_dashboard():
    if 'user_id' not in session or session.get('role') != 'gov':
        return redirect(url_for('login'))
        
    db = get_db()
    users = db.execute('SELECT * FROM users WHERE role = "user"').fetchall()
    buses = db.execute('SELECT * FROM buses').fetchall()
    
    sales_data = db.execute('''
        SELECT pass_type, COUNT(*) as count, SUM(amount) as revenue 
        FROM transactions 
        GROUP BY pass_type
    ''').fetchall()
    
    labels = [row['pass_type'] for row in sales_data]
    values = [row['count'] for row in sales_data]
    revenues = [row['revenue'] for row in sales_data]
    
    return render_template('gov_dashboard.html', users=users, buses=buses,labels=labels,values=values,revenues=revenues)

@app.route('/api/add_bus', methods=['POST'])
def add_bus():
    if session.get('role') != 'gov':
        return "Unauthorized", 403
    
    bus_num = request.form['bus_number']
    route_id = request.form['route_id']
    capacity = request.form['capacity']
    
    db = get_db()
    db.execute('INSERT INTO buses (route_id, bus_number, capacity, status) VALUES (?, ?, ?, ?)',
               (route_id, bus_num, capacity, 'On Time'))
    db.commit()
    return redirect(url_for('gov_dashboard'))

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))


@app.route('/api/route', methods=['POST'])
def get_route():
    data = request.json
    
    base_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Auto-detect binary based on OS (Windows uses .exe, Linux uses executable without extension)
    exe_name = 'router.exe' if os.name == 'nt' else 'router'
    exe_path = os.path.join(base_dir, exe_name)
    
    try:
        result = subprocess.run(
            [exe_path, str(data['src_lat']), str(data['src_lon']), str(data['dest_lat']), str(data['dest_lon'])],
            capture_output=True, text=True, check=True
        )
        
        distance = float(result.stdout.strip())
        return {"distance_km": round(distance, 2), "status": "success"}
        
    except FileNotFoundError:
        return {"error": f"Binary engine '{exe_name}' not found. Did you compile it?"}, 500
    except subprocess.CalledProcessError as e:
        return {"error": f"C++ Engine crashed: {e.stderr}"}, 500
    except Exception as e:
        return {"error": str(e)}, 500

@app.route('/api/incidents')
def check_incidents():
    db = get_db()
    
    issues = db.execute('SELECT bus_number, status FROM buses WHERE status != "On Time"').fetchall()
    
    alerts = [{"bus": row['bus_number'], "issue": row['status']} for row in issues]
    return jsonify(alerts)

@app.route('/signup', methods=['POST'])
def signup():
    name = request.form['name']
    email = request.form['email']
    password = request.form['password']
    role = request.form['role'] # 'user' or 'gov'
    
    db = get_db()
    
    try:
        # Insert the new user into the database
        db.execute('INSERT INTO users (role, name, email, password) VALUES (?, ?, ?, ?)',
                   (role, name, email, password))
        db.commit()
        
        # Fetch the newly created user to set up the session
        user = db.execute('SELECT * FROM users WHERE email = ?', (email,)).fetchone()
        
        session['user_id'] = user['id']
        session['role'] = user['role']
        
        # Route to the correct dashboard based on role
        if role == 'gov':
            return redirect(url_for('gov_dashboard'))
        return redirect(url_for('user_dashboard'))
        
    except sqlite3.IntegrityError:
        # This triggers if the email already exists in the database (UNIQUE constraint)
        return "Error: This email is already registered. Please go back and log in.", 400

@app.route('/api/edit_user', methods=['POST'])
def edit_user():
    if session.get('role') != 'gov':
        return "Unauthorized", 403
        
    user_id = request.form['user_id']
    name = request.form['name']
    email = request.form['email']
    
    db = get_db()
    db.execute('UPDATE users SET name = ?, email = ? WHERE id = ?', (name, email, user_id))
    db.commit()
    
    return redirect(url_for('gov_dashboard'))

@app.route('/api/delete_user/<int:user_id>', methods=['POST'])
def delete_user(user_id):
    if session.get('role') != 'gov':
        return "Unauthorized", 403
        
    db = get_db()
    
    # Optional: You may also want to delete the user's transactions 
    # to avoid foreign key constraint errors
    db.execute('DELETE FROM transactions WHERE user_id = ?', (user_id,))
    db.execute('DELETE FROM users WHERE id = ?', (user_id,))
    db.commit()
    
    return redirect(url_for('gov_dashboard'))

# Auto-initialize database on application startup for production deployment
if not os.path.exists(DATABASE):
    init_db()
    with app.app_context():
        db = get_db()
        db.execute('INSERT INTO users (role, name, email, password) VALUES (?, ?, ?, ?)', ('user', 'Test User', 'user@test.com', 'pass'))
        db.execute('INSERT INTO users (role, name, email, password) VALUES (?, ?, ?, ?)', ('gov', 'Admin', 'gov@test.com', 'pass'))
        db.commit()
if __name__ == '__main__':
    if not os.path.exists(DATABASE):
        init_db()
        with app.app_context():
            db = get_db()
            db.execute('INSERT INTO users (role, name, email, password) VALUES (?, ?, ?, ?)', ('user', 'Test User', 'user@test.com', 'pass'))
            db.execute('INSERT INTO users (role, name, email, password) VALUES (?, ?, ?, ?)', ('gov', 'Admin', 'gov@test.com', 'pass'))
            db.commit()
    app.run(debug=True, port=5000)