from flask import Flask, render_template, request, redirect, jsonify
import sqlite3
import math
import africastalking

app = Flask(__name__)

# --- AFRICA'S TALKING SMS CONFIGURATION ---
# Replace these with your real details from your Africa's Talking Dashboard
AT_USERNAME = "sandbox"  # Use "sandbox" for local testing
AT_API_KEY = "YOUR_AFRICAS_TALKING_API_KEY_HERE" 
PRINCIPAL_PHONE = "+254700000000" # Put the Principal's real mobile number here

# Initialize the SMS service
africastalking.initialize(AT_USERNAME, AT_API_KEY)
sms = africastalking.SMS

def get_db_connection():
    conn = sqlite3.connect('v2_database.db')
    conn.row_factory = sqlite3.Row
    return conn

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
    conn.execute('''
        CREATE TABLE IF NOT EXISTS allocations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            exam_name TEXT NOT NULL,
            form TEXT NOT NULL,
            stream TEXT NOT NULL,
            student_count INTEGER NOT NULL,
            pages_per_paper INTEGER NOT NULL,
            reams_allocated REAL NOT NULL,
            date_requested TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''')
    conn.commit()
    conn.close()

@app.before_request
def initialize_on_startup():
    init_db()

# --- FUNCTION TO CALCULATE METRICS & SEND SMS ---
def send_stock_alert_to_principal(exam_name, form, stream, reams_issued):
    conn = get_db_connection()
    
    # 1. Total Expected / Received (Total students who turned in their reams)
    received_row = conn.execute("SELECT COUNT(*) as total FROM students WHERE status = 'Submitted'").fetchone()
    total_received = received_row['total'] if received_row else 0
    
    # 2. Total Consumed (Sum of all exam allocations)
    consumed_row = conn.execute("SELECT SUM(reams_allocated) as total FROM allocations").fetchone()
    total_consumed = int(consumed_row['total']) if consumed_row['total'] is not None else 0
    
    # 3. Live Stock Remaining
    live_stock = total_received - total_consumed
    conn.close()
    
    # Construct the SMS message text layout
    message = (
        f"ReamTracker Alert!\n"
        f"Exam issued: {exam_name} (Form {form} {stream}) took {int(reams_issued)} Reams.\n\n"
        f"📋 Status Update:\n"
        f"- Total Received: {total_received} Reams\n"
        f"- Total Consumed: {total_consumed} Reams\n"
        f"- Live Stock: {live_stock} Reams remaining."
    )
    
    try:
        # Broadcast the text message live via Africa's Talking Gateway
        response = sms.send(message, [PRINCIPAL_PHONE])
        print("SMS Broadcast Successful:", response)
    except Exception as e:
        print("SMS Gateway Error (Likely Sandbox/Credentials mismatch):", e)

# ------------------ STANDARD ROUTING DESKS ------------------
@app.route('/')
def home():
    return redirect('/admin')

@app.route('/admin')
def admin_dashboard():
    conn = get_db_connection()
    students = conn.execute('SELECT * FROM students').fetchall()
    conn.close()
    return render_template('admin.html', students=students)

@app.route('/admin/add_student', methods=['POST'])
def add_student():
    adm_no = request.form['adm_no']
    name = request.form['name']
    form = request.form['form']
    stream = request.form['stream']
    gender = request.form['gender']
    conn = get_db_connection()
    try:
        conn.execute('INSERT INTO students (adm_no, name, form, stream, gender, status) VALUES (?, ?, ?, ?, ?, ?)',
                     (adm_no, name, form, stream, gender, 'Pending'))
        conn.commit()
    except sqlite3.IntegrityError:
        pass
    conn.close()
    return redirect('/admin')

@app.route('/taker')
def ream_taker_dashboard():
    conn = get_db_connection()
    students = conn.execute('SELECT * FROM students').fetchall()
    conn.close()
    return render_template('ream_taker.html', students=students)

@app.route('/taker/submit/<adm_no>')
def submit_ream(adm_no):
    conn = get_db_connection()
    conn.execute("UPDATE students SET status = 'Submitted' WHERE adm_no = ?", (adm_no,))
    conn.commit()
    conn.close()
    return redirect('/taker')

@app.route('/taker/undo/<adm_no>')
def undo_ream(adm_no):
    conn = get_db_connection()
    conn.execute("UPDATE students SET status = 'Pending' WHERE adm_no = ?", (adm_no,))
    conn.commit()
    conn.close()
    return redirect('/taker')

@app.route('/exam')
def exam_dashboard():
    conn = get_db_connection()
    forms = conn.execute('SELECT DISTINCT form FROM students ORDER BY form').fetchall()
    streams = conn.execute('SELECT DISTINCT stream FROM students ORDER BY stream').fetchall()
    allocations = conn.execute('SELECT * FROM allocations ORDER BY date_requested DESC').fetchall()
    conn.close()
    return render_template('exam.html', forms=forms, streams=streams, allocations=allocations)

@app.route('/api/get_student_count')
def get_student_count():
    form = request.args.get('form')
    stream = request.args.get('stream')
    conn = get_db_connection()
    count_row = conn.execute('SELECT COUNT(*) as total FROM students WHERE form = ? AND stream = ?', (form, stream)).fetchone()
    conn.close()
    return jsonify({'total': count_row['total'] if count_row else 0})

@app.route('/exam/allocate', methods=['POST'])
def allocate_paper_reams():
    exam_name = request.form['exam_name']
    form = request.form['form']
    stream = request.form['stream']
    student_count = int(request.form['student_count'])
    pages_per_paper = int(request.form['pages_per_paper'])
    
    total_sheets_needed = student_count * pages_per_paper
    reams_allocated = math.ceil(total_sheets_needed / 500)
    
    conn = get_db_connection()
    conn.execute('''
        INSERT INTO allocations (exam_name, form, stream, student_count, pages_per_paper, reams_allocated)
        VALUES (?, ?, ?, ?, ?, ?)''', (exam_name, form, stream, student_count, pages_per_paper, reams_allocated))
    conn.commit()
    conn.close()
    
    # Trigger the SMS Notification right after saving the database entry
    send_stock_alert_to_principal(exam_name, form, stream, reams_allocated)
    
    return redirect('/exam')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)