// テスト用のダミーデータ
const dummyHighlights = [
  {
    book_title: "人工知能と社会の未来",
    author: "山田太郎",
    content: "人工知能は単なるツールではなく、社会を根本から変革する可能性を秘めている。",
    location: "位置No. 142-143"
  },
  {
    book_title: "人工知能と社会の未来",
    author: "山田太郎",
    content: "AIの発展には倫理的な議論が不可欠であり、技術開発と並行して社会的合意形成を進める必要がある。",
    location: "位置No. 156-157"
  },
  {
    book_title: "人工知能と社会の未来",
    author: "山田太郎",
    content: "データの偏りがAIの判断にバイアスをもたらす可能性は、最も重要な技術的・社会的課題の一つである。",
    location: "位置No. 201-202"
  },
  {
    book_title: "効率的な学習法",
    author: "佐藤花子",
    content: "アクティブラーニングは単に「活動的な学習」ではなく、学習者が能動的に考え、知識を構築するプロセスである。",
    location: "位置No. 78-79"
  },
  {
    book_title: "効率的な学習法",
    author: "佐藤花子",
    content: "記憶の定着には、間隔をあけた復習が効果的である。一度に長時間学習するよりも、短時間の学習を分散させる方が記憶に残りやすい。",
    location: "位置No. 103-104"
  }
];

// Kindle Web Readerのページ構造をシミュレートするHTML
const dummyKindlePageHTML = `
<div class="kindle-reader-container">
  <div class="reader-header">
    <h1 class="reader-title">人工知能と社会の未来</h1>
    <h2 class="reader-author">山田太郎</h2>
  </div>
  <div class="reader-content">
    <div class="kp-notebook-highlight" data-location="位置No. 142-143">
      <div class="kp-notebook-highlight-text">人工知能は単なるツールではなく、社会を根本から変革する可能性を秘めている。</div>
    </div>
    <div class="kp-notebook-highlight" data-location="位置No. 156-157">
      <div class="kp-notebook-highlight-text">AIの発展には倫理的な議論が不可欠であり、技術開発と並行して社会的合意形成を進める必要がある。</div>
    </div>
    <div class="kp-notebook-highlight" data-location="位置No. 201-202">
      <div class="kp-notebook-highlight-text">データの偏りがAIの判断にバイアスをもたらす可能性は、最も重要な技術的・社会的課題の一つである。</div>
    </div>
  </div>
</div>
`;

// エクステンションのテスト用関数
function simulateHighlightCollection() {
  return {
    success: true,
    data: {
      book_title: "人工知能と社会の未来",
      author: "山田太郎",
      highlights: dummyHighlights.filter(h => h.book_title === "人工知能と社会の未来")
    }
  };
}

function simulateApiResponse(highlights) {
  return {
    success: true,
    message: `${highlights.length}件のハイライトを保存しました`,
    total_highlights: 5
  };
}

// エクスポート
if (typeof module !== 'undefined') {
  module.exports = {
    dummyHighlights,
    dummyKindlePageHTML,
    simulateHighlightCollection,
    simulateApiResponse
  };
}
