import streamlit as st
import pandas as pd
import os
from dotenv import load_dotenv

load_dotenv()

st.title("ヒアリングチャットの追加")

st.info("入居相談の追加ヒアリングを行います。")

# =========================
# 受付番号取得
# =========================

ticket = st.query_params.get("ticket")

if ticket is None:
    st.error("受付番号が取得できませんでした。")
    st.stop()

st.success(f"受付番号：{ticket}")

# =========================
# 保存先
# =========================

folder_path = os.path.expanduser("~/Desktop/AI入居相談")
file_path = os.path.join(folder_path, "相談記録.xlsx")

# =========================
# ヒアリング質問
# =========================

questions = [
    "差し支えなければ、障がい名を教えてください。",
    "障害区分はありますか？（例：区分3）",
    "現在通院している病院はありますか？",
    "ケースワーカー（相談員）はいますか？",
    "生活保護や障害年金など利用されていますか？"
]

columns = [
    "障がい名",
    "障害区分",
    "病院",
    "ケースワーカー",
    "経済状況"
]

# =========================
# セッション初期化
# =========================

if "messages" not in st.session_state:
    st.session_state.messages = [
        {"role": "assistant", "content": questions[0]}
    ]

if "step" not in st.session_state:
    st.session_state.step = 0

if "answers" not in st.session_state:
    st.session_state.answers = []

# =========================
# チャット履歴表示
# =========================

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.write(msg["content"])

# =========================
# 入力
# =========================

user_input = st.chat_input("ここに入力してください")

if user_input:

    # ユーザー表示
    st.session_state.messages.append({
        "role": "user",
        "content": user_input
    })

    with st.chat_message("user"):
        st.write(user_input)

    # 回答保存
    st.session_state.answers.append(user_input)

    st.session_state.step += 1

    # =========================
    # 次の質問
    # =========================

    if st.session_state.step < len(questions):

        reply = questions[st.session_state.step]

    else:

        reply = "ヒアリングありがとうございました。担当者よりご連絡いたします。"

        # =========================
        # Excel更新
        # =========================

        if os.path.exists(file_path):

            df = pd.read_excel(file_path)

            if "受付番号" in df.columns:

                index = df[df["受付番号"] == ticket].index

                if len(index) > 0:

                    for i, col in enumerate(columns):

                        if i < len(st.session_state.answers):

                            df.loc[index[0], col] = st.session_state.answers[i]

                    df.to_excel(file_path, index=False)

    # =========================
    # AI表示
    # =========================

    st.session_state.messages.append({
        "role": "assistant",
        "content": reply
    })

    with st.chat_message("assistant"):
        st.write(reply)