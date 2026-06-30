from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import check_password_hash
from functools import wraps
from flask import abort


from flask import Flask, render_template, request, redirect, url_for, flash, abort
import sqlite3
import math
import africastalking  # 1. Import the SMS module smoothly
import csv
import sqlite3
from io import TextIOWrapper

app = Flask(__name__)

# Enable session security
app.secret_key = "secure_ream_key_123" 

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'  # Sends unlogged-in users back to login page

class User(UserMixin):
    def __init__(self, id, username, role):
        self.id = id
        self.username = username
        self.role = role

@login_manager.user_loader
def load_user(user_id):
    conn = get_db_connection()
    user = conn.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()
    conn.close()
    if user:
        return User(user['id'], user['username'], user['role'])
    return None

def role_required(allowed_roles):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                return redirect(url_for('login'))
            if current_user.role not in allowed_roles:
                abort(403)
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def get_db_connection():
    conn = sqlite3.connect('ream_management.db')
    conn.row_factory = sqlite3.Row
    
    # Auto-create the users table if it's missing on the server
    conn.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL
        )
    ''')
    conn.commit()
    return conn

def init_db():
    conn = get_db_connection()
    conn.execute('''
        CREATE TABLE IF NOT EXISTS system_config (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            current_term TEXT NOT NULL,
            current_year TEXT NOT NULL
        )''')
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
    conn.execute('''
        CREATE TABLE IF NOT EXISTS exam_allocations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            exam_name TEXT NOT NULL,
            grade TEXT NOT NULL,
            student_count INTEGER NOT NULL,
            sheets_per_student INTEGER NOT NULL,
            expected_sheets INTEGER NOT NULL,
            extra_sheets INTEGER DEFAULT 60,
            gross_sheets_needed INTEGER NOT NULL,
            reams_allocated INTEGER NOT NULL,
            remaining_sheets INTEGER NOT NULL,
            term_context TEXT NOT NULL,
            year_context TEXT NOT NULL,
            date_logged TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''')
    config_check = conn.execute('SELECT COUNT(*) as count FROM system_config').fetchone()
    if config_check['count'] == 0:
        conn.execute("INSERT INTO system_config (current_term, current_year) VALUES ('Term 1', '2026')")
    conn.commit()
    conn.close()

@app.before_request
def initialize_on_startup():
    init_db()

def update_student_summary(conn, adm_no):
    student = conn.execute('SELECT term1, term2, term3 FROM students WHERE adm_no = ?', (adm_no,)).fetchone()
    if student:
        pending_count = 0
        if student['term1'] == 'Pending': pending_count += 1
        if student['term2'] == 'Pending': pending_count += 1
        if student['term3'] == 'Pending': pending_count += 1
        summary = "Cleared ✅" if pending_count == 0 else f"{pending_count} Reams Owed"
        conn.execute('UPDATE students SET summary_status = ? WHERE adm_no = ?', (summary, adm_no))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        conn = get_db_connection()
        
        # 1. Guarantee the user table exists
        conn.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL
            )
        ''')
        conn.commit()
        
        # 2. EMERGENCY DOOR: If there are ZERO admins in the system, automatically create yours
        from werkzeug.security import generate_password_hash
        admin_count = conn.execute("SELECT COUNT(*) FROM users WHERE role = 'Admin'").fetchone()[0]
        if admin_count == 0:
            conn.execute(
                "INSERT OR IGNORE INTO users (username, password_hash, role) VALUES (?, ?, ?)",
                ('erick_admin', generate_password_hash('admin123'), 'Admin')
            )
            conn.commit()

        # 3. Proceed with standard verification
        user = conn.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
        conn.close()
        
        if user and check_password_hash(user['password_hash'], password):
            user_obj = User(user['id'], user['username'], user['role'])
            login_user(user_obj)
            
            if user['role'] == 'Admin': 
                return redirect(url_for('admin_dashboard'))
            elif user['role'] == 'Principal': 
                return redirect(url_for('principal_dashboard'))
            elif user['role'] == 'Exam': 
                return redirect(url_for('exam_dashboard'))
            elif user['role'] == 'Taker': 
                return redirect(url_for('ream_taker_dashboard'))
                
        flash('Invalid username or password!')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.errorhandler(403)
def forbidden_error(error):
    return render_template('403.html'), 403
@app.route('/')
def home():
    return redirect('/admin')

# ------------------ ADMIN DESK ------------------

@app.route('/admin')
@login_required
@role_required(['Admin'])
def admin_dashboard():
    conn = get_db_connection()
    config = conn.execute('SELECT * FROM system_config LIMIT 1').fetchone()
    students = conn.execute('SELECT * FROM students').fetchall()
    distinct_grades = conn.execute('SELECT DISTINCT grade FROM students ORDER BY grade').fetchall()
    conn.close()
    return render_template('admin.html', config=config, students=students, distinct_grades=distinct_grades)

@app.route('/admin/report')
def generate_report():
    term_selected = request.args.get('term')
    year_selected = request.args.get('year')
    grade_selected = request.args.get('grade')
    term_col = term_selected.replace(" ", "").lower()
    conn = get_db_connection()
    rows = conn.execute('''SELECT adm_no, name, grade, stream, gender, term1, term2, term3, summary_status 
                           FROM students WHERE grade = ? ORDER BY stream, adm_no''', (grade_selected,)).fetchall()
    conn.close()
    student_list = []
    for r in rows:
        student_list.append({
            'adm_no': r['adm_no'],
            'name': r['name'],
            'stream': r['stream'],
            'term_status': r[term_col],
            'summary_status': r['summary_status']
        })
    return jsonify({'students': student_list, 'term': term_selected, 'year': year_selected, 'grade': grade_selected})

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
    adm_no = request.form['adm_no'].strip()
    name = request.form['name'].strip()
    grade = request.form['grade'].strip()
    stream = request.form['stream'].strip()
    gender = request.form['gender']
    conn = get_db_connection()
    try:
        conn.execute('INSERT INTO students (adm_no, name, grade, stream, gender) VALUES (?, ?, ?, ?, ?)', (adm_no, name, grade, stream, gender))
        conn.commit()
    except sqlite3.IntegrityError:
        pass
    conn.close()
    return redirect('/admin')

# ------------------ REAM TAKER DESK ------------------

@app.route('/taker')
@login_required
@role_required(['Taker', 'Admin'])
def ream_taker_dashboard():
    conn = get_db_connection()
    config = conn.execute('SELECT * FROM system_config LIMIT 1').fetchone()
    students = conn.execute('SELECT * FROM students').fetchall()
    conn.close()
    return render_template('ream_taker.html', config=config, students=students)

@app.route('/taker/submit/<adm_no>')
@login_required
@role_required(['Taker', 'Admin'])
def taker_submit(adm_no):
    conn = get_db_connection()
    config = conn.execute('SELECT current_term FROM system_config LIMIT 1').fetchone()
    current_term = config['current_term'].replace(" ", "").lower()
    conn.execute(f"UPDATE students SET {current_term} = 'Submitted' WHERE adm_no = ?", (adm_no,))
    update_student_summary(conn, adm_no)
    conn.commit()
    conn.close()
    return redirect('/taker')

@app.route('/taker/undo/<adm_no>')
@login_required
@role_required(['Taker', 'Admin'])
def taker_undo(adm_no):
    conn = get_db_connection()
    config = conn.execute('SELECT current_term FROM system_config LIMIT 1').fetchone()
    current_term = config['current_term'].replace(" ", "").lower()
    conn.execute(f"UPDATE students SET {current_term} = 'Pending' WHERE adm_no = ?", (adm_no,))
    update_student_summary(conn, adm_no)
    conn.commit()
    conn.close()
    return redirect('/taker')
# ------------------ EXAMINATION DEPARTMENT DESK ------------------

@app.route('/exam')
@login_required
@role_required(['Exam', 'Admin'])
def exam_dashboard():
    conn = get_db_connection()
    config = conn.execute('SELECT * FROM system_config LIMIT 1').fetchone()
    distinct_grades = conn.execute('SELECT DISTINCT grade FROM students ORDER BY grade').fetchall()
    allocations = conn.execute('SELECT * FROM exam_allocations ORDER BY date_logged DESC').fetchall()
    total_remnants_row = conn.execute('SELECT SUM(remaining_sheets) as total_rem FROM exam_allocations').fetchone()
    grand_total_leftover = total_remnants_row['total_rem'] if total_remnants_row['total_rem'] is not None else 0
    conn.close()
    return render_template('exam.html', config=config, distinct_grades=distinct_grades, allocations=allocations, grand_total_leftover=grand_total_leftover)

@app.route('/api/get_grade_count')
def get_grade_count():
    grade = request.args.get('grade')
    conn = get_db_connection()
    count_row = conn.execute('SELECT COUNT(*) as total FROM students WHERE grade = ?', (grade,)).fetchone()
    conn.close()
    return jsonify({'total': count_row['total'] if count_row else 0})

@app.route('/exam/allocate', methods=['POST'])
def allocate_exam_reams():
    exam_name = request.form['exam_name']
    grade = request.form['grade']
    student_count = int(request.form['student_count'])
    sheets_per_student = int(request.form['sheets_per_student'])
    term_context = request.form['term_context']
    year_context = request.form['year_context']
    
    expected_sheets = student_count * sheets_per_student
    extra_sheets = 60
    gross_sheets_needed = expected_sheets + extra_sheets
    reams_allocated = math.ceil(gross_sheets_needed / 500)
    
    total_sheets_provided = reams_allocated * 500
    remaining_sheets = total_sheets_provided - gross_sheets_needed
    
    conn = get_db_connection()
    conn.execute('''
        INSERT INTO exam_allocations (
            exam_name, grade, student_count, sheets_per_student, 
            expected_sheets, extra_sheets, gross_sheets_needed, 
            reams_allocated, remaining_sheets, term_context, year_context
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''', 
        (exam_name, grade, student_count, sheets_per_student, 
         expected_sheets, extra_sheets, gross_sheets_needed, 
         reams_allocated, remaining_sheets, term_context, year_context))
    conn.commit()
    
    # Calculate fresh real-time numbers for the SMS message contents
    t1 = conn.execute("SELECT COUNT(*) as total FROM students WHERE term1 LIKE 'submitted%'").fetchone()['total']
    t2 = conn.execute("SELECT COUNT(*) as total FROM students WHERE term2 LIKE 'submitted%'").fetchone()['total']
    t3 = conn.execute("SELECT COUNT(*) as total FROM students WHERE term3 LIKE 'submitted%'").fetchone()['total']
    reams_received = t1 + t2 + t3
    
    consumed_row = conn.execute('SELECT SUM(reams_allocated) as total FROM exam_allocations').fetchone()
    reams_consumed = consumed_row['total'] if consumed_row['total'] is not None else 0
    live_stock_reams = reams_received - reams_consumed
    
    leftover_sheets_row = conn.execute('SELECT SUM(remaining_sheets) as total FROM exam_allocations').fetchone()
    leftover_sheets = leftover_sheets_row['total'] if leftover_sheets_row['total'] is not None else 0
    conn.close()
    
    # SMS BROADCAST PROTOCOL
    try:
        # ⚠️ CHANGE THESE TWO LINES WITH YOUR AFRICA'S TALKING DETAILS
        username = "ReamManagement"
        api_key = "atsk_cb7f17f79b851238d02dd731f24126f1f841fb46c07f2358788481ad37ee2579bad18699"
        
        africastalking.initialize(username, api_key)
        sms = africastalking.SMS
        
        # ⚠️ CHANGE THESE TO THE ACTUAL PHONE NUMBERS (Keep the plus sign and country code)
        recipients = ["+254755479890"] 
        
        sms_message = (
            f"⚠️ ReamTracker Audit Update\n"
            f"New Print Run: {exam_name} ({grade})\n"
            f"---------------------------\n"
            f"📦 Live Cabinet Stock: {live_stock_reams} Reams\n"
            f"📉 Consumed Reams: {reams_consumed} Reams\n"
            f"📄 Leftover Loose Paper: {leftover_sheets} sheets\n"
            f"---------------------------\n"
            f"Context: {term_context}, {year_context}"
        )
        
        sms.send(sms_message, recipients)
        print("Inventory text sent out successfully.")
    except Exception as e:
        print(f"SMS Broadcast failed to dispatch: {e}")
        
    return redirect('/exam')
@app.route('/admin/create_user', methods=['POST'])
def create_user():
    username = request.form.get('username')
    plain_password = request.form.get('password')
    role = request.form.get('role') # Taker, Exam, Principal, Admin
    
    if not username or not plain_password or not role:
        flash("All fields are required!")
        return redirect(url_for('admin_dashboard'))
        
    conn = get_db_connection()
    try:
        # Securely hash the password before saving it
        from werkzeug.security import generate_password_hash
        hashed_password = generate_password_hash(plain_password)
        
        conn.execute(
            "INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)",
            (username, hashed_password, role)
        )
        conn.commit()
        flash(f"User '{username}' successfully created as {role}!")
    except sqlite3.IntegrityError:
        flash("Error: That username is already taken.")
    finally:
        conn.close()
        
    return redirect(url_for('admin_dashboard'))

# ------------------ PRINCIPAL AUDIT OVERVIEW ROUTE ------------------
@app.route('/principal')
@login_required
@role_required(['Principal', 'Admin'])
def principal_dashboard():
    conn = get_db_connection()
    config = conn.execute('SELECT * FROM system_config LIMIT 1').fetchone()
    
    total_students_row = conn.execute('SELECT COUNT(*) as total FROM students').fetchone()
    expected_reams = total_students_row['total'] if total_students_row else 0
    
    t1_count = conn.execute("SELECT COUNT(*) as total FROM students WHERE term1 LIKE 'submitted%'").fetchone()['total']
    t2_count = conn.execute("SELECT COUNT(*) as total FROM students WHERE term2 LIKE 'submitted%'").fetchone()['total']
    t3_count = conn.execute("SELECT COUNT(*) as total FROM students WHERE term3 LIKE 'submitted%'").fetchone()['total']
    reams_received = t1_count + t2_count + t3_count
    
    consumed_row = conn.execute('SELECT SUM(reams_allocated) as total FROM exam_allocations').fetchone()
    reams_consumed = consumed_row['total'] if consumed_row['total'] is not None else 0
    
    live_stock_reams = reams_received - reams_consumed
    
    leftover_sheets_row = conn.execute('SELECT SUM(remaining_sheets) as total FROM exam_allocations').fetchone()
    leftover_sheets = leftover_sheets_row['total'] if leftover_sheets_row['total'] is not None else 0
    
    recent_logs = conn.execute('SELECT * FROM exam_allocations ORDER BY date_logged DESC LIMIT 10').fetchall()
    conn.close()
    
    return render_template('principal.html', 
                           config=config,
                           expected_reams=expected_reams,
                           reams_received=reams_received,
                           reams_consumed=reams_consumed,
                           live_stock_reams=live_stock_reams,
                           leftover_sheets=leftover_sheets,
                           recent_logs=recent_logs)

@app.route('/admin/upload_students', methods=['POST'])
def upload_students():
    if 'csv_file' not in request.files:
        flash('No file selected!')
        return redirect(url_for('admin_dashboard'))
        
    file = request.files['csv_file']
    if file.filename == '':
        flash('No file selected!')
        return redirect(url_for('admin_dashboard'))
        
    if file and file.filename.endswith('.csv'):
        csv_file = TextIOWrapper(file.stream, encoding='utf-8')
        reader = csv.DictReader(csv_file)
        
        # Clean up any weird spaces or casing from Excel headers
        if reader.fieldnames:
            reader.fieldnames = [field.strip().lower() for field in reader.fieldnames]
        
        conn = get_db_connection()
        success_count = 0
        duplicate_count = 0
        skipped_count = 0
        
        try:
            for row in reader:
                # Strip spaces from values to prevent empty string mismatches
                adm_no = row.get('adm_no')
                name = row.get('name')
                grade = row.get('grade')
                stream = row.get('stream')
                gender = row.get('gender')
                
                if adm_no and name and grade and stream and gender:
                    try:
                        conn.execute(
                            """
                            INSERT INTO students (adm_no, name, grade, stream, gender) 
                            VALUES (?, ?, ?, ?, ?)
                            """,
                            (str(adm_no).strip(), str(name).strip(), str(grade).strip(), str(stream).strip(), str(gender).strip())
                        )
                        success_count += 1
                    except sqlite3.IntegrityError:
                        duplicate_count += 1
                else:
                    # Keeps track of lines missing data or mismatched headers
                    skipped_count += 1
                        
            conn.commit()
            
            # This descriptive flash message will tell us EXACTLY what happened on your screen
            flash(f"Upload Complete! Successfully Imported: {success_count} | Skipped (Empty/Header Mismatch): {skipped_count} | Skipped (Already Exists): {duplicate_count}")
            
        except Exception as e:
            flash(f"Error processing spreadsheet: {str(e)}")
        finally:
            conn.close()
    else:
        flash('Invalid file format. Please upload a standard .csv spreadsheet file.')
        
    return redirect(url_for('admin_dashboard'))
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)