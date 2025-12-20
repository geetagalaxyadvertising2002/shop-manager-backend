import sqlite3

conn = sqlite3.connect("db.sqlite3")
cursor = conn.cursor()

# Clean admin + authtoken migrations
cursor.execute("DELETE FROM django_migrations WHERE app='admin';")
cursor.execute("DELETE FROM django_migrations WHERE app='authtoken';")

conn.commit()
conn.close()

print("Admin aur Authtoken migrations delete ho gaye ✅")
