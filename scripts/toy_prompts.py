
# toy_prompts.py
# Use this script to valid various prompt strategies for relevance scoring.

PROMPTS = {
    "1_BASELINE_SIMPLE": """
You are a relevance scoring engine.
Video Title: {title}
Video Description: {description}
User Goal: {goal}

Task: Rate the relevance of this video to the goal on a scale of 0-100.
Output JSON: {{"score": <int>, "reasoning": "<string>"}}
    """,

    "2_REASONING_FIRST_COT": """
You are an expert productivity assistant. Your task is to evaluate if a video is TRULY helpful for a specific goal.
Don't just look for keyword matches; look for educational value and alignment.

Video Title: {title}
Video Description: {description}
User Goal: {goal}

Step 1: Analyze the user's specific intent in their goal.
Step 2: Analyze the video content based on title and description.
Step 3: Compare intent vs content. Is it a tutorial? Entertainment? Commentary?
Step 4: Assign a score (0-100).
    - 0-20: Irrelevant or purely entertainment.
    - 21-50: Tangentially related but not actionable.
    - 51-80: Good match, helpful content.
    - 81-100: Perfect match, highly actionable and efficient.

Output a valid JSON object:
{
  "user_intent": "...",
  "video_type": "...",
  "alignment_analysis": "...",
  "score": <int>
}
    """,

    "3_FEW_SHOT_LEARNING": """
Score the relevance (0-100) of a video to a goal.

Examples:
Goal: "Learn Python for Data Science"
Video: "Funny Python Snake Compilation"
Score: 0
Reason: Pure entertainment, irrelevant to programming.

Goal: "Learn Python for Data Science"
Video: "Python for Beginners - Full Course"
Score: 80
Reason: Good comprehensive tutorial, though maybe not specific to Data Science.

Goal: "Learn Python for Data Science"
Video: "Pandas and NumPy for Data Analysis in Python"
Score: 95
Reason: Highly specific and relevant tools for the stated goal.

Now Score This:
Goal: {goal}
Video Title: {title}
Video Description: {description}

Output JSON: {{"score": <int>, "reason": "<string>"}}
    """,

    "4_STRICT_PROFESSOR_PERSONA": """
You are a very strict University Professor. You only value high-quality, dense, and academic/educational material.
You despise clickbait, fluff, and "entertainment-edutainment" content.

User Goal: {goal}
Video Title: {title}
Video Description: {description}

Critique this video. Is it worthy of the student's time?
Give a 'strict_score' (0-100) where 50 is already a pass. Most YouTube videos should score below 30.

Output JSON:
{
  "critique": "...",
  "is_fluff": <bool>,
  "strict_score": <int>
}
    """,

    "5_STRUCTURED_TAG_ANALYSIS": """
Analyze the relevance by extracting key concepts.

Goal: {goal}
Video Title: {title}
Video Description: {description}

1. Extract 3 key concepts from the Goal.
2. Extract 3 key concepts from the Video.
3. Calculate how many concepts overlap.
4. Score based on overlap strength.

Output JSON:
{
  "goal_concepts": ["...", "...", "..."],
  "video_concepts": ["...", "...", "..."],
  "overlap_concepts": ["..."],
  "score": <int>
}
    """
}

def get_toy_prompt(prompt_name, title, description, goal):
    """
    Returns the formatted prompt string.
    """
    if prompt_name not in PROMPTS:
        raise ValueError(f"Prompt {prompt_name} not found. Available: {list(PROMPTS.keys())}")
    
    return PROMPTS[prompt_name].format(
        title=title, 
        description=description, 
        goal=goal
    )

if __name__ == "__main__":
    # Example usage
    title = "Python for Beginners"
    desc = "Learn python in 1 hour."
    goal = "Learn coding"
    
    print("--- Example: 2_REASONING_FIRST_COT ---")
    print(get_toy_prompt("2_REASONING_FIRST_COT", title, desc, goal))
