import google.generativeai as genai
import os

# HARDCODED KEY that we think is correct
TEST_KEY = "AIzaSyDMzBVzlHdB6wmVWRjQGtYytz72hnePcBA"

print(f"Testing generation with key: {TEST_KEY[:10]}...")

genai.configure(api_key=TEST_KEY)

try:
    print("Attempting to generate with gemini-2.0-flash...")
    model = genai.GenerativeModel('gemini-2.0-flash')
    response = model.generate_content("Hello")
    print("SUCCESS!")
    print(response.text)
except Exception as e:
    print("FAILURE during generation!")
    print(e)
