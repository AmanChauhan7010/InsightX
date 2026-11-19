import sqlite3

def fetch_user_record(user_id: int):
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    cursor.execute(f'SELECT * FROM users WHERE id = {user_id}')
    return cursor.fetchone()
