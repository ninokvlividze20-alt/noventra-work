import psycopg2

try:
    conn = psycopg2.connect(
        host='localhost',
        database='noventra_db',
        user='postgres',
        password='noventra2026'
    )
    print("წარმატება! ბაზასთან კავშირი დამყარებულია.")
    conn.close()
except Exception as e:
    print(f"შეცდომა: {e}")
