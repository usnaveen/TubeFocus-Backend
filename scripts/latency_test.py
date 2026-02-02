
import os
import json
import subprocess
import tempfile

videos = [
    "https://www.youtube.com/watch?v=kJQP7kiw5Fk",  # Despacito
    "https://www.youtube.com/watch?v=8_x0E_k4Gk4",  # Khan Academy Statistics
    "https://www.youtube.com/watch?v=Rk2gS_9c_g4",  # Life In A Day 2020
    "https://www.youtube.com/watch?v=c_p2-S4bS_w",  # Key & Peele Substitute Teacher
    "https://www.youtube.com/watch?v=eOrNdBpGMv8",  # Avengers: Endgame Trailer
    "https://www.youtube.com/watch?v=1_2_t-6x-e8",  # MKBHD iPhone 15 Pro Review
    "https://www.youtube.com/watch?v=v4y-p_a-L8k",  # Casey Neistat Snowboarding
    "https://www.youtube.com/watch?v=i-hZ1a_iXkU",  # PewDiePie Minecraft
    "https://www.youtube.com/watch?v=J94Kx3e4_8",   # Binging with Babish Krabby Patty
    "https://www.youtube.com/watch?v=1_2_t-6x-e8",  # BBC News Webb Telescope
]

goals = [
    "Popular latin music",
    "Learn about statistics",
    "Global user-submitted documentary",
    "Funny classroom sketch",
    "Superhero movie trailer",
    "Latest smartphone technology review",
    "New York City snowboarding vlog",
    "Entertaining Minecraft gameplay",
    "How to cook a Krabby Patty",
    "James Webb Space Telescope news",
]

modes = [
    "title_only",
    "title_and_description",
    "title_and_clean_desc",
]

print("| Video | Goal | Mode | Latency (s) |")
print("|---|---|---|---|")

for i in range(len(videos)):
    video = videos[i]
    goal = goals[i]
    for mode in modes:
        with tempfile.NamedTemporaryFile() as tmp:
            command = f"""
            curl -s -o {tmp.name} -w '%{{time_total}}' -X POST -H "Content-Type: application/json" -H "X-API-KEY: changeme" -d '{{"video_url": "{video}", "goal": "{goal}", "mode": "{mode}"}}' http://localhost:8080/score/simple
            """
            try:
                latency = subprocess.check_output(command, shell=True, stderr=subprocess.STDOUT).decode('utf-8')
                video_id = video.split('=')[-1]
                print(f"| {video_id} | {goal} | {mode} | {latency} |")
            except subprocess.CalledProcessError as e:
                print(f"| {video.split('=')[-1]} | {goal} | {mode} | Error: {e.output} |")
