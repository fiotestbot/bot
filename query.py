import os
import sys
import sqlite3
import argparse
import datetime
import subprocess
from pathlib import Path
from bs4 import BeautifulSoup

import requests

DB_FILE="message_ids.sqlite3"
URL="https://lore.kernel.org/fio/?t=1&q=s%3A%22PATCH%22+AND+NOT+s%3A%22RE%22+AND+dt%3A{0}"

def parse_args():
    """Parse command-line arguments."""

    parser = argparse.ArgumentParser(description="Query mailing list for new patches and test them")
    parser.add_argument("-q", "--query-only", action="store_true",
            help="Query for message IDs only")
    parser.add_argument("-s", "--skip-test", action="store_true",
            help="Skip testing (but still store new message IDs)")
    parser.add_argument("--since", action="store",
            help="Date range for query; 20221201000000.. for everything since 2022-12-01")
    parser.add_argument("--db", action="store", help="Specify file for saving message IDs")
    args = parser.parse_args()

    return args


def query_msg_ids(since):
    """Get message IDs from from query."""

    query_url = URL.format(since)
    print("Query URL:", query_url)
    page = requests.get(query_url)
    soup = BeautifulSoup(page.content, "html.parser")

    msg_ids = set()
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

        if href not in msg_ids:
            msg_ids.add(href)

    return msg_ids


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
    except Exception as error:
        print("Unable to create database file:", error)
        sys.exit(1)

    return conn


def msg_id_exists(conn, msg_id):
    """Check if database contains id."""

    sql_check_item = """SELECT EXISTS(SELECT 1 FROM IDS WHERE ID=? COLLATE NOCASE) LIMIT 1"""

    cur = conn.cursor()
    check = cur.execute(sql_check_item, (msg_id,))
    return check.fetchone()[0] == 1


def add_msg_id(conn, msg_id):
    """Add record to the database."""

    sql_insert_item = """INSERT OR REPLACE INTO IDS(ID) VALUES(?)"""

    cur = conn.cursor()
    cur.execute(sql_insert_item, (msg_id,))
    conn.commit()


def process_msg_ids(msg_id_list, query_only=False, skip_test=False, db_file=DB_FILE):
    """Save new message IDs, download corresponding patch series, and initiate testing."""

    conn = init_db(DB_FILE)
    for msg_id in msg_id_list:
        if query_only:
            print("Found {0}".format(msg_id))
        elif msg_id_exists(conn, msg_id):
            print("Skipping {0}".format(msg_id))
        else:
            print("Testing {0}".format(msg_id))
            if skip_test:
                print("Skipping test")
            else:
                try:
                    with open("{0}.log".format(msg_id), "x") as file:
                        subprocess.run(["./test-list-patch.sh", "autotest/"+msg_id,
                            msg_id, "--cleanup"], stdout=file, stderr=file, check=True)
                except Exception as error:
                    print("Error initiating test:", error)
                else:
                    add_msg_id(conn, msg_id)

    conn.close()


def main():
    """Entry point."""

    args = parse_args()
    if not args.since:
        # By default query patches since yesterday
        yesterday = datetime.date.today() - datetime.timedelta(days = 1)
        args.since = yesterday.strftime("%Y%m%d") + "000000.."
    if not args.db:
        args.db_file = DB_FILE

    msg_ids = query_msg_ids(args.since)
    process_msg_ids(msg_ids, query_only=args.query_only, skip_test=args.skip_test,
        db_file=args.db)


if __name__ == "__main__":
    main()
