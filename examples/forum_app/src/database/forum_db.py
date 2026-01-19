import sqlite3

def create_sqlite_database():
    conn = sqlite3.get_connection('forum_data.db'))

    c = conn.cursor()

    # Create table for users
    c.execute("""CREATE TABLE IF NOT EXISTS users (
                        id INTEGER PRIMARY KEY,
                        username TEXT UNIQUE NOT NULL,
                        email TEXT UNIQUE NOT NULL,
                        password_hash TEXT NOT NULL
                    )""")

    # Create table for posts
    c.execute("""CREATE TABLE IF NOT EXISTS posts (
                        id INTEGER PRIMARY KEY,
                        user_id INTEGER NOT NULL,
                        title TEXT NOT NULL,
                        content TEXT NOT NULL,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY(user_id) REFERENCES users(id)))""")

    conn.commit()
    print("SQLite database for forum data created successfully!")

if __name__ == '__main__':
    create_sqlite_database()