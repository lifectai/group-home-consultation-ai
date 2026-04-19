# 福祉業界の入居相談をAIで自動化してみた【Python x Streamlit x OpenAI API x Google Sheets】

**タグ:** Python / Streamlit / OpenAI / 生成AI / 福祉DX

---

## 1. はじめに

福祉業界で働きながら、生成AIエンジニアコースを受講してアプリを作りました。現場の課題を自分で解決したくて。

障害者グループホームへの入居相談は、現場スタッフにとって想像以上に負担の大きい業務です。

- 電話やメールで問い合わせが入るたびに、同じ項目を一から聞き直す
- ヒアリング内容を手書きや口頭でメモし、別途スプレッドシートに転記する
- 担当者が不在だと折り返しが遅れ、相談者を不安にさせてしまう
- 職員によって聞く内容がバラバラで、引き継ぎが困難になる

そこで作ったのが、AIを使った入居相談受付システムです。

---

## 2. 作ったもの

**デモURL**
https://group-home-consultation-ai-demo.streamlit.app

**GitHub**
https://github.com/lifectai/group-home-consultation-ai

**アプリの流れ**

1. 相談者がWebフォームにアクセス
2. 名前・性別・電話番号・相談内容を入力
3. AIが順番に質問しながら必要事項をヒアリング
4. 相談終了時にAIが自動で内容を要約・構造化
5. Google Sheetsに自動保存 → LINEで担当スタッフに通知

---

## 3. システム構成

| 技術 | 用途 |
|------|------|
| Python | バックエンド全般 |
| Streamlit | WebアプリUI |
| OpenAI API (gpt-4o-mini) | AIヒアリング・要約・情報抽出 |
| Google Sheets (gspread) | 相談記録の保存・管理 |
| LINE Messaging API | スタッフへのリアルタイム通知 |
| pytz | タイムゾーン処理（Asia/Tokyo） |

`app.py` 1ファイルで完結する構成にしました。

---

## 4. なぜこの技術を選んだか

### Streamlit を選んだ理由
- 受講していた生成AIエンジニアコースで学んだ技術で実践的に活かせると判断した
- Pythonだけで完結するため、フロントエンドの知識がなくてもWebアプリが作れる
- Streamlit Cloudを使えばサーバー管理不要でデプロイが簡単

### OpenAI API を選んだ理由
- 信頼性が高く、商用利用での実績も豊富
- 自然言語で相談内容を理解して返答できるため、複雑な分岐ロジックを自前で書く必要がない
- ルールベースのチャットボットでは対応しきれない幅広いケースにも柔軟に対応できる

### Google Sheets を選んだ理由
- 担当者がExcelライクに操作できるため、学習コストが不要
- APIが無料で使えるためランニングコストを抑えられる
- 現場への導入障壁が低い

---

## 5. 実装のポイント

このアプリで生成AIを使っている箇所は3つです。

- **① AIヒアリング（会話）**：gpt-4o-mini が相談者と自然な会話をしながら8項目を順番に引き出す
- **② AI要約生成**：会話ログ全体をGPTに渡してスタッフ向けの要約文を自動生成
- **③ 情報構造化抽出**：会話から障害種別・支援区分などをJSON形式で自動抽出

### Google Sheets 連携

```python
@st.cache_resource
def get_gsheet_client():
    creds_dict = dict(st.secrets["gcp_service_account"])
    creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
    return gspread.authorize(creds)
```

### AIヒアリングの設計

System Promptで質問の順番を厳密に指定しています。

```
【絶対に守るべきルール】
・質問は必ず1〜8の順番通りに行う
・1が未回答なら1を聞く。この順番を絶対に飛ばさない
・1回の発言で質問は1つだけ
```

### AI要約・情報抽出

```python
prompt = f"""
以下の会話ログから情報を抽出し、必ずJSON形式で返してください。
{{
  "障害種別": "",
  "障害支援区分": "",
  "生活状況": "",
  "日常生活のケア": "",
  "行動障害": "",
  "希望入居時期": "",
  "家賃上限": "",
  "こだわり条件": "",
  "希望エリア": ""
}}
不明な場合は「未確認」と書く
"""
```

### AIに空室情報を答えさせない設計

```
【禁止事項】
・空室状況・入居可否・費用の具体的な金額については一切回答しないこと
・「空きがあります」などの断定表現を使わないこと
・不確かな情報は「担当者からご連絡します」と伝えること
```

AIの役割は「情報を集める」こと。「情報を与える」ことではない。

---

## 6. つまずいたポイント（全記録）

### カテゴリー1：タイムゾーンと環境設定

**（1-1）日本時間（JST）とのズレ**

```python
# NG: UTC時刻になってしまう
datetime.now().strftime("%Y-%m-%d %H:%M:%S")

# OK: JSTに変換
datetime.now(pytz.timezone("Asia/Tokyo")).strftime("%Y-%m-%d %H:%M:%S")
```

**（1-2）ライブラリ不足によるデプロイエラー**

```
# requirements.txtに追加
pytz
gspread
google-auth
```

### カテゴリー2：データ保存とGoogle Sheets連携

**（2-1）電話番号の先頭「0」が消える**

```python
# 先頭に ' を付けることで文字列として保存される
"'" + str(phone)
ws.append_row(row, value_input_option="USER_ENTERED")
```

**（2-2）シートが見つからないエラー**

```python
# NG: シート名で取得（名前変更に弱い）
ws = sh.worksheet("相談一覧")

# OK: インデックスで取得
ws = sh.get_worksheet(0)
```

**（2-3）データが保存されない**：「相談を終了する」ボタンを追加してfinishステップへ遷移させて解決。

### カテゴリー3：APIと認証

**（3-1）Google認証情報のパス問題**：Streamlit Secretsに統一。ローカルも `.streamlit/secrets.toml` で同形式に。

**（3-2）OpenAI APIキーの無効**：ローカルの.envとクラウドのSecretsでキーが不一致。両方更新して解決。

**（3-3）APIのクレジット不足**：残高0ドルでエラー。Billing画面からチャージして解決。

**（3-4）レート制限（429エラー）**：リトライ処理を追加。エラー時はユーザーに「少々お待ちください」と表示。

**（3-5）通信タイムアウト**：timeoutパラメータを設定して再試行するよう対処。

### カテゴリー4：Gitとセキュリティ

**（4-1）APIキーをgitにコミット**

```
# .gitignoreに必ず追加
.env
secrets.toml
*.json
```

GitHubにpushした瞬間OpenAIから警告メール。git-filter-repoで履歴から削除して解決。

**（4-2）リポジトリの未初期化**：`git init` で初期化しリモートリポジトリを追加して解決。

**（4-3）Claude Code APIエラー500**：サーバー側の一時障害でClaude Code経由のgit pushが不可。ターミナルから手動でgit操作して対処。

```bash
git add .
git commit -m "修正内容"
git push origin main
```

### カテゴリー5：StreamlitのUIと仕様

**（5-1）セッションステートの管理**

```python
# NG: ページ再実行のたびにリセットされる
messages = []

# OK: session_stateで永続化
if "messages" not in st.session_state:
    st.session_state.messages = []
```

**（5-2）意図しない単語変換**：Chromeの自動翻訳で「入居」が「滞在」に。

```python
st.markdown('<meta name="google" content="notranslate">', unsafe_allow_html=True)
```

**（5-3）チャット画面が自動スクロールしない**

```python
st.markdown(
    "<script>window.scrollTo(0, document.body.scrollHeight);</script>",
    unsafe_allow_html=True
)
```

**（5-4）ログの重複表示**：`if not any(...)` で同内容チェックしてから追加するよう修正。

### カテゴリー6：コーディングミス

**（6-1）変数のスコープエラー（NameError）**

```python
# NG
if condition:
    ai_summary = generate_ai_summary(...)
print(ai_summary)  # NameError!

# OK
ai_summary = ""
if condition:
    ai_summary = generate_ai_summary(...)
```

**（6-2）インデントの崩れ**：VSCodeのフォーマット機能（Shift+Alt+F）で解消。

---

## 7. 今後の展望

- **施設マッチング精度向上：** RAGを活用してヒアリング内容をもとに精度の高い施設候補を提示
- **管理画面の整備：** スタッフが相談一覧をアプリ上で確認・対応できる機能
- **マーケティング分析：** 相談内容の割合を可視化して営業戦略に活用
- **FAQ自動生成：** 蓄積した相談ログからよくある質問を自動生成してHPに掲載
- **多言語対応：** 外国籍の利用者向けに英語・中国語での対応を追加
- **音声入力対応：** 文字入力が難しい方へのアクセシビリティ向上
- **Dropbox・Excel連携：** 実務環境への完全移行

---

## 8. おわりに

このシステムを作って一番感じたのは、**AIを使って何を作るかより、現場のどの課題を解決するかが重要だ**ということです。技術は手段であって目的ではない。現場を知っているからこそ作れるものがある、と改めて実感しました。

福祉・介護・医療など、同じような繰り返し業務を抱えている現場の方の参考になれば嬉しいです。

**GitHub:** https://github.com/lifectai/group-home-consultation-ai
**デモ:** https://group-home-consultation-ai-demo.streamlit.app
