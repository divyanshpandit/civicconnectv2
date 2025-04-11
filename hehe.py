import sqlite3

conn = sqlite3.connect("db.sqlite3")
conn.execute('''
    CREATE TABLE alerts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        neighborhood TEXT,
        alert TEXT
    );
''')
conn.commit()
conn.close()
