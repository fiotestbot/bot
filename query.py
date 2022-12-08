import os
import sys
import json
import argparse
import datetime
import subprocess
from pathlib import Path
from bs4 import BeautifulSoup

import requests

DB_FILE="message_ids.json"
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


def init_db(db_file):
    """Initialize database."""

    if not os.path.exists(db_file):
        return set()

    try:
        with open(db_file, "r") as file:
            tested_msg_ids = set(json.load(file)["message_ids"])
    except Exception as error:
        print("Unable to read database file:", error)
        sys.exit(1)

    return tested_msg_ids


def add_msg_id(tested_msg_ids, msg_id, db_file):
    """Add record to the database."""

    tested_msg_ids.add(msg_id)

    try:
        with open(db_file, "w") as file:
            dict = { "message_ids": list(tested_msg_ids) }
            file.write(json.dumps(dict))
    except Exception as error:
        print("Unable to add message ID to database file:", error)


def process_msg_ids(msg_id_list, query_only=False, skip_test=False, db_file=DB_FILE):
    """Save new message IDs, download corresponding patch series, and initiate testing."""

    tested_msg_ids = init_db(db_file)
    for msg_id in msg_id_list:
        if query_only:
            print("Found {0}".format(msg_id))
        elif msg_id in tested_msg_ids:
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
                    add_msg_id(tested_msg_ids, msg_id, db_file)


def main():
    """Entry point."""

    args = parse_args()
    if not args.since:
        # By default query patches since yesterday
        yesterday = datetime.date.today() - datetime.timedelta(days = 1)
        args.since = yesterday.strftime("%Y%m%d") + "000000.."
    if not args.db:
        args.db = DB_FILE

    msg_ids = query_msg_ids(args.since)
    process_msg_ids(msg_ids, query_only=args.query_only, skip_test=args.skip_test,
        db_file=args.db)


if __name__ == "__main__":
    main()
