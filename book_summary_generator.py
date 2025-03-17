import os
import pandas as pd
import numpy as np
from pathlib import Path
from openai import OpenAI
from dotenv import load_dotenv
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.cluster import KMeans
from sklearn.metrics.pairwise import cosine_similarity

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
    
    def extract_keywords(self, text, num_keywords=10):
        """
        Extract key concepts/keywords from the text using OpenAI API.
        
        Args:
            text (str): The text to extract keywords from
            num_keywords (int): The number of keywords to extract
            
        Returns:
            list: A list of extracted keywords
        """
        prompt = f"""
        Extract the {num_keywords} most important keywords or key concepts from the following text.
        Return only the keywords as a comma-separated list, without any additional text.
        
        Text:
        {text}
        """
        
        try:
            response = self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are a helpful assistant that extracts key concepts and keywords from text."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=200
            )
            keywords = response.choices[0].message.content.strip()
            return [k.strip() for k in keywords.split(',')]
        except Exception as e:
            print(f"Error extracting keywords: {e}")
            return []
    
    def cluster_highlights(self, highlights, n_clusters=5):
        """
        Cluster highlights to ensure diversity of topics.
        
        Args:
            highlights (list): List of highlight texts
            n_clusters (int): Number of clusters to create
            
        Returns:
            list: Indices of selected highlights from each cluster
        """
        if len(highlights) <= n_clusters:
            return list(range(len(highlights)))
        
        # Create TF-IDF vectors
        vectorizer = TfidfVectorizer(max_features=1000, stop_words='english')
        tfidf_matrix = vectorizer.fit_transform(highlights)
        
        # Adjust number of clusters if we have fewer highlights than requested clusters
        actual_n_clusters = min(n_clusters, len(highlights))
        
        # Apply KMeans clustering
        kmeans = KMeans(n_clusters=actual_n_clusters, random_state=42)
        clusters = kmeans.fit_predict(tfidf_matrix)
        
        # Get cluster centers
        centers = kmeans.cluster_centers_
        
        # Select the highlight closest to each cluster center
        selected_indices = []
        for i in range(actual_n_clusters):
            # Get highlights in this cluster
            cluster_indices = [idx for idx, cluster in enumerate(clusters) if cluster == i]
            
            if cluster_indices:
                # Get vectors for highlights in this cluster
                cluster_vectors = tfidf_matrix[cluster_indices]
                
                # Calculate similarity to cluster center
                similarities = cosine_similarity(cluster_vectors, centers[i].reshape(1, -1))
                
                # Get the index of the highlight closest to the center
                closest_idx = cluster_indices[np.argmax(similarities)]
                selected_indices.append(closest_idx)
        
        return selected_indices
    
    def rank_highlights_by_importance(self, highlights, keywords):
        """
        Rank highlights by their importance based on keyword presence and other factors.
        
        Args:
            highlights (list): List of highlight texts
            keywords (list): List of important keywords
            
        Returns:
            list: Indices of highlights sorted by importance (most important first)
        """
        scores = []
        
        for i, highlight in enumerate(highlights):
            # Count keyword occurrences
            keyword_count = sum(1 for keyword in keywords if keyword.lower() in highlight.lower())
            
            # Consider highlight length (normalize to avoid bias towards very long highlights)
            length_score = min(len(highlight) / 200, 1.0)  # Cap at 1.0 for highlights longer than 200 chars
            
            # Calculate final score (can adjust weights as needed)
            final_score = (keyword_count * 0.7) + (length_score * 0.3)
            scores.append((i, final_score))
        
        # Sort by score in descending order
        sorted_indices = [idx for idx, score in sorted(scores, key=lambda x: x[1], reverse=True)]
        return sorted_indices
    
    def generate_summary_from_highlights(self, book_title, author, highlights, max_highlights=10):
        """
        Generate a summary by selecting and concatenating important highlights.
        
        Args:
            book_title (str): The title of the book
            author (str): The author of the book
            highlights (list): List of highlight texts
            max_highlights (int): Maximum number of highlights to include
            
        Returns:
            str: The generated summary
        """
        if not highlights:
            return f"No highlights available for {book_title} by {author}."
        
        # Join highlights for keyword extraction
        all_text = "\n".join(highlights)
        
        # Extract keywords
        keywords = self.extract_keywords(all_text)
        print(f"Extracted keywords: {', '.join(keywords)}")
        
        # Cluster highlights to ensure diversity
        cluster_indices = self.cluster_highlights(highlights)
        clustered_highlights = [highlights[idx] for idx in cluster_indices]
        
        # Rank the clustered highlights by importance
        ranked_indices = self.rank_highlights_by_importance(clustered_highlights, keywords)
        
        # Select top highlights
        top_indices = ranked_indices[:max_highlights]
        selected_highlights = [clustered_highlights[idx] for idx in top_indices]
        
        # Create summary by concatenating selected highlights
        summary = f"# {book_title}\n## by {author}\n\n"
        summary += "## Key Concepts\n"
        summary += ", ".join(keywords) + "\n\n"
        summary += "## Summary\n"
        
        for i, highlight in enumerate(selected_highlights, 1):
            summary += f"{i}. {highlight}\n\n"
        
        return summary
    
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
        # Convert highlights string to list
        highlight_list = highlights.split('\n')
        highlight_list = [h.strip() for h in highlight_list if h.strip()]
        
        try:
            print(f"Generating summary for book: {book_title}")
            
            # Use the new approach to generate summary from highlights
            summary = self.generate_summary_from_highlights(book_title, author, highlight_list)
            
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
