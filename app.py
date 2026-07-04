from flask import Flask, render_template, request, redirect
import sqlite3

app = Flask(__name__)

# Helper function to connect to our SQLite database
def get_db_connection():
    # Using v2_database.db ensures a fresh, clean database slate on Render
    conn = sqlite3.connect('v2_database.db')
    conn.row_factory = sqlite3.Row
    return conn

# Automatically set up the student database table structure
def init_db():
    conn = get_db_connection()
    conn.execute('''
        CREATE TABLE IF NOT EXISTS students (
            adm_no TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            form TEXT NOT NULL,
            stream TEXT NOT NULL,
            gender TEXT NOT NULL,
            status TEXT DEFAULT 'Pending'
        )''')
    conn.commit()
    conn.close()

# This tells Flask to build the database schema before handling ANY incoming web request
@app.before_request
def initialize_on_startup():
    init_db()

# Route 0: Automatically redirect the bare home URL to the Admin page
@app.route('/')
def home():
    return redirect('/admin')

# Route 1: Displays the Admin dashboard
@app.route('/admin')
def admin_dashboard():
    conn = get_db_connection()
    students = conn.execute('SELECT * FROM students').fetchall()
    conn.close()
    return render_template('admin.html', students=students)

# Route 2: Receives data when the Admin clicks the "Add to Registry" button
@app.route('/admin/add_student', methods=['POST'])
def add_student():
    adm_no = request.form['adm_no']
    name = request.form['name']
    form = request.form['form']
    stream = request.form['stream']
    gender = request.form['gender']
    
    conn = get_db_connection()
    try:
        # Explicitly sets the default status to 'Pending' for new registrations
        conn.execute('INSERT INTO students (adm_no, name, form, stream, gender, status) VALUES (?, ?, ?, ?, ?, ?)',
                     (adm_no, name, form, stream, gender, 'Pending'))
        conn.commit()
    except sqlite3.IntegrityError:
        # Skips if admission number is a duplicate to prevent app failure
        pass
    conn.close()
    return redirect('/admin')

# Route 3: Ream Taker Dashboard (Displays all students and their statuses)
@app.route('/taker')
def ream_taker_dashboard():
    conn = get_db_connection()
    students = conn.execute('SELECT * FROM students').fetchall()
    conn.close()
    return render_template('ream_taker.html', students=students)

# Route 4: Action when clicking "Submitted" -> Changes status to Submitted
@app.route('/taker/submit/<adm_no>')
def submit_ream(adm_no):
    conn = get_db_connection()
    conn.execute("UPDATE students SET status = 'Submitted' WHERE adm_no = ?", (adm_no,))
    conn.commit()
    conn.close()
    return redirect('/taker')

# Route 5: Action when clicking "Undo" -> Changes status back to Pending
@app.route('/taker/undo/<adm_no>')
def undo_ream(adm_no):
    conn = get_db_connection()
    conn.execute("UPDATE students SET status = 'Pending' WHERE adm_no = ?", (adm_no,))
    conn.commit()
    conn.close()
    return redirect('/taker')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)