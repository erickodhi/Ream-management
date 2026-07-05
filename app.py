from flask import Flask, render_template, request, redirect, jsonify
import sqlite3
import math

app = Flask(__name__)

def get_db_connection():
    conn = sqlite3.connect('ream_yearly_v1.db')
    conn.row_factory = sqlite3.Row
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
    
    # UPDATED: Added remaining_sheets column for explicit paper audit tracking
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

@app.route('/')
def home():
    return redirect('/admin')

# ------------------ ADMIN DESK ------------------
@app.route('/admin')
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
    adm_no = request.form['adm_no']
    name = request.form['name']
    grade = request.form['grade']
    stream = request.form['stream']
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
    current_term = config['current_term'].replace(" ", "").lower()
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

# ------------------ EXAMINATION DEPARTMENT DESK ------------------
@app.route('/exam')
def exam_dashboard():
    conn = get_db_connection()
    config = conn.execute('SELECT * FROM system_config LIMIT 1').fetchone()
    distinct_grades = conn.execute('SELECT DISTINCT grade FROM students ORDER BY grade').fetchall()
    allocations = conn.execute('SELECT * FROM exam_allocations ORDER BY date_logged DESC').fetchall()
    conn.close()
    return render_template('exam.html', config=config, distinct_grades=distinct_grades, allocations=allocations)

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
    
    # NEW MATH: Calculate the leftover loose paper sheets remaining from the opened reams
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
    conn.close()
    return redirect('/exam')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)