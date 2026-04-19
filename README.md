# グループホーム入居相談AIシステム

障害者グループホームへの入居相談を自動化するWebアプリです。
AIが相談者と自然な会話をしながら必要事項をヒアリングし、Google Sheetsへの保存とLINE通知まで一気通貫で自動化します。

---

## デモ・本番URL

| 種別 | URL |
|---|---|
| デモ | https://group-home-consultation-ai-demo.streamlit.app |
| 本番 | https://group-home-consultation-ai-hnfappzescdepzmygjdufma.streamlit.app |

---

## システム構成

| 技術 | 用途 |
|---|---|
| Python | バックエンド全般 |
| Streamlit | WebアプリUI |
| OpenAI API (gpt-4o-mini) | AIヒアリング・要約・情報抽出 |
| Google Sheets (gspread) | 相談記録の保存・管理 |
| LINE Messaging API | スタッフへのリアルタイム通知 |
| pytz | タイムゾーン処理（Asia/Tokyo） |

`app.py` 1ファイルで完結する構成です。Streamlit Cloudにデプロイしているため、サーバー管理不要で運用できます。

---

## アーキテクチャ

```
相談者（HP / QRコード）
        ↓
Streamlit Webアプリ（マルチステップ・フォーム）
        ↓
OpenAI API（gpt-4o-mini）
 ├─ ① ヒアリングエージェント（逐次質問）
 ├─ ② 要約生成
 └─ ③ JSON構造化（障がい名・生活状況・必要支援・希望エリア）
        ↓
 ┌──────────────────────┐
 ↓                      ↓
Google Sheets        LINE Messaging API
（gspread API）       （担当職員へ即時通知）
 └──────────────────────┘
        ↓
現場スタッフ（整理済み情報で折り返し対応）
```

---

## 主な機能

- **AIヒアリング**：障害種別・支援区分・生活状況など8項目を自然な会話で引き出す
- **AI要約生成**：会話ログ全体をもとにスタッフ向けの読みやすい要約文を自動生成
- **JSON構造化抽出**：会話から必要情報をJSON形式で自動抽出
- **Google Sheets保存**：相談記録をリアルタイムで自動保存
- **LINE通知**：相談完了と同時に担当職員のLINEへ即時通知

---

## セットアップ

### 1. リポジトリをクローン

```bash
git clone https://github.com/lifectai/group-home-consultation-ai.git
cd group-home-consultation-ai
```

### 2. ライブラリをインストール

```bash
pip install -r requirements.txt
```

### 3. Secretsを設定

`.streamlit/secrets.toml` を作成し以下を入力します。

```toml
OPENAI_API_KEY = "sk-..."
LINE_CHANNEL_ACCESS_TOKEN = "..."
LINE_USER_ID = "U..."

[gcp_service_account]
type = "service_account"
project_id = "..."
private_key_id = "..."
private_key = "-----BEGIN RSA PRIVATE KEY-----\n..."
client_email = "...@....iam.gserviceaccount.com"
```

### 4. 起動

```bash
streamlit run app.py
```

---

## 開発者

**石破昇悟 / Lifect**

名古屋で組織マネジメントに携わりながら、現場課題をAIで解決するアプリを開発しています。
DMM生成AIエンジニアコース修了（2025年3月）／オープンバッジ取得。

- GitHub：https://github.com/lifectai
- Qiita：https://qiita.com/Lifect

---

## 関連記事

[福祉業界の入居相談をAIで自動化してみた【Python x Streamlit x OpenAI API x Google Sheets】](https://qiita.com/Lifect/items/136a9d8cbf2aba449998)
