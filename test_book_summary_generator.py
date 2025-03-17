import pandas as pd
from book_summary_generator import BookSummaryGenerator

# Create a sample DataFrame with book highlights
sample_data = [
    {
        "書籍タイトル": "テスト書籍",
        "著者": "テスト著者",
        "ハイライト内容": "これはテスト書籍のハイライト1です。"
    },
    {
        "書籍タイトル": "テスト書籍",
        "著者": "テスト著者",
        "ハイライト内容": "これはテスト書籍のハイライト2です。"
    },
    {
        "書籍タイトル": "テスト書籍",
        "著者": "テスト著者",
        "ハイライト内容": "これはテスト書籍のハイライト3です。"
    }
]

# Create a DataFrame
df = pd.DataFrame(sample_data)

# Initialize the BookSummaryGenerator
generator = BookSummaryGenerator()

# Generate a summary for the test book
print("Generating summary for test book...")
summaries_df = generator.generate_summaries_from_dataframe(df)

# Print the generated summary
print("\nGenerated Summary:")
print(summaries_df["要約"].iloc[0])

print("\nTest completed successfully!")
