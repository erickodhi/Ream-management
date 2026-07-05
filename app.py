from flask import Flask, render_template, request, redirect
import sqlite3

app = Flask(__name__)

def get_db_connection():
    # Using a brand new database file name for our fresh architecture start
    conn = sqlite3.connect('ream_yearly_v1.db')
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    # Creates the global system configuration table for Term/Year setup
    conn.execute('''
        CREATE TABLE IF NOT EXISTS system_config (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            current_term TEXT NOT NULL,
            current_year TEXT NOT NULL
        )''')
    
    # Creates the student table tracking individual terms and summary status
    conn.execute('''
        CREATE TABLE IF NOT EXISTS students (
            adm_no TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            grade TEXT NOT NULL,
            stream TEXT NOT NULL,
            gender TEXT NOT NULL,
            term1 TEXT DEFAULT 'Pending',
            term2 TEXT DEFAULT 'Pending',
            term3 TEXT DEFAULT 'Pending',
            summary_status TEXT DEFAULT '3 Reams Owed'
        )''')
    
    # Set default term configuration if table is empty
    config_check = conn.execute('SELECT COUNT(*) as count FROM system_config').fetchone()
    if config_check['count'] == 0:
        conn.execute("INSERT INTO system_config (current_term, current_year) VALUES ('Term 1', '2026')")
        
    conn.commit()
    conn.close()

@app.before_request
def initialize_on_startup():
    init_db()

# Helper function to recalculate how many reams are remaining for a student
def update_student_summary(conn, adm_no):
    student = conn.execute('SELECT term1, term2, term3 FROM students WHERE adm_no = ?', (adm_no,)).fetchone()
    if student:
        pending_count = 0
        if student['term1'] == 'Pending': pending_count += 1
        if student['term2'] == 'Pending': pending_count += 1
        if student['term3'] == 'Pending': pending_count += 1
        
        summary = "Cleared ✅" if pending_count == 0 else f"{pending_count} Reams Owed"
        conn.execute('UPDATE students SET summary_status = ? WHERE adm_no = ?', (summary, adm_no))

@app.route('/')
def home():
    return redirect('/admin')

# ------------------ ADMIN DESK ------------------
@app.route('/admin')
def admin_dashboard():
    conn = get_db_connection()
    config = conn.execute('SELECT * FROM system_config LIMIT 1').fetchone()
    students = conn.execute('SELECT * FROM students').fetchall()
    conn.close()
    return render_template('admin.html', config=config, students=students)

@app.route('/admin/update_config', methods=['POST'])
def update_config():
    term = request.form['current_term']
    year = request.form['current_year']
    conn = get_db_connection()
    conn.execute('UPDATE system_config SET current_term = ?, current_year = ? WHERE id = 1', (term, year))
    conn.commit()
    conn.close()
    return redirect('/admin')

@app.route('/admin/add_student', methods=['POST'])
def add_student():
    adm_no = request.form['adm_no']
    name = request.form['name']
    grade = request.form['grade']
    stream = request.form['stream']
    gender = request.form['gender']
    
    conn = get_db_connection()
    try:
        conn.execute('''INSERT INTO students (adm_no, name, grade, stream, gender) 
                        VALUES (?, ?, ?, ?, ?)''', (adm_no, name, grade, stream, gender))
        conn.commit()
    except sqlite3.IntegrityError:
        pass
    conn.close()
    return redirect('/admin')

# ------------------ REAM TAKER DESK ------------------
@app.route('/taker')
def ream_taker_dashboard():
    conn = get_db_connection()
    config = conn.execute('SELECT * FROM system_config LIMIT 1').fetchone()
    students = conn.execute('SELECT * FROM students').fetchall()
    conn.close()
    return render_template('ream_taker.html', config=config, students=students)

@app.route('/taker/submit/<adm_no>')
def taker_submit(adm_no):
    conn = get_db_connection()
    config = conn.execute('SELECT current_term FROM system_config LIMIT 1').fetchone()
    current_term = config['current_term'].replace(" ", "").lower() # turns "Term 1" into "term1"
    
    conn.execute(f"UPDATE students SET {current_term} = 'Submitted' WHERE adm_no = ?", (adm_no,))
    update_student_summary(conn, adm_no)
    conn.commit()
    conn.close()
    return redirect('/taker')

@app.route('/taker/undo/<adm_no>')
def taker_undo(adm_no):
    conn = get_db_connection()
    config = conn.execute('SELECT current_term FROM system_config LIMIT 1').fetchone()
    current_term = config['current_term'].replace(" ", "").lower()
    
    conn.execute(f"UPDATE students SET {current_term} = 'Pending' WHERE adm_no = ?", (adm_no,))
    update_student_summary(conn, adm_no)
    conn.commit()
    conn.close()
    return redirect('/taker')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)