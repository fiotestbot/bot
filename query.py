import os
import sqlite3
import requests
import subprocess
from pathlib import Path
from bs4 import BeautifulSoup

DB_FILE="message_ids.sqlite3"
URL="https://lore.kernel.org/fio/?t=1&q=s%3A%22PATCH%22+AND+NOT+s%3A%22RE%22+AND+dt%3A20221029165149.."

def get_ids():
    page = requests.get(URL)

    soup = BeautifulSoup(page.content, "html.parser")

    ids = set()
    for link in soup.find_all('a'):
        href = link.get('href')
        if '?' in href:
            continue
        if '@' not in href:
            continue
        split = href.split('-')
        if len(split) == 3:
            split[1] = "1"
            href = "-".join(split)
            # TODO ensure last element is a valid email address
            # TODO ensure second element is an integer
        elif len(split) != 1:
            continue

        if href[-1] == '/':
            href = href[:-1]

        if href not in ids:
            ids.add(href)

    return ids


def create_table(conn):
    """Create SQLite3 table."""

    sql_create_id_table = """CREATE TABLE IF NOT EXISTS IDS (ID TEXT PRIMARY KEY);"""

    conn.cursor().execute(sql_create_id_table)


def init_db(db_file):
    """Initialize database."""

    db_file = os.path.join(Path(__file__).absolute().parent, db_file)

    conn = None
    try:
        create = not os.path.exists(db_file)
        conn = sqlite3.connect(db_file)
        if create:
            create_table(conn)
    except Exception as e:
        print(e)
        sys.exit(1)

    return conn


def id_exists(conn, id):
    """Check if database contains id."""

    sql_check_item = """SELECT EXISTS(SELECT 1 FROM IDS WHERE ID=? COLLATE NOCASE) LIMIT 1"""

    cur = conn.cursor()
    check = cur.execute(sql_check_item, (id,))
    return check.fetchone()[0] == 1


def add_id(conn, id):
    """Add record to the database."""

    sql_insert_item = """INSERT OR REPLACE INTO IDS(ID) VALUES(?)"""

    cur = conn.cursor()

    cur.execute(sql_insert_item, (id,))
    conn.commit()


def process_ids(id_list):
    conn = init_db(DB_FILE)
    for id in id_list:
        if id_exists(conn, id):
            print("skipping {0}".format(id))
        else:
            print("testing {0}".format(id))
            subprocess.run(["./test-list-patch.sh", id, id])
            add_id(conn, id)

    conn.close()


def main():
    """Entry point."""

    ids = get_ids()
    process_ids(ids)


if __name__ == "__main__":
    main()
