import sqlite3

conn = sqlite3.connect('taiwan_election_2024.db')
cur = conn.cursor()

cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = cur.fetchall()
print('Tables:', tables)

for t in tables:
    name = t[0]
    cur.execute(f"PRAGMA table_info({name})")
    cols = cur.fetchall()
    print(f"\n{name}:")
    for col in cols:
        print(" ", col)

    cur.execute(f"SELECT COUNT(*) FROM {name}")
    print(f"  Row count: {cur.fetchone()[0]}")

conn.close()