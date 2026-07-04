from flask import Flask, render_template, request, redirect
import sqlite3

app = Flask(__name__)

# Helper function to connect to our SQLite database
def get_db_connection():
    conn = sqlite3.connect('database.db')
    conn.row_factory = sqlite3.Row
    return conn

# Automatically set up the student database table when the program starts
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

# Route 0: Automatically redirect the bare home URL to the Admin page
@app.route('/')
def home():
    return redirect('/admin')

# Route 1: Displays the dashboard with the form and side-by-side table
@app.route('/admin')
def admin_dashboard():
    conn = get_db_connection()
    students = conn.execute('SELECT * FROM students').fetchall()
    conn.close()
    return render_template('admin.html', students=students)

# Route 2: Receives data when the "Add to Registry" button is clicked
@app.route('/admin/add_student', methods=['POST'])
def add_student():
    adm_no = request.form['adm_no']
    name = request.form['name']
    form = request.form['form']
    stream = request.form['stream']
    gender = request.form['gender']
    status TEXT DEFAULT 'Pending'
    
    conn = get_db_connection()
    try:
        conn.execute('INSERT INTO students (adm_no, name, form, stream, gender) VALUES (?, ?, ?, ?, ?)',
                     (adm_no, name, form, stream, gender))
        conn.commit()
    except sqlite3.IntegrityError:
        # Prevents crashing if the Admission Number already exists
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

# Route 4: Action when the Ream Taker clicks "Submitted"
@app.route('/taker/submit/<adm_no>')
def submit_ream(adm_no):
    conn = get_db_connection()
    conn.execute("UPDATE students SET status = 'Submitted' WHERE adm_no = ?", (adm_no,))
    conn.commit()
    conn.close()
    return redirect('/taker')

if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=5000)