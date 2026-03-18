import sqlite3
import os
import pandas as pd

DB_PATH = "data/mailing_list.db"

def check_db():
    if not os.path.exists(DB_PATH):
        print(f"Database not found at {DB_PATH}")
        return

    print(f"--- Database: {DB_PATH} ---")
    conn = sqlite3.connect(DB_PATH)
    try:
        # Get tables
        tables = pd.read_sql("SELECT name FROM sqlite_master WHERE type='table';", conn)
        print("\n[Tables]")
        print(tables)

        # Count rows in each table
        print("\n[Row Counts]")
        for table in tables['name']:
            count = pd.read_sql(f"SELECT COUNT(*) as count FROM {table}", conn).iloc[0]['count']
            print(f"{table}: {count}")

        # Show last 5 leads
        if 'leads' in tables['name'].values:
            print("\n[Last 5 Leads]")
            leads = pd.read_sql("SELECT id, company, email, source, created_at FROM leads ORDER BY id DESC LIMIT 5", conn)
            print(leads.to_string(index=False))

        # Show recent outreach
        if 'outreach' in tables['name'].values:
            print("\n[Last 5 Outreach Actions]")
            outreach = pd.read_sql("SELECT * FROM outreach ORDER BY id DESC LIMIT 5", conn)
            if not outreach.empty:
                print(outreach.to_string(index=False))
            else:
                print("No outreach records found.")

    except Exception as e:
        print(f"Error: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    check_db()
