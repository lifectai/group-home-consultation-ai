import json
import streamlit as st
import pandas as pd
df = pd.read_csv("施設マスタ.csv")
import os
from datetime import datetime
from openai import OpenAI
from dotenv import load_dotenv
import gspread
from google.oauth2.service_account import Credentials

# APIキー読み込み
load_dotenv()
client = OpenAI()

# ----------------------------
# Google Sheets 接続
# ----------------------------
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

@st.cache_resource
def get_gsheet_client():
    creds_dict = dict(st.secrets["gcp_service_account"])
    creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
    return gspread.authorize(creds)

def get_worksheet():
    gc = get_gsheet_client()
    sheet_url = st.secrets["spreadsheet_url"]
    spreadsheet = gc.open_by_url(sheet_url)
    try:
        ws = spreadsheet.worksheet("相談記録")
    except gspread.WorksheetNotFound:
        ws = spreadsheet.add_worksheet(title="相談記録", rows=1000, cols=20)
        ws.append_row([
            "受付番号", "日時", "名前", "電話番号", "希望エリア", "相談区分",
            "障がい名", "生活状況", "必要支援", "希望エリア（AI抽出）",
            "会話ログ", "AI要約"
        ])
    return ws

st.set_page_config(page_title="グループホーム入居相談", page_icon="🏠")

st.markdown(
    '<meta name="google" content="notranslate">',
    unsafe_allow_html=True
)

st.title("グループホーム入居相談")
st.markdown("""
### このアプリでできること
・AIが入居相談をヒアリングし、状況を整理  
・相談内容を自動で要約し、担当者へ共有  
・相談データを蓄積し、営業・分析に活用  

👉 電話対応の前に、必要な情報を自動で整理します
""")
st.warning("このアプリは『ヒアリング → 要約 → 情報整理』を自動化し、電話対応の質を均一化することを目的としています")
st.success("20260320-条件分岐版")
st.info("入居相談をAIが順番にお伺いします。1〜3分ほどで完了します。途中で難しい場合は「電話での連絡を希望」を押してください。")

# ----------------------------
# セッション初期化
# ----------------------------
if "ticket_no" not in st.session_state:
    st.session_state.ticket_no = datetime.now().strftime("UKETSUKE%Y%m%d%H%M%S")

if "messages" not in st.session_state:
    st.session_state.messages = [
        {
            "role": "assistant",
            "content": "こんにちは。グループホーム入居相談AIです。まずお名前を教えてください。"
        }
    ]

if "step" not in st.session_state:
    st.session_state.step = "name"

if "name" not in st.session_state:
    st.session_state.name = ""

if "phone" not in st.session_state:
    st.session_state.phone = ""

if "area" not in st.session_state:
    st.session_state.area = ""

if "consultation_type" not in st.session_state:
    st.session_state.consultation_type = ""

if "ai_summary" not in st.session_state:
    st.session_state.ai_summary = ""

if "extracted_info" not in st.session_state:
    st.session_state.extracted_info = {
        "障がい名": "未確認",
        "生活状況": "未確認",
        "必要支援": "未確認",
        "希望エリア": "未確認"
    }

if "saved_once" not in st.session_state:
    st.session_state.saved_once = False

st.caption(f"受付番号：{st.session_state.ticket_no}")



# ----------------------------
# 便利関数
# ----------------------------
def build_log_text(messages: list) -> str:
    log_text = ""
    for m in messages:
        log_text += f"{m['role']} : {m['content']} / "
    return log_text


def extract_consultation_info(messages: list) -> dict:
    log_text = build_log_text(messages)

    prompt = f"""
以下の入居相談の会話ログから情報を抽出してください。

出力は必ずJSON形式で返してください。
JSON以外の文章は一切出力しないでください。

{{
  "障がい名": "",
  "生活状況": "",
  "必要支援": "",
  "希望エリア": ""
}}

不明な場合は「未確認」と書く

会話ログ:
{log_text}
"""

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "あなたは福祉相談内容を整理する専門家です。"},
            {"role": "user", "content": prompt}
        ]
    )

    text = response.choices[0].message.content.strip()

    if text.startswith("```"):
        text = text.replace("```json", "").replace("```", "").strip()

    try:
        data = json.loads(text)
    except:
        data = {
            "障がい名": "未確認",
            "生活状況": "未確認",
            "必要支援": "未確認",
            "希望エリア": "未確認"
        }

    return {
        "障がい名": data.get("障がい名", "未確認"),
        "生活状況": data.get("生活状況", "未確認"),
        "必要支援": data.get("必要支援", "未確認"),
        "希望エリア": data.get("希望エリア", "未確認")
    }


def generate_ai_summary(messages: list, name: str, phone: str, consultation_type: str) -> str:
    log_text = build_log_text(messages)

    summary_prompt = f"""
あなたは障害者グループホームの相談内容を整理する担当者です。

以下の会話ログをもとに、担当者がすぐに電話対応できるように、
必ず以下のフォーマットで整理してください。

【相談者情報】
・名前：{name}
・電話番号：{phone}
・相談区分：{consultation_type}

【相談内容】
・障がい名：
・生活状況：
・必要な支援：
・希望エリア：

【補足】
・特記事項や注意点：

※不明な項目は「未確認」と記載してください

会話ログ:
{log_text}
"""

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "あなたは福祉相談の内容整理が得意なアシスタントです。"},
                {"role": "user", "content": summary_prompt}
            ]
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"AI要約エラー: {e}"


def save_to_sheets(
    ticket_no: str,
    name: str,
    phone: str,
    area: str,
    consultation_type: str,
    messages: list,
    ai_summary: str,
    extracted_info: dict
) -> None:
    log_text = build_log_text(messages)
    row = [
        ticket_no,
        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        name,
        phone,
        area,
        consultation_type,
        extracted_info.get("障がい名", "未確認"),
        extracted_info.get("生活状況", "未確認"),
        extracted_info.get("必要支援", "未確認"),
        extracted_info.get("希望エリア", "未確認"),
        log_text,
        ai_summary
    ]
    ws = get_worksheet()
    ws.append_row(row, value_input_option="USER_ENTERED")


# ----------------------------
# 会話履歴表示
# ----------------------------
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.write(msg["content"])

        if msg["role"] == "assistant":
            if "障がい" in msg["content"]:
                st.caption("例：統合失調症、知的障害 など")
            elif "生活" in msg["content"]:
                st.caption("例：一人暮らし、家族と同居 など")
            elif "支援" in msg["content"]:
                st.caption("例：服薬管理、通院同行、金銭管理 など")


# ----------------------------
# 名前入力
# ----------------------------
if st.session_state.step == "name":
    with st.form("name_form", clear_on_submit=True):
        name_input = st.text_input("お名前")
        submitted_name = st.form_submit_button("送信")

    if submitted_name and name_input:
        st.session_state.name = name_input
        st.session_state.messages.append({"role": "user", "content": name_input})

        reply = "ありがとうございます。次にお電話番号を教えてください。"
        st.session_state.messages.append({"role": "assistant", "content": reply})

        st.session_state.step = "phone"
        st.rerun()


# ----------------------------
# 電話番号入力
# ----------------------------
elif st.session_state.step == "phone":
    with st.form("phone_form", clear_on_submit=True):
        phone_input = st.text_input("電話番号")
        submitted_phone = st.form_submit_button("送信")

    if submitted_phone and phone_input:
        st.session_state.phone = phone_input
        st.session_state.messages.append({"role": "user", "content": phone_input})

        reply = "ありがとうございます。ご相談内容を選んでください。"
        st.session_state.messages.append({"role": "assistant", "content": reply})

        st.session_state.step = "consultation_select"
        st.rerun()


# ----------------------------
# エリア選択
# ----------------------------
elif st.session_state.step == "area_select":
    st.subheader("ご希望のエリア")

    area = st.selectbox(
        "ご希望のエリアを選択してください",
        [
            "どこでも可能",
            "名古屋市（名東区）",
            "名古屋市（中川区）",
            "名古屋市（港区）",
            "名古屋市（熱田区）",
            "一宮市"
        ]
    )

    if st.button("次へ"):
        if not any(
            m["role"] == "user" and "希望エリア：" in m["content"]
            for m in st.session_state.messages
        ):
            st.session_state.messages.append({
                "role": "user",
                "content": f"希望エリア：{area}"
            })

        st.session_state.area = area

        system_prompt = """
あなたは障害者グループホームの入居相談員です。
やさしい言葉で1つずつ質問してください。
"""

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": st.session_state.consultation_type}
            ]
        )

        reply = response.choices[0].message.content
        st.session_state.messages.append({"role": "assistant", "content": reply})

        st.session_state.step = "hearing"
        st.rerun()

# ----------------------------
# 相談内容選択
# ----------------------------
elif st.session_state.step == "consultation_select":
    st.subheader("ご相談内容を選んでください")
    col1, col2 = st.columns(2)

    selected = None

    with col1:
        if st.button("入居について相談したい", use_container_width=True):
            selected = "入居について相談したい"
        if st.button("空室を知りたい", use_container_width=True):
            selected = "空室を知りたい"
        if st.button("料金を知りたい", use_container_width=True):
            selected = "料金を知りたい"

    with col2:
        if st.button("見学を希望したい", use_container_width=True):
            selected = "見学を希望したい"

        if st.button("その他を相談したい", use_container_width=True):
            st.session_state.step = "consultation_other"
            st.rerun()

    if selected:
        st.session_state.consultation_type = selected
        st.session_state.messages.append({"role": "user", "content": selected})

        # ★条件分岐
        if selected in ["入居について相談したい", "空室を知りたい"]:
            reply = "ありがとうございます。ご希望のエリアを教えてください。"
            st.session_state.messages.append({"role": "assistant", "content": reply})
            st.session_state.step = "area_select"
            st.rerun()
            st.stop()

        system_prompt = """
あなたは障害者グループホームの入居相談員です。

相談者が答えやすいように、具体的でやさしい質問をしてください。

必ず以下を守ってください：

・質問は1つずつ行う
・専門用語は使わない
・誰でも答えられる聞き方にする
・文章は2〜3行以内
・必ず質問で終わる

【質問の例】
・どのような障がいがありますか？
・現在はどのような生活をされていますか？
・どのような支援が必要ですか？
・ご希望のエリアはありますか？

会話の目的：
相談者の状況（障がい・生活状況・必要支援・希望）を引き出すこと
"""

        try:
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": selected}
                ]
            )
            reply = response.choices[0].message.content
        except Exception as e:
            reply = f"AI応答でエラーが発生しました。{e}"

        st.session_state.messages.append({"role": "assistant", "content": reply})
        st.session_state.step = "hearing"
        st.rerun()


# ----------------------------
# ヒアリング
# ----------------------------
elif st.session_state.step == "hearing":
    st.info("AIからの質問にお答えください")

    st.caption("入力が難しい場合は、電話対応に切り替えできます。")
    
    with st.form("hearing_form", clear_on_submit=True):
        hearing_input = st.text_input(
        "ご相談内容をご入力ください",
        placeholder="こちらにご入力ください"
    )

        col1, col2, col3 = st.columns(3)

        with col1:
            submitted_hearing = st.form_submit_button("送信")

        with col2:
            request_call = st.form_submit_button("電話での連絡を希望")

        with col3:
            finish_chat = st.form_submit_button("相談を終了する")

    # ★相談終了
    if finish_chat:
        st.session_state.step = "finish"
        st.rerun()

    # ★電話希望
    elif request_call:
        st.session_state.messages.append({
            "role": "assistant",
            "content": "ありがとうございます。担当者より1週間以内にお電話いたします。"
        })

        st.session_state.step = "finish"
        st.rerun()

    # 通常送信
    elif submitted_hearing and hearing_input and not finish_chat:
        st.session_state.messages.append({"role": "user", "content": hearing_input})

        filtered_df = df.copy()

    #.エリアで絞る
        if st.session_state.area:
            filtered_df = filtered_df[
                filtered_df["エリア"].str.contains(st.session_state.area, na=False)
            ]

        facility_data = filtered_df.to_string()

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": f"""

あなたはグループホームの相談員です。

以下の順番で必ず質問してください：

① 障がい
② 生活状況
③ 必要支援

ルール：
・1回の発言で質問は1つだけ
・必ず順番通りに進める
・すでに聞いた内容は聞かない

【施設情報】
{facility_data}

【追加ルール】
・空室は案内しない
・合いそうな施設の特徴のみ伝える
・不明な場合は「担当者よりご案内します」とする
"""
            }
        ] + st.session_state.messages
        )
        reply = response.choices[0].message.content

        st.session_state.messages.append({"role": "assistant", "content": reply})
        st.rerun()

# ----------------------------
# 終了
# ----------------------------
elif st.session_state.step == "finish":
    if not st.session_state.saved_once:
        st.session_state.ai_summary = generate_ai_summary(
            st.session_state.messages,
            st.session_state.name,
            st.session_state.phone,
            st.session_state.consultation_type
        )

        st.session_state.extracted_info = extract_consultation_info(
            st.session_state.messages
        )

        save_to_sheets(
            st.session_state.ticket_no,
            st.session_state.name,
            st.session_state.phone,
            st.session_state.area,
            st.session_state.consultation_type,
            st.session_state.messages,
            st.session_state.ai_summary,
            st.session_state.extracted_info
        )

        st.session_state.saved_once = True

    # フィルタ済みデータ
    filtered_df = df.copy()

    if st.session_state.area:
        filtered_df = filtered_df[
            filtered_df["エリア"].str.contains(st.session_state.area, na=False)
        ]

    facility_data = filtered_df.to_string()

    recommend_prompt = f"""
あなたはグループホームの相談員です。

以下の相談内容をもとに、相談者の状況に合った施設を提案してください。

【相談内容】
{build_log_text(st.session_state.messages)}

【施設情報】
{facility_data}

ルール：
・空室は案内しない
・必ず相談内容と紐づけて説明する
・「〇〇のため、この施設が合います」と理由を書く
・合いそうな施設を2〜3件に絞る
・合わない場合は無理に提案しない
"""

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "あなたは福祉施設提案のプロです"},
            {"role": "user", "content": recommend_prompt}
        ]
    )

    recommend_text = response.choices[0].message.content

    st.markdown("### あなたに合いそうな施設")
    st.write(recommend_text)

    st.success("ご相談ありがとうございました")
    st.info("1週間以内に担当者よりお電話いたします")