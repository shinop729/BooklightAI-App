import os
import pandas as pd
from pathlib import Path
from openai import OpenAI
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class BookSummaryGenerator:
    def __init__(self, api_key=None):
        """
        Initialize the BookSummaryGenerator with an OpenAI API key.
        If no API key is provided, it will try to get it from the environment variables.
        """
        if api_key is None:
            api_key = os.getenv("OPENAI_API_KEY")
        
        self.client = OpenAI(api_key=api_key)
    
    def generate_summary(self, book_title, author, highlights):
        """
        Generate a summary for a book using OpenAI's API based on the highlights.
        
        Args:
            book_title (str): The title of the book
            author (str): The author of the book
            highlights (str): The highlights from the book, separated by newlines
            
        Returns:
            str: The generated summary
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
            print(f"Calling OpenAI API for book: {book_title}")
            response = self.client.chat.completions.create(
                model="gpt-3.5-turbo",  # Changed from gpt-4-turbo to gpt-3.5-turbo for faster response
                messages=[
                    {"role": "system", "content": "You are a skilled book summarizer who can extract the key ideas and themes from book highlights and create a comprehensive, insightful summary."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=1000
            )
            summary = response.choices[0].message.content.strip()
            print(f"Successfully generated summary for: {book_title}")
            return summary
        except Exception as e:
            error_msg = f"Error generating summary for {book_title}: {e}"
            print(error_msg)
            # Return a placeholder summary instead of an error message
            return f"この書籍のAIによる要約は生成できませんでした。\n\nエラー詳細: {e}\n\n以下はハイライトの一部です:\n\n{highlights[:500]}..."
    
    def generate_summaries_from_dataframe(self, df, update_progress=None):
        """
        Generate summaries for each book in the DataFrame.
        
        Args:
            df (pandas.DataFrame): DataFrame containing book highlights
            update_progress (callable, optional): Callback function to update progress
                The function should accept three parameters: current, total, and book_title
            
        Returns:
            pandas.DataFrame: DataFrame containing book summaries
        """
        # Group highlights by book title and author
        print("Grouping highlights by book title and author...")
        grouped = df.groupby(["書籍タイトル", "著者"])["ハイライト内容"].apply(lambda x: "\n".join(x)).reset_index()
        total_books = len(grouped)
        print(f"Found {total_books} books to summarize")
        
        # Generate summaries for each book
        summaries = []
        for i, row in grouped.iterrows():
            book_title = row["書籍タイトル"]
            author = row["著者"]
            highlights = row["ハイライト内容"]
            
            # Update progress with current book title if callback is provided
            if update_progress is not None:
                update_progress(i+1, total_books, book_title)
            
            print(f"[{i+1}/{total_books}] Generating summary for: {book_title}")
            summary = self.generate_summary(book_title, author, highlights)
            
            summaries.append({
                "書籍タイトル": book_title,
                "著者": author,
                "要約": summary
            })
        
        # Create a DataFrame from the summaries
        print("All summaries generated successfully!")
        return pd.DataFrame(summaries)
    
    def save_summaries(self, summaries_df, output_path):
        """
        Save the summaries DataFrame to a CSV file.
        
        Args:
            summaries_df (pandas.DataFrame): DataFrame containing book summaries
            output_path (str or Path): Path to save the CSV file
            
        Returns:
            Path: Path to the saved CSV file
        """
        output_path = Path(output_path)
        try:
            # Ensure the directory exists
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Save the file
            summaries_df.to_csv(output_path, index=False)
            print(f"Summaries successfully saved to: {output_path}")
            return output_path
        except Exception as e:
            print(f"Error saving summaries to {output_path}: {e}")
            # Try saving to a fallback location
            fallback_path = Path("BookSummaries_fallback.csv")
            summaries_df.to_csv(fallback_path, index=False)
            print(f"Summaries saved to fallback location: {fallback_path}")
            return fallback_path
    
    def generate_and_save_summaries(self, highlights_df, user_id, update_progress=None):
        """
        Generate summaries for each book in the highlights DataFrame and save them to a CSV file.
        
        Args:
            highlights_df (pandas.DataFrame): DataFrame containing book highlights
            user_id (str): User ID
            update_progress (callable, optional): Callback function to update progress
                The function should accept three parameters: current, total, and book_title
            
        Returns:
            Path: Path to the saved CSV file
        """
        # Generate summaries
        summaries_df = self.generate_summaries_from_dataframe(highlights_df, update_progress)
        
        # Save the summaries to a CSV file
        user_dir = Path("user_data") / "docs" / user_id
        output_path = user_dir / "BookSummaries.csv"
        
        return self.save_summaries(summaries_df, output_path)
