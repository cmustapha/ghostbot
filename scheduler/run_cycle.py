import csv, random, time
from utils.db import init_db, already_posted, mark_posted
from utils.logger import get_logger
import subprocess

log = get_logger("cycle")

conn = init_db()
with open("data/queue.csv", newline='', encoding="utf-8") as f:
    for row in csv.DictReader(f):
        img, cap, tags, plats = row["image_path"], row["caption"], row["tags"], row["platforms"]
        for p in plats.split(":"):
            if already_posted(conn, p, img): continue
            if p == "tumblr":
                subprocess.run(["python3", "tumblr/post_photo_selenium.py", "--image", img, "--caption", cap])
            mark_posted(conn, p, "ghost01", img)
            time.sleep(random.uniform(30, 60))
