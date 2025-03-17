import pandas as pd
from book_summary_generator import BookSummaryGenerator

def main():
    print("Testing the new book summary approach...")
    
    # Create a sample DataFrame with book highlights
    sample_data = [
        {
            "書籍タイトル": "テスト書籍",
            "著者": "テスト著者",
            "ハイライト内容": "キーワード抽出は書籍の主要概念を特定するための重要な技術です。"
        },
        {
            "書籍タイトル": "テスト書籍",
            "著者": "テスト著者",
            "ハイライト内容": "クラスタリングを使うと多様なトピックをカバーするハイライトを選択できます。"
        },
        {
            "書籍タイトル": "テスト書籍",
            "著者": "テスト著者",
            "ハイライト内容": "選択したハイライトを重要度順に並べ替えることで、最も重要な情報を優先できます。"
        },
        {
            "書籍タイトル": "テスト書籍",
            "著者": "テスト著者",
            "ハイライト内容": "上位のハイライトを連結することで、効果的なサマリを作成できます。"
        },
        {
            "書籍タイトル": "テスト書籍",
            "著者": "テスト著者",
            "ハイライト内容": "自然言語処理技術は、テキスト分析において非常に重要な役割を果たします。"
        },
        {
            "書籍タイトル": "テスト書籍",
            "著者": "テスト著者",
            "ハイライト内容": "機械学習アルゴリズムを使用することで、テキストから意味のあるパターンを抽出できます。"
        },
        {
            "書籍タイトル": "テスト書籍",
            "著者": "テスト著者",
            "ハイライト内容": "効果的なサマリは、原文の主要なポイントを簡潔に伝えるものです。"
        }
    ]

    # Create a DataFrame
    df = pd.DataFrame(sample_data)

    # Initialize the BookSummaryGenerator
    generator = BookSummaryGenerator()

    # Test keyword extraction
    print("\nTesting keyword extraction...")
    all_highlights = "\n".join(df["ハイライト内容"])
    keywords = generator.extract_keywords(all_highlights, num_keywords=5)
    print(f"Extracted keywords: {', '.join(keywords)}")

    # Test clustering
    print("\nTesting clustering...")
    highlights_list = df["ハイライト内容"].tolist()
    cluster_indices = generator.cluster_highlights(highlights_list, n_clusters=3)
    print(f"Selected highlight indices from clusters: {cluster_indices}")
    print("Selected highlights:")
    for idx in cluster_indices:
        print(f"- {highlights_list[idx]}")

    # Test ranking
    print("\nTesting ranking...")
    clustered_highlights = [highlights_list[idx] for idx in cluster_indices]
    ranked_indices = generator.rank_highlights_by_importance(clustered_highlights, keywords)
    print(f"Ranked indices: {ranked_indices}")
    print("Ranked highlights (most important first):")
    for idx in ranked_indices:
        print(f"- {clustered_highlights[idx]}")

    # Test full summary generation
    print("\nGenerating full summary...")
    summaries_df = generator.generate_summaries_from_dataframe(df)
    
    # Print the generated summary
    print("\nGenerated Summary:")
    print(summaries_df["要約"].iloc[0])

    print("\nTest completed successfully!")

if __name__ == "__main__":
    main()
