import os
import sys
import ssl
import json
import email
import smtplib
import argparse
import datetime
import requests
import subprocess
from github import Github
from pathlib import Path
from bs4 import BeautifulSoup
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.header import Header


NOTIFIED_DB="notified.json"
TESTED_DB="message_ids.json"
URL='https://lore.kernel.org/fio/?t=1&q=s%3A"[PATCH"+AND+NOT+s%3A"re%3A"+AND+d%3A{0}'
#
# s:"[PATCH" AND NOT s:"RE:" AND d:{0}
#
# This may need more refinement
#
# For details see:
#   https://lore.kernel.org/fio/_/text/help/
#   https://xapian.org/docs/queryparser.html
#   https://people.kernel.org/monsieuricon/lore-lei-part-1-getting-started
#

def parse_args():
    """Parse command-line arguments."""

    parser = argparse.ArgumentParser(description="Query mailing list for new patches and test them")
    parser.add_argument("-q", "--query-only", action="store_true",
            help="Query for message IDs only")
    parser.add_argument("--since", action="store",
            help="Date range for query; last.week.. for everything since last week")
    parser.add_argument("--db", action="store", help="Specify file for saving message IDs")
    parser.add_argument("-n", "--notify", action="store_true", help="Send notifications regarding completed tests")
    args = parser.parse_args()

    return args


def query_msg_ids(since):
    """Get message IDs from from query."""

    query_url = URL.format(since)
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
        return list()

    try:
        with open(db_file, "r", encoding="utf-8") as file:
            tested_msg_ids = list(json.load(file)["message_ids"])
    except Exception as error:
        print("Unable to read database file:", error)
        sys.exit(1)

    return tested_msg_ids


def add_msg_id(tested_msg_ids, msg_id, db_file):
    """Add record to the database."""

    tested_msg_ids.append(msg_id)

    try:
        with open(db_file, "w", encoding="utf-8") as file:
            dictionary = { "message_ids": sorted(tested_msg_ids) }
            file.write(json.dumps(dictionary, indent=4))
            try:
                subprocess.run(["git", "add", db_file], check=True)
            except Exception as error:
                print("Unable to add database file to git:", error)

    except Exception as error:
        print("Unable to add message ID to database file:", error)


def test_msg_ids(msg_id_list, query_only=False, db_file=TESTED_DB):
    """Save new message IDs and emit them."""

    tested_msg_ids = init_db(db_file)
    for msg_id in msg_id_list:
        if query_only:
            print(msg_id)
        elif msg_id not in tested_msg_ids:
            print(msg_id)
            add_msg_id(tested_msg_ids, msg_id, db_file)


def get_workflow(token, branch):
    """Get GitHub Actions workflow."""

    g = Github(token)
    repo = g.get_repo("fiotestbot/fio")
    workflow_runs = repo.get_workflow_runs(branch=branch)
    count = workflow_runs.totalCount

    if count == 0:
        return None

    return workflow_runs[count-1]   # Get the most recent workflow


def msg_id2branch(msg_id):
    """Convert message ID to branch name."""

    return f"test-{msg_id}"


def branch2msg_id(branch):
    """Convert branch name to message ID."""

    return branch.replace("test-", "")


def get_subject(msg_id):
    """Get email subject."""

    page = requests.get(f"https://lore.kernel.org/fio/{msg_id}/")
    soup = BeautifulSoup(page.content, "html.parser")

    subject = "fio CI test result"
    for line in soup.body.get_text().split("\n"):
        if line.startswith("Subject: "):
            subject = line.replace("Subject: ", "")
            break

    return subject


def send_email(outcome, url, msg_id):
    """Send email message."""

#
# TODO change recipient_email to mailing list when deploying for real
#
    port = 465
    smtp_server = "smtp.gmail.com"
    user_email = "fiotestbot@gmail.com"
    user_password = os.environ.get("EMAIL_PASSWORD")
    recipient_email = "vincentfu@gmail.com"
    body = f"""
The result of fio's continuous integration tests was: {outcome}

For more details see {url}
"""
    msg = MIMEMultipart()
    msg["From"] = user_email
    msg["To"] = recipient_email
    msg["Subject"] = Header("Re: " + get_subject(msg_id), "utf-8")
    msg["In-Reply-To"] = "<" + msg_id + ">"
    msg["References"] = "<" + msg_id + ">"
    msg["Message-ID"] = email.utils.make_msgid()
    msg.attach(MIMEText(body, "plain"))
    email_body = msg.as_string()

    with smtplib.SMTP_SSL(smtp_server, port) as server:
        server.login(user_email, user_password)
        server.sendmail(user_email, recipient_email, email_body)
 

def notify_msg_ids(msg_id_list, query_only=False, db_file=NOTIFIED_DB):
    """Scan for completed tests and send email messages with results."""

    notified_msg_ids = init_db(db_file)
    token = os.environ.get("GITHUB_PAT")
    for msg_id in msg_id_list:
        print(msg_id)
        branch = msg_id2branch(msg_id)
        if msg_id in notified_msg_ids:
            print("Already notified")
            continue
        workflow = get_workflow(token, branch)
        if workflow:
            print(branch, workflow.conclusion)
            if not query_only:
                send_email(workflow.conclusion, workflow.html_url, msg_id)
                add_msg_id(notified_msg_ids, msg_id, db_file)
                try:
                    subprocess.run(["git", "add", db_file], check=True)
                    subprocess.run(["git", "commit", "-m", f"Add {branch} to notified database"], check=True)
                    subprocess.run(["git", "push"], check=True)
                except Exception as error:
                    print("Unable to add database file to git:", error)
        else:
            print("No workflow found")


def main():
    """Entry point."""

    args = parse_args()
    if not args.since:
        # By default query patches since last week
        yesterday = datetime.date.today() - datetime.timedelta(days = 1)
        args.since = "last.week.."
    if not args.db:
        if args.notify:
            args.db = os.path.join(Path(__file__).absolute().parent, NOTIFIED_DB)
        else:
            args.db = os.path.join(Path(__file__).absolute().parent, TESTED_DB)

    msg_ids = query_msg_ids(args.since)
    if args.notify:
        notify_msg_ids(msg_ids, query_only=args.query_only, db_file=args.db)
    else:
        test_msg_ids(msg_ids, query_only=args.query_only, db_file=args.db)


if __name__ == "__main__":
    main()
