---
title: 福祉業界の入居相談をAIで自動化してみた【Python×Streamlit×OpenAI API×Google Sheets】
tags:
  - Python
  - Streamlit
  - OpenAI
  - 生成AI
  - 福祉DX
---

## 1. はじめに 🏠

障害者グループホームへの入居相談は、現場スタッフにとって想像以上に負担の大きい業務です。

- 電話やメールで問い合わせが入るたびに、同じ項目を一から聞き直す
- ヒアリング内容を手書きや口頭でメモし、別途スプレッドシートに転記する
- 担当者が不在だと折り返しが遅れ、相談者を不安にさせてしまう

こうした「聞く→記録する→共有する」の繰り返し作業は、スタッフのリソースを大きく消耗させます。特に小規模な福祉事業所では、相談対応と施設運営を兼務するケースも多く、タイムラグや漏れが発生しやすい状況です。

**「初回ヒアリングだけでも自動化できないか？」** という発想から、AIを使った入居相談受付システムを作りました。

---

## 2. 作ったもの 🤖

### デモ

👉 [https://group-home-consultation-ai-demo.streamlit.app](https://group-home-consultation-ai-demo.streamlit.app)

### GitHub

👉 [https://github.com/lifectai/group-home-consultation-ai](https://github.com/lifectai/group-home-consultation-ai)

### アプリの流れ

1. 相談者がWebフォームにアクセス
2. 名前・性別・電話番号・相談内容を入力
3. AIが順番に質問しながら必要事項（障害種別・支援区分・希望入居時期など）をヒアリング
4. 相談終了時に**AIが自動で内容を要約**
5. Google Sheetsに自動保存 → LINEで担当スタッフに通知

スタッフが対応する前に、必要な情報がすべて整理された状態でスプレッドシートに入っています。📋

---

## 3. システム構成 ⚙️

| 技術 | 用途 |
|------|------|
| Python | バックエンド全般 |
| Streamlit | WebアプリUI |
| OpenAI API（gpt-4o-mini） | AIヒアリング・要約・情報抽出 |
| Google Sheets（gspread） | 相談記録の保存・管理 |
| LINE Messaging API | スタッフへのリアルタイム通知 |
| pytz | タイムゾーン処理（Asia/Tokyo） |

シンプルに `app.py` 1ファイルで完結する構成にしました。Streamlit Cloudにデプロイしているため、サーバー管理も不要です。

---

## 4. 実装のポイント 💡

### Google Sheets 連携

Streamlit Secretsに認証情報を持たせ、`@st.cache_resource` でクライアントをキャッシュすることで、リロードのたびに再接続しないようにしています。

```python
@st.cache_resource
def get_gsheet_client():
    creds_dict = dict(st.secrets["gcp_service_account"])
    creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
    return gspread.authorize(creds)
```

シートが存在しない場合は自動作成し、ヘッダー行もコードで定義しているため、初回セットアップが楽です。

### AIヒアリングの設計

会話のブレを防ぐために、System Promptで「①障害種別 → ②支援区分 → ...」の順番を厳密に指定しています。**「未回答の最小番号の項目だけを聞く」** というルールを明文化することで、AIが項目を飛ばしたり逆戻りしたりするのを抑制しました。

```python
system_prompt = """
【絶対に守るべきルール】
・質問は必ず以下の①〜⑧の順番通りに行う
・①が未回答なら①を聞く。②が未回答なら②を聞く。この順番を絶対に飛ばさない
・1回の発言で質問は1つだけ
"""
```

また、全項目が揃ったタイミングで「ご入力いただいた内容を担当者に共有します」という特定の文言をAIに出力させることで、相談終了のトリガーにしています。

### AI要約・情報抽出

会話ログ全体をGPTに渡し、2種類の処理を実行しています。

- `extract_consultation_info`：JSON形式で9項目を構造化抽出
- `generate_ai_summary`：担当者が電話対応しやすい要約文を生成

```python
# JSON抽出のプロンプト（一部）
prompt = f"""
以下の会話ログから情報を抽出し、必ずJSON形式で返してください。

{{
  "障害種別": "",
  "障害支援区分": "",
  ...
}}
不明な場合は「未確認」と書く
"""
```

---

## 5. つまずいたポイント 🔧

### ① タイムゾーン問題

`datetime.now()` をそのまま使うとUTC（協定世界時）になり、9時間ずれた時刻が記録されてしまいます。`pytz` を使って明示的にJSTに変換することで解決しました。

```python
# NG: UTC時刻になってしまう
datetime.now().strftime("%Y-%m-%d %H:%M:%S")

# OK: JSTに変換
datetime.now(pytz.timezone("Asia/Tokyo")).strftime("%Y-%m-%d %H:%M:%S")
```

受付番号の生成にも同じ問題があったので、両方まとめて修正しました。

### ② 電話番号の先頭0が消える問題

Google Sheetsに `090xxxxxxxx` を保存すると、数値として解釈されて `90xxxxxxxx` になってしまいます。

解決策は、先頭にシングルクォートを付けて文字列として保存することです。

```python
# 先頭に ' を付けることで文字列として保存される
"'" + str(phone)
```

さらに `append_row` の引数に `value_input_option="USER_ENTERED"` を指定することで、Sheetsの書式を強制的にテキストとして扱わせています。

```python
ws.append_row(row, value_input_option="USER_ENTERED")
```

---

## 6. 今後の展望 🚀

- **多言語対応**：外国籍の利用者向けに英語・中国語での対応を追加したい
- **施設マッチング精度向上**：ヒアリング内容をもとに、より精度の高い施設候補を提示する機能
- **音声入力対応**：文字入力が難しい方へのアクセシビリティ向上
- **管理画面の整備**：スタッフが相談一覧をアプリ上で確認・対応できる機能

---

## 7. おわりに 🙏

「毎回同じことを電話で聞いている」「メモが散らばって引き継ぎが大変」という現場の課題が、コードにすると意外とシンプルに解決できることがわかりました。

OpenAI APIとGoogle Sheetsを組み合わせるだけで、ヒアリング・記録・通知の一連の流れが自動化できます。特定業種向けの業務自動化は、生成AIが最も力を発揮できる領域の一つだと実感しています。

福祉・介護・医療など、同じような繰り返し業務を抱えている現場の方の参考になれば嬉しいです。フィードバックや改善提案もお待ちしています！

---

**GitHub**: https://github.com/lifectai/group-home-consultation-ai
**デモ**: https://group-home-consultation-ai-demo.streamlit.app
