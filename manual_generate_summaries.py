import os
import pandas as pd
from pathlib import Path
from book_summary_generator import BookSummaryGenerator
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

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
    
    print(f"Loading highlights from: {highlights_path}")
    df = pd.read_csv(highlights_path)
    print(f"Loaded {len(df)} highlights")
    
    # Count books
    book_count = len(df.groupby(["書籍タイトル", "著者"]))
    print(f"Found {book_count} books to summarize")
    
    # Initialize the BookSummaryGenerator
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("Error: OPENAI_API_KEY not found in environment variables.")
        print("Please make sure you have set the OPENAI_API_KEY in the .env file.")
        return
    
    print("Initializing BookSummaryGenerator...")
    generator = BookSummaryGenerator(api_key=api_key)
    
    # Define a progress callback function
    def update_progress(current, total, book_title):
        progress_percent = (current / total) * 100
        print(f"Progress: {current}/{total} books ({progress_percent:.1f}%) - Current book: {book_title}")
    
    # Generate summaries with progress updates
    print("Generating summaries...")
    output_path = generator.generate_and_save_summaries(df, user_id, update_progress)
    
    print(f"Summaries generated and saved to: {output_path}")
    
    # Verify the output file exists
    if Path(output_path).exists():
        summary_df = pd.read_csv(output_path)
        print(f"Successfully generated {len(summary_df)} book summaries")
        
        # Print the first summary as a sample
        if not summary_df.empty:
            sample_book = summary_df.iloc[0]
            print("\nSample summary:")
            print(f"Book: {sample_book['書籍タイトル']}")
            print(f"Author: {sample_book['著者']}")
            print(f"Summary:\n{sample_book['要約'][:500]}...")
    else:
        print(f"Error: Summary file not found at {output_path}")

if __name__ == "__main__":
    main()
