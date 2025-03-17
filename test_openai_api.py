import os
from openai import OpenAI
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Get the API key from the environment variables
api_key = os.getenv("OPENAI_API_KEY")

if not api_key:
    print("Error: OPENAI_API_KEY not found in environment variables.")
    print("Please make sure you have set the OPENAI_API_KEY in the .env file.")
    exit(1)

# Initialize the OpenAI client
client = OpenAI(api_key=api_key)

# Test the API key
try:
    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Hello, can you hear me?"}
        ],
        max_tokens=50
    )
    print("API key is valid. Response:")
    print(response.choices[0].message.content)
except Exception as e:
    print(f"Error: {e}")
    print("Please check your API key and try again.")
