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
| 強気予測 | 天気がよい・イベントがある・週末 |
| 普通予測 | いつも通りの日（デフォルト） |
| 弱気予測 | 雨・連休明けなど |

**③ 製造数を確認する**　商品ごとの製造推奨数が表示されます。スプレッドシートと同じ並び順なので、そのまま転記できます。

---

## 画面の見方

### 週間売上予測カード

1週間分の売上予測が7枚のカードで表示されます。

- **土曜日**：水色のカード・青い曜日文字
- **日曜日・祝日**：薄ピンクのカード・赤い曜日文字
- 大きな数字が税込の予測売上合計です

**カード内の内訳**（色付き3行）：

| 色 | 区分 | 内容 |
|---|---|---|
| 青 | パン | 食パン・惣菜パン・フィリング二次製品の売上 |
| テラコッタ | リベイク | フレンチトースト・ピザ・明太フランスなどの売上 |
| グリーン | サンド | バゲットサンド・パニーノなどの売上 |

**バッジの意味**：祝＝祝日 / 学休＝学校休み / 早大休＝早稲田休み / 昼雨・夕雨＝雨予報

**予測幅**（カード下部のバー）：弱気予測〜強気予測の幅を示します。バーの幅が広いほど予測の不確実性が高い日です。

---

### 製造計画テーブル

3つのセクションに分かれています。

| セクション | 内容 | 生産数の考え方 |
|---|---|---|
| パン製造計画 | 食パン・惣菜パン・フィリング二次製品 | AI予測数を表示 |
| サンドイッチ・パニーノ計画 | バゲットサンド・パニーノなど | AI予測数を表示（直近14日に販売実績のある商品のみ） |
| リベイク二次製品計画 | フレンチトースト・ピザトースト・明太フランスなど | AI予測数を表示（直近14日に販売実績のある商品のみ） |

**フィリング二次製品**（あんこ塩パン・クリーム入りプチなど）はベースパンの生産数に含まれるため、「ベースパンに含む」と表示されます。

**売切↑** — よく売り切れる商品。多めに検討
**廃棄↓** — ロスが出やすい商品。少なめに検討

---

### 週間売上予測サマリー

ページ下部に3区分の週合計カードと積み上げ棒グラフが表示されます。
パン類（青）・リベイク（テラコッタ）・サンドイッチ（グリーン）の色分けで日別の構成が確認できます。

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

サンドイッチ・リベイク品については、**直近14日間に販売実績のある商品のみ**が予測に表示されます。メニュー変更後は自動的に切り替わります。

---

## 予測の自動更新について

このアプリは**毎晩2時（日本時間）に自動でデータ取得・再学習**を行います。

1. Squareレジから前日の売上データを自動取得
2. 学習データセットを更新
3. AIモデルを再学習
4. 翌朝には最新データを反映した予測が表示される

月次のスプレッドシート更新も引き続き行うと、ロス率・売切率の精度が向上します。

---

## 月に1回やること

前月のスプレッドシートが埋まったら、ターミナルで以下を実行します（約5〜10分）。

```
cd ~/kandagawa-bakery
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
| サンドイッチ・リベイクが出てこない | 直近14日間に販売実績がない商品は表示されません。販売再開後、翌日から自動で追加されます |
""")
