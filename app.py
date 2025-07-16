import streamlit as st
import pandas as pd
import datetime
import google.generativeai as genai
import os
import plotly.graph_objects as go
from streamlit_plotly_events import plotly_events

# --- Gemini APIキー設定 ---
try:
    GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]
except KeyError:
    st.error("GEMINI_API_KEY が secrets.toml に設定されていません。")
    st.stop()

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-2.0-flash-lite")

DATA_FILE = "diary_data.csv"

st.title("📝 感情分析付き 日記アプリ")
st.markdown("日記に題名をつけて、感情分析しネガティブなら励ましアドバイスも表示します。")

# --- 日記入力フォーム ---
with st.form("diary_form"):
    date = st.date_input("日付", value=datetime.date.today())
    title = st.text_input("題名を入力してください", max_chars=50)
    content = st.text_area("今日の出来事や気持ちを自由に書いてください", height=200)
    submitted = st.form_submit_button("保存して感情分析")

if submitted and content.strip():
    感情リスト = ["とてもポジティブ", "ポジティブ", "ややポジティブ", "ニュートラル", "ネガティブ", "とてもネガティブ"]

    prompt = f"""
以下の文章の感情を、次の6つのうちいずれかで返してください。
{感情リスト}

また、感情の理由や背景も簡潔に説明してください。

文章: {content}
"""

    try:
        response = model.generate_content(prompt)
        text = response.text.strip()
        st.write("=== Gemini APIの返答 ===")
        st.text(text)

        lines = text.split("\n")
        emotion = lines[0].replace("*", "").strip() if lines else "ニュートラル"
        explanation = "\n".join(lines[1:]).strip() if len(lines) > 1 else ""

        if emotion not in 感情リスト:
            emotion = "ニュートラル"
        if not explanation:
            explanation = ""

    except Exception as e:
        st.error(f"Gemini APIエラー: {e}")
        st.stop()

    advice = ""
    if emotion in ["ネガティブ", "とてもネガティブ"]:
        advice_prompt = f"""
あなたは思いやりのあるカウンセラーです。

以下のネガティブな気持ちを少しでも前向きにするような、
やさしい励ましや視点の切り替えアドバイスを1～2文でください。

日記の内容: {content}
"""
        try:
            advice_response = model.generate_content(advice_prompt)
            advice = advice_response.text.strip()
        except Exception as e:
            advice = "（アドバイス生成中にエラーが発生しました）"

    new_data = pd.DataFrame([[date, title, content, emotion, explanation, advice]],
                            columns=["date", "title", "content", "emotion", "explanation", "advice"])

    if os.path.exists(DATA_FILE):
        old_data = pd.read_csv(DATA_FILE, keep_default_na=False)
        if "title" not in old_data.columns:
            old_data["title"] = ""
        all_data = pd.concat([old_data, new_data], ignore_index=True)
    else:
        all_data = new_data

    all_data.to_csv(DATA_FILE, index=False)

    st.success(f"日記を保存しました！ 感情: **{emotion}**")
    if advice:
        st.markdown(f"### 💡 ポジティブアドバイス\n> {advice}")

if os.path.exists(DATA_FILE):
    st.subheader("📚 過去の日記一覧")

    df = pd.read_csv(DATA_FILE, keep_default_na=False)
    if "title" not in df.columns:
        df["title"] = ""
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date", ascending=False).reset_index(drop=True)

    diary_titles = [f"{row['title']} - {row['emotion']}" for _, row in df.iterrows()]
    selected = st.selectbox("表示する日記を選んでください", diary_titles)
    selected_index = diary_titles.index(selected)
    selected_entry = df.iloc[selected_index]

    st.markdown(f"### 🗓 {selected_entry['date'].date()} - {selected_entry['title']} - 感情: **{selected_entry['emotion']}**")
    if selected_entry["explanation"]:
        st.write(f"**感情の理由・背景**:\n{selected_entry['explanation']}")
    st.write(selected_entry["content"])
    if "advice" in df.columns and selected_entry["advice"]:
        st.markdown(f"### 💡 ポジティブアドバイス\n> {selected_entry['advice']}")

    if st.button("この日記を削除"):
        df = df.drop(selected_index).reset_index(drop=True)
        df.to_csv(DATA_FILE, index=False)
        st.success("選択した日記を削除しました。ページをリロードしてください。")

    emotion_score_map = {
        "とてもポジティブ": 2,
        "ポジティブ": 1,
        "ややポジティブ": 0.5,
        "ニュートラル": 0,
        "ネガティブ": -1,
        "とてもネガティブ": -2
    }
    df["score"] = df["emotion"].map(emotion_score_map).fillna(0)
    daily_scores = df.groupby("date")["score"].mean().reset_index()

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=daily_scores["date"],
        y=daily_scores["score"],
        mode="lines+markers",
        marker=dict(size=8),
        line=dict(color="royalblue"),
        hovertemplate="日付: %{x}<br>感情スコア: %{y}<extra></extra>"
    ))

    fig.update_layout(
        title="感情グラフ（クリックで日記表示）",
        xaxis_title="日付",
        yaxis_title="感情スコア",
        yaxis=dict(range=[-2.1, 2.1]),
        template="plotly_white"
    )

    st.subheader("📈 感情グラフ")
    selected_points = plotly_events(fig, click_event=True, hover_event=False)

    if selected_points:
        selected_date_str = selected_points[0]["x"]
        selected_date = pd.to_datetime(selected_date_str)

        df["date_only"] = df["date"].dt.date
        matching_row = df[df["date_only"] == selected_date.date()]

        if not matching_row.empty:
            entry = matching_row.iloc[0]
            st.markdown(f"### 🖱 グラフから選択: {entry['date'].date()} - {entry['title']} - 感情: **{entry['emotion']}**")
            if entry["explanation"]:
                st.write(f"**感情の理由・背景**:\n{entry['explanation']}")
            st.write(entry["content"])
            if entry.get("advice"):
                st.markdown(f"### 💡 ポジティブアドバイス\n> {entry['advice']}")
        else:
            st.warning("クリックした日付に対応する日記が見つかりませんでした。")

else:
    st.info("まだ日記が記録されていません。まずは最初の記録を追加してください。")
