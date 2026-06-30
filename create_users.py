import sqlite3
from werkzeug.security import generate_password_hash

def init_users():
    conn = sqlite3.connect('ream_management.db')
    cursor = conn.cursor()
    
    # 1. Create the users table if it doesn't exist yet
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL
        )
    ''')
    
    # 2. Define your initial school staff accounts
    # CHANGE THESE PASSWORDS TO LATER SPREAD TO STAFF
    staff_users = [
        ('erick_admin', generate_password_hash('admin123'), 'Admin'),
        ('principal_office', generate_password_hash('prim123'), 'Principal'),
        ('exam_clerk', generate_password_hash('exam123'), 'Exam'),
        ('store_taker', generate_password_hash('taker123'), 'Taker')
    ]
    
    # 3. Insert accounts cleanly into the database
    for username, password_hash, role in staff_users:
        try:
            cursor.execute(
                'INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)',
                (username, password_hash, role)
            )
            print(f"Success: Created {role} account ({username})")
        except sqlite3.IntegrityError:
            print(f"Notice: Account for {username} already exists.")
            
    conn.commit()
    conn.close()

if __name__ == '__main__':
    init_users()