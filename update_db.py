import os
import psycopg2

# შენი Neon ბაზის URL (ზუსტად იგივე, რაც app.py-ში გიწერია)
DATABASE_URL = "postgresql://neondb_owner:npg_o6plSifKNIc9@ep-damp-thunder-asbmmuxu.c-4.eu-central-1.aws.neon.tech/neondb?sslmode=require"

def update_database():
    print("Connecting to Neon PostgreSQL database...")
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = True
    cursor = conn.cursor()
    
    queries = [
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS full_name VARCHAR(100) DEFAULT '';",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS email VARCHAR(100) DEFAULT '';",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS is_banned BOOLEAN DEFAULT FALSE;",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS clicks_left INTEGER DEFAULT 250;",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS total_clicks INTEGER DEFAULT 0;",
        "ALTER TABLE questions ADD COLUMN IF NOT EXISTS region_id VARCHAR(50) DEFAULT 'tbilisi';"
    ]
    
    for q in queries:
        try:
            print(f"Executing: {q}")
            cursor.execute(q)
        except Exception as e:
            print(f"Note: {e}")
            
    cursor.close()
    conn.close()
    print("Database updated successfully!")

if __name__ == "__main__":
    update_database()
