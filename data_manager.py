import csv
import os

FEEDBACK_FILE = 'feedback_data.csv'

FEATURE_NAMES = ['desc_score', 'title_score', 'tags_score', 'category_score', 'user_score']

def save_feedback(desc_score, title_score, tags_score, category_score, user_score):
    exists = os.path.exists(FEEDBACK_FILE)
    with open(FEEDBACK_FILE, 'a', newline='') as f:
        writer = csv.writer(f)
        if not exists:
            writer.writerow(FEATURE_NAMES)
        writer.writerow([desc_score, title_score, tags_score, category_score, user_score])

def load_feedback():
    if not os.path.exists(FEEDBACK_FILE):
        return []
    with open(FEEDBACK_FILE, 'r') as f:
        reader = csv.DictReader(f)
        return list(reader) 