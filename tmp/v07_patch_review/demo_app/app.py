"""Harmless example for read_source/search_code integration demonstrations."""


def list_users(cursor):
    # Static parameterized SQL. Finding a keyword does not imply SQL injection.
    cursor.execute("SELECT id, name FROM users WHERE active = ?", (1,))
    return cursor.fetchall()
