import google.generativeai as genai
import os

# HARDCODED KEY for debugging only
TEST_KEY = "AIzaSyDMzBVzlHdB6wmVWRjQGtYytz72hnePcBA"

print(f"Testing key: {TEST_KEY[:10]}...")

try:
    genai.configure(api_key=TEST_KEY)
    print("Listing available models:")
    for m in genai.list_models():
        if 'generateContent' in m.supported_generation_methods:
            print(f"- {m.name}")
except Exception as e:
    print("\nFAILURE!")
    print(e)
