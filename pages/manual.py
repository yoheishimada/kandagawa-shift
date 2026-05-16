import streamlit as st

st.set_page_config(page_title='使い方マニュアル | 神田川ベーカリー', layout='wide')

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+JP:wght@300;400;500;700&display=swap');
body, * { font-family: 'Noto Sans JP', sans-serif !important; }
h1 { font-size: 1.4rem !important; font-weight: 700 !important; color: #1a1a1a !important; }
h2 { font-size: 1.05rem !important; font-weight: 600 !important;
     text-transform: none !important; letter-spacing: normal !important;
     color: #1a1a1a !important; border-bottom: 1px solid #e8e4de;
     padding-bottom: 0.3rem; margin-top: 1.6rem !important; }
h3 { font-size: 0.9rem !important; font-weight: 600 !important; color: #555 !important; }
p, li { font-size: 0.9rem !important; color: #333 !important; line-height: 1.8 !important; }
table { width: 100%; border-collapse: collapse; font-size: 0.85rem !important; }
th { background: #f5f5f3; padding: 0.5rem 0.8rem; text-align: left;
     border: 1px solid #e8e4de; font-weight: 600; color: #1a1a1a; }
td { padding: 0.5rem 0.8rem; border: 1px solid #e8e4de; color: #333; }
code { background: #f5f5f3; padding: 0.1rem 0.4rem; border-radius: 4px;
       font-size: 0.82rem !important; color: #c0392b; }
pre code { display: block; padding: 0.8rem 1rem; color: #333 !important; }
blockquote { border-left: 3px solid #e8e4de; padding-left: 1rem;
             color: #888 !important; margin: 0.5rem 0; }
</style>
""", unsafe_allow_html=True)

st.markdown("""
# 神田川ベーカリー　売上予測 & 製造数プランナー　使い方マニュアル

> このマニュアルは管理者向けです。困ったときは嶋田に連絡してください。

---

## アプリを開く

スマホ・タブレット・パソコンのブラウザで下のアドレスを開くだけ。インターネットにつながっていればどこからでも使えます。

```
kandagawa-bakery-production.up.railway.app
```

**パスワード：** `Kandagawa0222`

---

## 毎日の使い方

**3ステップで製造計画が完成します。**

**① 日付を選ぶ**　画面左のパネルから、計画を立てたい週の開始日を選びます。

**② モードを選ぶ**

| モード | こんな日に使う |
|---|---|
| 🔴 強気 | 天気がよい・イベントがある・週末 |
| 🟢 普通 | いつも通りの日（デフォルト） |
| 🔵 弱気 | 雨・連休明けなど |

**③ 製造数を確認する**　商品ごとの製造推奨数が表示されます。スプレッドシートと同じ並び順なので、そのまま転記できます。

---

## 画面の見方

**週間カード**　1週間分の売上予測が並びます。数字は税込の予測売上です。
カードの内訳にはパン・リベイク・サンドの区分別金額が表示されます。

バッジの意味：祝＝祝日 / 学休＝学校休み / 早大休＝早稲田休み / 昼雨・夕雨＝雨予報

**製造計画**　3つのセクションに分かれています。

| セクション | 内容 | 生産数の考え方 |
|---|---|---|
| 🍞 パン類 | 食パン・惣菜パン・フィリング二次製品 | AI予測数を表示 |
| 🔥 リベイク二次製品 | フレンチトースト・ピザトースト・明太フランスなど | AI予測数を表示（前日ロスから生産） |
| 🥪 サンドイッチ | バゲットサンド・パニーノなど | AI予測数を表示 |

**フィリング二次製品**（あんこ塩パン・クリーム入りプチなど）はベースパンの生産数に含まれるため、「ベースパンに含む」と表示されます。

🔴 **売切↑** — よく売り切れる商品。多めに検討
🔵 **廃棄↓** — ロスが出やすい商品。少なめに検討

**週間売上サマリー**　ページ下部に3区分の週合計カードと積み上げ棒グラフが表示されます。
パン類（黒）・リベイク（赤）・サンドイッチ（グレー）の色分けで日別の構成が確認できます。

---

## バッファーとは

製造数に上乗せする「安全マージン」のことです。

| 設定 | 意味 |
|---|---|
| 0% | 予測通りに製造 |
| 10% | 予測より1割多く製造（通常はここ） |
| 20% | 予測より2割多く製造（売切を避けたい日） |

---

## ラインナップ基準日

サイドバーに「基準日：〇〇」と表示されます。これは**前日の商品ラインナップ**を参照していることを示します。
予測週を来週に設定しても、基準日は常に昨日です（来週のラインナップはまだ未定のため）。

---

## 月に1回やること

前月のスプレッドシートが埋まったら、ターミナルで以下を実行します（約5分）。

```
python3 parse_sheets.py
python3 build_calibration.py
git add calibration.pkl sheet_actuals.pkl
git commit -m "月次更新"
git push
```

pushすると2〜3分でクラウドに自動反映されます。

---

## 困ったときは

| 症状 | 対処 |
|---|---|
| アプリが開かない | インターネット接続を確認してください |
| パスワードが通らない | 大文字・小文字に注意。コピー&貼り付けが確実です |
| 天気が取れないと表示される | 17日以上先は天気予報が使えません。予測は続きます |
| 数字が古い気がする | ブラウザを再読み込み（⌘R）してください |
| 月次更新後に反映されない | git pushから2〜3分待って再読み込みしてください |
| 商品が予測に出てこない | 販売日数が10日未満の新商品は翌日以降に自動追加されます |
""")
