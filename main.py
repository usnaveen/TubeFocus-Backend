from youtube_api import fetch_video_details
from scoring_modules import score_description, score_title, score_tags, score_category
from data_manager import save_feedback, load_feedback
from model_trainer import train_and_save_model, load_model
import numpy as np

MIN_FEEDBACK = 5

def main():
    video_id = input('Enter YouTube video ID: ').strip()
    goal = input('Enter your learning goal: ').strip()
    details = fetch_video_details(video_id)
    if not details:
        print('Could not fetch video details.')
        return
    print(f"Title: {details['title']}")
    print(f"Category: {details['category']}")
    print(f"Tags: {', '.join(details['tags']) if details['tags'] else '(none)'}")
    print(f"Description: {details['description'][:120]}{'...' if len(details['description']) > 120 else ''}")

    # Compute scores
    desc_score = score_description(goal, details['title'], details['description'])
    title_score = score_title(goal, details['title'])
    tags_score = score_tags(goal, details['tags'])
    category_score = score_category(goal, details['category'])
    features = np.array([[desc_score, title_score, tags_score, category_score]])

    # Predict final score
    model = load_model()
    if model:
        final_score = float(model.predict(features)[0])
    else:
        final_score = np.mean(features)
    print(f"Predicted relevance score: {final_score:.2f} (0-1 scale)")

    # User feedback
    user_score = float(input('How would you rate this video for your goal? (0-1): '))
    save_feedback(desc_score, title_score, tags_score, category_score, user_score)

    # Retrain if enough feedback
    feedback = load_feedback()
    if len(feedback) >= MIN_FEEDBACK:
        X = np.array([[float(row['desc_score']), float(row['title_score']), float(row['tags_score']), float(row['category_score'])] for row in feedback])
        y = np.array([float(row['user_score']) for row in feedback])
        train_and_save_model(X, y)
        print('Model retrained with new feedback!')
    else:
        print(f'Not enough feedback to retrain (need {MIN_FEEDBACK}, have {len(feedback)})')

if __name__ == '__main__':
    main() 