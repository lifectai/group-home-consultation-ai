import json
import requests
import streamlit as st
import pandas as pd
df = pd.read_csv("施設マスタ.csv")
import os
from datetime import datetime
import pytz
from openai import OpenAI
from dotenv import load_dotenv
import gspread
from google.oauth2.service_account import Credentials

# APIキー読み込み
load_dotenv()
client = OpenAI()
LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN", "")
LINE_USER_ID = os.getenv("LINE_USER_ID", "")

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
            "受付番号", "日時", "名前", "性別", "電話番号", "希望エリア", "相談区分",
            "障害種別", "障害支援区分", "生活状況", "日常生活のケア", "行動障害",
            "希望入居時期", "家賃上限", "こだわり条件", "希望エリア（AI抽出）",
            "会話ログ", "AI要約"
        ])
    return ws

st.set_page_config(page_title="グループホーム入居相談", page_icon="🏠")

st.markdown(
    '<meta name="google" content="notranslate">',
    unsafe_allow_html=True
)

st.title("グループホーム入居相談")
st.info("🔍 これはデモ版です。実際の相談データは保存されません。")
st.markdown("""
### このアプリでできること
・AIが入居相談をヒアリングし、状況を整理
・相談内容を自動で要約し、担当者へ共有
・相談データを蓄積し、営業・分析に活用

👉 電話対応の前に、必要な情報を自動で整理します
""")
st.warning("このアプリは『ヒアリング → 要約 → 情報整理』を自動化し、電話対応の質を均一化することを目的としています")
st.info("入居相談をAIが順番にお伺いします。1〜3分ほどで完了します。途中で難しい場合は「電話での連絡を希望」を押してください。")

# ----------------------------
# セッション初期化
# ----------------------------
if "ticket_no" not in st.session_state:
    st.session_state.ticket_no = datetime.now(pytz.timezone("Asia/Tokyo")).strftime("UKETSUKE%Y%m%d%H%M%S")

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

if "gender" not in st.session_state:
    st.session_state.gender = ""

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
        "障害種別": "未確認",
        "障害支援区分": "未確認",
        "生活状況": "未確認",
        "日常生活のケア": "未確認",
        "行動障害": "未確認",
        "希望入居時期": "未確認",
        "家賃上限": "未確認",
        "こだわり条件": "未確認",
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

    default = {
        "障害種別": "未確認",
        "障害支援区分": "未確認",
        "生活状況": "未確認",
        "日常生活のケア": "未確認",
        "行動障害": "未確認",
        "希望入居時期": "未確認",
        "家賃上限": "未確認",
        "こだわり条件": "未確認",
        "希望エリア": "未確認"
    }

    try:
        data = json.loads(text)
    except:
        return default

    return {k: data.get(k, "未確認") for k in default}


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
・障害種別：
・障害支援区分：
・現在の生活状況：
・日常生活のケアの有無：
・行動障害の有無：
・希望入居時期：
・家賃上限：
・こだわり条件：
・希望エリア：

【担当者へのポイント】
・優先対応が必要な事項：
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
    gender: str,
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
        datetime.now(pytz.timezone("Asia/Tokyo")).strftime("%Y-%m-%d %H:%M:%S"),
        name,
        gender,
        "'" + str(phone),
        area,
        consultation_type,
        extracted_info.get("障害種別", "未確認"),
        extracted_info.get("障害支援区分", "未確認"),
        extracted_info.get("生活状況", "未確認"),
        extracted_info.get("日常生活のケア", "未確認"),
        extracted_info.get("行動障害", "未確認"),
        extracted_info.get("希望入居時期", "未確認"),
        extracted_info.get("家賃上限", "未確認"),
        extracted_info.get("こだわり条件", "未確認"),
        extracted_info.get("希望エリア", "未確認"),
        log_text,
        ai_summary
    ]
    ws = get_worksheet()
    ws.append_row(row, value_input_option="USER_ENTERED")


def send_line_notification(
    ticket_no: str,
    name: str,
    gender: str,
    phone: str,
    consultation_type: str,
    extracted_info: dict,
    area: str
) -> None:
    if not LINE_CHANNEL_ACCESS_TOKEN or not LINE_USER_ID:
        return

    message = (
        f"【新着相談】\n"
        f"受付番号：{ticket_no}\n"
        f"名前：{name}\n"
        f"性別：{gender}\n"
        f"電話番号：{phone}\n"
        f"相談区分：{consultation_type}\n"
        f"障害種別：{extracted_info.get('障害種別', '未確認')}\n"
        f"希望エリア：{area}\n"
        f"担当者対応をお願いします。"
    )

    requests.post(
        "https://api.line.me/v2/bot/message/push",
        headers={
            "Authorization": f"Bearer {LINE_CHANNEL_ACCESS_TOKEN}",
            "Content-Type": "application/json",
        },
        json={
            "to": LINE_USER_ID,
            "messages": [{"type": "text", "text": message}],
        },
        timeout=10,
    )


# ----------------------------
# 会話履歴表示
# ----------------------------
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.write(msg["content"])

        if msg["role"] == "assistant":
            if "障害種別" in msg["content"] or "障がいの種類" in msg["content"]:
                st.caption("例：統合失調症、知的障害、身体障害、発達障害、高次脳機能障害 など")
            elif "障害支援区分" in msg["content"] or "支援区分" in msg["content"]:
                st.caption("例：区分1〜6、未判定、申請中 など")
            elif "生活状況" in msg["content"] or "どのような状況" in msg["content"] or "現在どこ" in msg["content"]:
                st.caption("例：家族と同居、一人暮らし、入院中、施設入所中 など")
            elif "日常生活のケア" in msg["content"] or "日常生活" in msg["content"]:
                st.caption("例：服薬管理、通院同行、買い物同行、定期受診の付き添い、入浴の手伝い、着替えの手伝い、掃除の手伝い、生活上の相談 など")
            elif "行動障害" in msg["content"] or "行動" in msg["content"]:
                st.caption("例：自傷行為、他害行為、パニック、飛び出し など")
            elif "入居時期" in msg["content"] or "いつ頃" in msg["content"]:
                st.caption("例：すぐにでも、1ヶ月以内、3ヶ月以内、半年以内、未定 など")
            elif "家賃" in msg["content"] or "費用" in msg["content"]:
                st.caption("例：生活保護の範囲内、障害年金の範囲内、月6万円以内 など")
            elif "こだわり" in msg["content"] or "希望条件" in msg["content"]:
                st.caption("例：駅近、個室、女性専用、支援内容（調理・洗濯）、ペット可 など")


# ----------------------------
# 名前入力
# ----------------------------
if st.session_state.step == "name":
    with st.form("name_form", clear_on_submit=True):
        name_input = st.text_input("お名前")
        col1, col2 = st.columns(2)
        with col1:
            submitted_name = st.form_submit_button("送信")
        with col2:
            submitted_anonymous = st.form_submit_button("匿名で相談する")

    if submitted_name and name_input:
        st.session_state.name = name_input
        st.session_state.messages.append({"role": "user", "content": name_input})

        reply = "ありがとうございます。性別を教えてください。"
        st.session_state.messages.append({"role": "assistant", "content": reply})

        st.session_state.step = "gender"
        st.rerun()

    elif submitted_anonymous:
        st.session_state.name = "匿名"
        st.session_state.messages.append({"role": "user", "content": "匿名"})

        reply = "承知しました。性別を教えてください。"
        st.session_state.messages.append({"role": "assistant", "content": reply})

        st.session_state.step = "gender"
        st.rerun()


# ----------------------------
# 性別選択
# ----------------------------
elif st.session_state.step == "gender":
    st.subheader("性別を選択してください")
    col1, col2, col3 = st.columns(3)

    selected_gender = None

    with col1:
        if st.button("男性", use_container_width=True):
            selected_gender = "男性"
    with col2:
        if st.button("女性", use_container_width=True):
            selected_gender = "女性"
    with col3:
        if st.button("答えたくない", use_container_width=True):
            selected_gender = "答えたくない"

    if selected_gender:
        st.session_state.gender = selected_gender
        st.session_state.messages.append({"role": "user", "content": selected_gender})

        reply = "ありがとうございます。次にお電話番号を教えてください。"
        st.session_state.messages.append({"role": "assistant", "content": reply})

        st.session_state.step = "phone"
        st.rerun()


# ----------------------------
# 電話番号入力
# ----------------------------
elif st.session_state.step == "phone":
    with st.form("phone_form", clear_on_submit=True):
        phone_input = st.text_input("電話番号", placeholder="半角数字で入力してください")
        submitted_phone = st.form_submit_button("送信")

    if submitted_phone:
        import re
        if not phone_input:
            st.error("電話番号を入力してください。")
        elif not re.fullmatch(r"[\d\-]+", phone_input):
            st.error("電話番号は半角数字（ハイフン可）で入力してください。")
        else:
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
やさしい言葉で、まず最初の質問（障害種別）から始めてください。
（例：統合失調症、知的障害、身体障害、発達障害、高次脳機能障害 など）
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

相談者が答えやすいように、やさしい言葉で1つずつ質問してください。
まず最初に障害種別から質問してください。

必ず以下を守ってください：

・質問は1つずつ行う
・専門用語には必ず具体例を添える
・誰でも答えられる聞き方にする
・文章は2〜3行以内
・必ず質問で終わる

【質問の順番と例示】
① 障害種別（例：統合失調症、知的障害、身体障害、発達障害 など）
② 障害支援区分（例：区分1〜6、未判定、申請中 など）
③ 現在の生活状況（例：家族と同居、一人暮らし、入院中 など）
④ 日常生活のケア（例：服薬管理、通院同行、たんの吸引 など）
⑤ 行動障害（例：自傷行為、他害行為、パニック など）
⑥ 希望入居時期（例：すぐにでも、1ヶ月以内、未定 など）
⑦ 家賃上限（例：生活保護の範囲内、月6万円以内 など）
⑧ こだわり条件（例：駅近、個室希望、支援内容 など）

会話の目的：
上記8項目を順番に引き出すこと
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
# その他相談
# ----------------------------
elif st.session_state.step == "consultation_other":
    st.subheader("その他のご相談内容をお聞かせください")
    with st.form("other_form", clear_on_submit=True):
        other_input = st.text_area("ご相談内容", placeholder="こちらにご入力ください")
        submitted_other = st.form_submit_button("送信")

    if submitted_other and other_input:
        consultation_type = f"その他：{other_input}"
        st.session_state.consultation_type = consultation_type
        st.session_state.messages.append({"role": "user", "content": other_input})
        st.session_state.messages.append({
            "role": "assistant",
            "content": "ありがとうございます。ご相談内容を担当者に共有します。担当者より改めてご連絡いたします。"
        })
        st.session_state.step = "finish"
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
相談者が答えやすいように、やさしい言葉で1つずつ質問してください。

【絶対に守るべきルール】
・質問は必ず以下の①〜⑧の順番通りに行う
・①が未回答なら①を聞く。②が未回答なら②を聞く。この順番を絶対に飛ばさない
・1回の発言で質問は1つだけ
・すでに回答を得た項目は聞かない
・専門用語には必ず具体例を添える
・文章は2〜3行以内
・次に聞く質問を自分で判断せず、必ず番号順に進める

【質問の順番（この順番を絶対に守ること）】
① 障害種別
   → 会話ログに障害種別の回答がなければ、必ずこれを最初に聞く
   （例：統合失調症、知的障害、身体障害、発達障害、高次脳機能障害 など）
② 障害支援区分
   → ①の回答が得られてから初めて聞く
   （例：区分1〜6、未判定、申請中 など）
③ 現在の生活状況
   → ②の回答が得られてから初めて聞く
   （例：家族と同居、一人暮らし、入院中、施設入所中 など）
④ 日常生活のケア
   → ③の回答が得られてから初めて聞く
   （例：服薬管理、通院同行、買い物同行、入浴の手伝い、着替えの手伝い、掃除の手伝い、生活上の相談。ない場合も教えてください）
⑤ 行動障害の有無
   → ④の回答が得られてから初めて聞く
   （例：自傷行為、他害行為、パニック、飛び出し。ない場合も教えてください）
⑥ 希望入居時期
   → ⑤の回答が得られてから初めて聞く
   （例：すぐにでも、1ヶ月以内、3ヶ月以内、半年以内、未定 など）
⑦ 家賃上限
   → ⑥の回答が得られてから初めて聞く
   （例：生活保護の範囲内、障害年金の範囲内、月6万円以内 など）
⑧ こだわり条件
   → ⑦の回答が得られてから初めて聞く
   （例：駅近、個室希望、女性専用、支援内容（調理・洗濯）、ペット可 など）

【進め方の例】
- 会話ログに障害種別が書かれていない → ①を聞く（②〜⑧は絶対に聞かない）
- 会話ログに障害種別はあるが障害支援区分がない → ②を聞く（③〜⑧は絶対に聞かない）
- 以降も同様に、未回答の最小番号の項目だけを聞く

【施設情報】
{facility_data}

【全項目完了時のルール】
・①〜⑧の全項目への回答が会話ログから確認できたとき、その返答の末尾に必ず以下の文をそのまま追記すること。
  「ご入力いただいた内容を担当者に共有します。他にご相談があれば入力して送信を押してください。終了する場合は「相談を終了する」ボタンを押してください。」
・この文は全項目が揃った最初の返答にのみ付け加える。まだ未回答の項目が1つでもある場合は絶対に付けない。

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
            st.session_state.gender,
            st.session_state.phone,
            st.session_state.area,
            st.session_state.consultation_type,
            st.session_state.messages,
            st.session_state.ai_summary,
            st.session_state.extracted_info
        )

        send_line_notification(
            st.session_state.ticket_no,
            st.session_state.name,
            st.session_state.gender,
            st.session_state.phone,
            st.session_state.consultation_type,
            st.session_state.extracted_info,
            st.session_state.area
        )

        st.session_state.saved_once = True

    st.markdown("### お聞かせいただいた内容")
    info = st.session_state.extracted_info
    st.markdown(f"""
| 項目 | 内容 |
|------|------|
| 障害種別 | {info.get("障害種別", "未確認")} |
| 障害支援区分 | {info.get("障害支援区分", "未確認")} |
| 生活状況 | {info.get("生活状況", "未確認")} |
| 日常生活のケア | {info.get("日常生活のケア", "未確認")} |
| 行動障害 | {info.get("行動障害", "未確認")} |
| 希望入居時期 | {info.get("希望入居時期", "未確認")} |
| 家賃上限 | {info.get("家賃上限", "未確認")} |
| こだわり条件 | {info.get("こだわり条件", "未確認")} |
| 希望エリア | {info.get("希望エリア", "未確認")} |
""")

    st.info("お聞かせいただいた内容を担当者に共有します。担当者より改めてご連絡いたします。")
    st.success("ご相談ありがとうございました")
    st.info("数日以内に担当者よりお電話いたします")