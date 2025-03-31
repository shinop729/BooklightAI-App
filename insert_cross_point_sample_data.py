#!/usr/bin/env python3
# insert_cross_point_sample_data.py
# Cross Point機能をテストするための追加サンプルデータを挿入するスクリプト

import os
import sys
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from datetime import datetime

# プロジェクトのルートディレクトリをPythonパスに追加
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# データベースモデルをインポート
from api.database.models import User, Book, Highlight

print("Cross Point機能テスト用サンプルデータ挿入スクリプトを開始します...")

# データベースに接続
db_path = './booklight.db'
engine = create_engine(f'sqlite:///{db_path}')
Session = sessionmaker(bind=engine)
session = Session()

try:
    # 開発ユーザーを取得
    dev_user = session.query(User).filter(User.email == 'dev@example.com').first()
    if not dev_user:
        print("開発ユーザーが見つかりません。先に insert_sample_data.py を実行してください。")
        sys.exit(1)
    
    print(f"開発ユーザーを使用します: ID={dev_user.id}")

    # 追加のサンプル書籍データ
    additional_books = [
        {"title": "経済学の思考法", "author": "トーマス・ソウェル"},
        {"title": "戦略論", "author": "マイケル・ポーター"},
        {"title": "ノーコード革命", "author": "ライアン・ホリデイ"},
        {"title": "FACTFULNESS", "author": "ハンス・ロスリング"},
        {"title": "影響力の武器", "author": "ロバート・チャルディーニ"}
    ]

    # 追加のサンプルハイライトデータ（Cross Point機能のテスト用に関連性のあるものを含む）
    additional_highlights = [
        # 経済学の思考法
        {"book_idx": 0, "content": "農業というものは、他の産業に比べて需要が本来あまり伸びないという特性を持っている。例えば収入が２倍になったからといって、人々はジャガイモやニンジンをいままでの２倍食べるようになるだろうか。農業の弱点というのは、実にここである。人間の胃袋の大きさに限度があって、どう努力したところで人間は１日１トンのジャガイモを食べるようにはならないという現実が、その需要を固定的なものにしているのである。", "location": "1234"},
        {"book_idx": 0, "content": "農業と商工業の対決においては、農業の側がほとんど伸びない需要と中途半端な速度で伸ばせる供給という、最悪のコンビネーションから成り立っているのに対し、商工業の側は、供給の伸びの速度が速すぎるという不利を抱えながらも、ゴムのように伸縮自在な需要がその不利をカバーしている。", "location": "1567"},
        {"book_idx": 0, "content": "江戸が行政の中心地になったことで、当然それを支える人口がこの都市に集中することになったが、それらの人々は本質的に非生産者である。そして江戸という町の最大の泣き所は、その膨大な人々のための物資を供給する場所が近くになかったこと", "location": "2345"},
        
        # 戦略論
        {"book_idx": 1, "content": "そもそも第二次世界大戦自体が、石炭文明から石油文明への過渡期を象徴する世界史的な出来事であったと言えるだろう。第二次世界大戦においては、しばしばその戦略行動や戦争目的そのものが、「石油の確保」というテーマを巡って動いていたが、それは第一次世界大戦の時には見られなかったものである。", "location": "890"},
        {"book_idx": 1, "content": "そして米国の場合を眺めると、この石油文明への先導役を務めたのは何と言っても自動車である。これは米国ではすでに１９２０年代から始まっていたのだが、世界的に見るとこの動きもやはり第二次世界大戦がちょうど過渡期に当たっており、それを最も象徴するのがドイツのフォルクスワーゲンだろう。 \u3000そもそもこれはヒトラーが「一家に１台の自動車を」という国民車（＝フォルクスワーゲン） の構想を政策として打ち出したことから生まれたもので、その名残りが現在でも会社名に残っているのである。", "location": "1023"},
        {"book_idx": 1, "content": "産業としての機動力の差にある。つまり農業は、ほとんど固定化された需要と中途半端な速度で増やせる供給という、最悪のコンビネーションで成り立っており、迅速に攻め口を転換できる商工業に大きな差をつけられてしまうからである。", "location": "1456"},
        
        # ノーコード革命
        {"book_idx": 2, "content": "・一方商工業の側にも弱点があり、それは需要がすぐに飽和してしまうことである。これは技術革新によって別の市場を新しく作ることを繰り返していく以外に停滞を脱する方法がない。", "location": "345"},
        {"book_idx": 2, "content": "産業の基本となるエネルギーと鉄鋼の基盤を作り上げ、それがある程度達成された時点ではじめて、それらを他の産業にも分けていく。こういう資源の重点集中投入戦術が「傾斜生産方式」である。", "location": "678"},
        {"book_idx": 2, "content": "急遽、ポーランドの穀倉地帯などをはじめとするバルト海沿岸が新たな穀物供給先としてクローズアップされてきたのだが、これこそオランダにとっての一大チャンスだった。つまりオランダはそれを運ぶためのバルト海貿易を一手に引き受けていたためその穀物供給の輸送を独占することになり、そして競争相手がいないので利益も独占できたのである。つまりこれこそまさにオランダ繁栄の最大の理由だった。", "location": "912"},
        
        # FACTFULNESS
        {"book_idx": 3, "content": "ところが米国が一つの国である限り、貿易体制をいずれか一方に決めねばならず、これはどうにも妥協のできないものとなってしまった。それならばいっそ二つに分かれてしまえばよいではないかというわけで、南部が分離独立の方向に向かい始めたのだが、北部がそれを一顧だにせず、結局北部の工業文明と南部の農業文明の激突に発展し、北部が圧倒的な「国力差」をもってその試みを粉砕したというのが、南北戦争の本質である。", "location": "2341"},
        {"book_idx": 3, "content": "・近代になると貿易の世界、というより経済世界全体が「商業」から「産業」の世界へ移行したが、それは貿易においても中継貿易で生きるオランダやイスラムなどのような存在を駆逐し、英国をはじめとする、国内の生産品を官民一体となって強引に売り込む産業国家を貿易の主役としていった。", "location": "3456"},
        {"book_idx": 3, "content": "何らかの理由でこの設備投資が急激に縮小して固まってしまった時には、政府がそれにかわって「公共投資」という形で外から強制的に資金を注いで回復させねばならないというのが、ケインズ経済学の主張である。", "location": "4567"},
        
        # 影響力の武器
        {"book_idx": 4, "content": "しかし彼らの主張の致命的欠陥は、その肝心の神の手が「縮小均衡」という概念、つまり汲み上げポンプなどが低い運転状態に陥ったまま一個の均衡状態を作ってしまう問題には本質的に無力だ、という点を見落としていたことである。つまり神の手は確かに各運転状態の枠内でそれなりの均衡状態を作り上げることはきちんとできるが、逆に言えばそれが限度であり、運転状態自体を高いレベルに引き上げたりすることは、本来その能力の中には含まれていないのである。", "location": "789"},
        {"book_idx": 4, "content": "う。 ケインズ政策の場合、泣き所がどこに出てくるかと言えば、それはこの政策がとかく財政赤字とインフレの温床になりやすいことである。", "location": "1234"},
        {"book_idx": 4, "content": "つまり英国は資本主義のトップを走っていて国内に豊富な資金を貯め込んでいるにもかかわらず、国内にはその投資先がないことになる。そこでそれらの投資先はもっぱら海外へ求められることになった。 19 世紀だとその代表例は米国の国債や州債であり、英国の投資家たちにとっては英国企業の債券のかわりにこれらの債券を買うことが「投資」だったのである。 \u3000逆に当時の発展途上国であった米国の立場からすれば、工業化のためにはいくら金があっても足りない状態であり、米国の大陸横断鉄道などの資金にしても、そうした英国の投資家たちが米国の州債を買ってくれたことで調達が可能になったのである。", "location": "2345"}
    ]

    # 書籍データの挿入
    books = []
    new_book_count = 0
    
    # 既存の書籍を取得
    existing_books = session.query(Book).filter(Book.user_id == dev_user.id).all()
    existing_book_titles = [book.title for book in existing_books]
    
    for book_data in additional_books:
        # 既存の書籍を確認
        if book_data["title"] in existing_book_titles:
            book = session.query(Book).filter(
                Book.title == book_data["title"],
                Book.user_id == dev_user.id
            ).first()
        else:
            book = Book(
                title=book_data["title"],
                author=book_data["author"],
                user_id=dev_user.id
            )
            session.add(book)
            session.commit()
            new_book_count += 1
        
        books.append(book)
    
    print(f"書籍データを挿入しました: {new_book_count}冊の新規書籍")

    # ハイライトデータの挿入
    new_highlight_count = 0
    
    for highlight_data in additional_highlights:
        book = books[highlight_data["book_idx"]]
        
        # 既存のハイライトを確認
        highlight = session.query(Highlight).filter(
            Highlight.content == highlight_data["content"],
            Highlight.book_id == book.id,
            Highlight.user_id == dev_user.id
        ).first()
        
        if not highlight:
            highlight = Highlight(
                content=highlight_data["content"],
                location=highlight_data["location"],
                user_id=dev_user.id,
                book_id=book.id,
                created_at=datetime.utcnow()
            )
            session.add(highlight)
            new_highlight_count += 1

    session.commit()
    print(f"ハイライトデータを挿入しました: {new_highlight_count}件の新規ハイライト")

    # 確認のためにデータを取得して表示
    total_books = session.query(Book).filter(Book.user_id == dev_user.id).count()
    total_highlights = session.query(Highlight).filter(Highlight.user_id == dev_user.id).count()
    
    print(f"\n開発ユーザー（ID={dev_user.id}）のデータ:")
    print(f"- 書籍数: {total_books}冊")
    print(f"- ハイライト数: {total_highlights}件")
    
    print("\nCross Point機能テスト用サンプルデータの挿入が完了しました。")
    print("ブラウザを更新して、Cross Point機能を確認してください。")

except Exception as e:
    session.rollback()
    print(f"エラーが発生しました: {e}")
    import traceback
    traceback.print_exc()
finally:
    session.close()
