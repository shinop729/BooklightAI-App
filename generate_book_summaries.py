import os
import pandas as pd
import json
from pathlib import Path
from openai import OpenAI
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Initialize OpenAI client
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def generate_summary(book_title, author, highlights):
    """
    Generate a summary for a book using OpenAI's API based on the highlights.
    """
    # Prepare the prompt
    prompt = f"""
    Book Title: {book_title}
    Author: {author}
    
    Highlights from the book:
    {highlights}
    
    Based on these highlights, please generate a comprehensive summary of the book. 
    The summary should:
    1. Capture the main themes and key ideas of the book
    2. Be well-structured and coherent
    3. Be around 300-500 words
    4. Include the most important concepts and insights from the highlights
    5. Be written in a clear, engaging style
    """
    
    # Call the OpenAI API
    try:
        response = client.chat.completions.create(
            model="gpt-4-turbo",
            messages=[
                {"role": "system", "content": "You are a skilled book summarizer who can extract the key ideas and themes from book highlights and create a comprehensive, insightful summary."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=1000
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"Error generating summary for {book_title}: {e}")
        return f"Error generating summary: {e}"

def process_highlights_file(file_path, user_id):
    """
    Process the highlights file and generate summaries for each book.
    """
    # Read the highlights file
    df = pd.read_csv(file_path)
    
    # Group highlights by book title and author
    grouped = df.groupby(["書籍タイトル", "著者"])["ハイライト内容"].apply(lambda x: "\n".join(x)).reset_index()
    
    # Generate summaries for each book
    summaries = []
    for _, row in grouped.iterrows():
        book_title = row["書籍タイトル"]
        author = row["著者"]
        highlights = row["ハイライト内容"]
        
        print(f"Generating summary for: {book_title}")
        summary = generate_summary(book_title, author, highlights)
        
        summaries.append({
            "書籍タイトル": book_title,
            "著者": author,
            "要約": summary
        })
    
    # Create a DataFrame from the summaries
    summaries_df = pd.DataFrame(summaries)
    
    # Save the summaries to a CSV file
    user_dir = Path("user_data") / "docs" / user_id
    output_path = user_dir / "BookSummaries.csv"
    summaries_df.to_csv(output_path, index=False)
    
    print(f"Summaries saved to: {output_path}")
    return output_path

def main():
    # Get the user ID from the command line argument
    import sys
    if len(sys.argv) > 1:
        user_id = sys.argv[1]
    else:
        # Default user ID for testing
        user_id = "113701316513048922830"
    
    # Path to the highlights file
    highlights_path = Path("user_data") / "docs" / user_id / "KindleHighlights.csv"
    
    if not highlights_path.exists():
        print(f"Highlights file not found: {highlights_path}")
        return
    
    # Process the highlights file
    output_path = process_highlights_file(highlights_path, user_id)
    print(f"Book summaries generated and saved to: {output_path}")

if __name__ == "__main__":
    main()
