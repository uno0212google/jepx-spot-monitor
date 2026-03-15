import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import japanize_matplotlib  # グラフの日本語文字化けを解消
from datetime import datetime, timedelta
import requests
import io

# ページ設定（スマホでも見やすいレイアウト）
st.set_page_config(page_title="JEPX関西スポット価格", layout="wide")

# 3. タイトルの変更
st.title("⚡ JEPX関西スポット価格")
# 2. 手数料や税を含まない旨の注意書き（少し小さめの文字でグレー表示）
st.markdown("<p style='font-size: 14px; color: #666666;'>※表示価格は手数料や託送料、税を含まない金額です。</p>", unsafe_allow_html=True)

@st.cache_data(ttl=3600)
def load_jepx_data():
    now = datetime.now()
    year = now.year
    if now.month <= 3:
        target_year = year - 1
    else:
        target_year = year
        
    url = f"https://www.jepx.jp/market/excel/spot_{target_year}.csv"
    
    try:
        response = requests.get(url, timeout=10)
        response.encoding = 'shift_jis'
        df = pd.read_csv(io.StringIO(response.text))
        df.columns = [c.strip() for c in df.columns]
        df['date'] = pd.to_datetime(df['年月日'], format='%Y/%m/%d')
        return df
    except Exception as e:
        st.error(f"データ取得エラー: {e}")
        return None

data = load_jepx_data()

if data is not None:
    now = datetime.now()
    today = now.date()
    
    # 昨日、今日、明日の日付を設定
    target_dates = {
        "本日": today,
        "明日": today + timedelta(days=1),
        "昨日": today - timedelta(days=1)
    }
    
    kansai_col = 'エリアプライス関西(円/kWh)'
    
    # --- 4. 現在の状況を大きくハイライト表示 ---
    st.markdown("---")
    
    # 現在の時刻コードと時間帯の文字列を作成
    current_slot = (now.hour * 2) + (1 if now.minute >= 30 else 0) + 1
    start_m = 30 if now.minute >= 30 else 0
    end_h = now.hour + (1 if start_m == 30 else 0)
    end_m = 0 if start_m == 30 else 30
    time_range_str = f"{now.hour:02d}:{start_m:02d} - {end_h % 24:02d}:{end_m:02d}"
    
    # 今日のデータから現在単価を取得
    df_today = data[data['date'] == pd.to_datetime(today)].copy()
    current_price = "データなし"
    if not df_today.empty:
        try:
            current_price = f"{df_today[df_today['時刻コード'] == current_slot][kansai_col].values[0]:.2f}"
        except IndexError:
            current_price = "取得中..."

    # オペレーター向け：HTML/CSSを使って大きく目立たせる
    st.markdown(f"""
    <div style="background-color: #f8f9fa; padding: 20px; border-radius: 10px; text-align: center; border: 2px solid #e0e0e0;">
        <p style="font-size: 20px; margin: 0; color: #333;">現在時刻: <strong>{now.strftime('%H:%M')}</strong> ｜ 当該時間帯: <strong>{time_range_str}</strong></p>
        <h1 style="font-size: 56px; color: #D35400; margin: 10px 0;">現在単価: {current_price} <span style="font-size: 24px;">円/kWh</span></h1>
    </div>
    """, unsafe_allow_html=True)
    st.markdown("---")

    # --- 1. タブで表示を切り替える（昨日は常時非表示） ---
    tab_today, tab_tomorrow, tab_yesterday = st.tabs(["📊 本日の価格推移", "📅 明日の価格推移", "⏪ 昨日の実績"])

    # タブと日付の対応付け
    tabs_dict = {
        "本日": tab_today,
        "明日": tab_tomorrow,
        "昨日": tab_yesterday
    }

    # 各タブの中にグラフを描画
    for label, target_date in target_dates.items():
        with tabs_dict[label]:
            st.subheader(f"{label}のデータ ({target_date.strftime('%Y/%m/%d')})")
            
            target_dt = pd.to_datetime(target_date)
            df_target = data[data['date'] == target_dt].copy()
            
            if df_target.empty:
                if label == "明日":
                    st.info("💡 明日のデータは、本日10:00〜11:00頃にJEPXより公開されるまでお待ちください。")
                else:
                    st.warning("データが取得できません。")
                continue
                
            df_target['hour'] = (df_target['時刻コード'] - 1) * 0.5
            
            col1, col2 = st.columns([1, 2])
            
            with col1:
                # 平均・最高・最安値を表示
                avg_price = round(df_target[kansai_col].mean(), 2)
                max_price = df_target[kansai_col].max()
                min_price = df_target[kansai_col].min()
                st.metric(label="1日の平均単価", value=f"{avg_price} 円/kWh")
                st.write(f"最高値: **{max_price}** 円/kWh")
                st.write(f"最安値: **{min_price}** 円/kWh")
            
            with col2:
                fig, ax = plt.subplots(figsize=(8, 3))
                color = '#E67E22' if label == "本日" else '#7F8C8D' if label == "昨日" else '#2980B9'
                
                ax.plot(df_target['hour'], df_target[kansai_col], marker='o', color=color)
                
                # 「本日」のみ現在時刻の赤線を引く
                if label == "本日":
                    ax.axvline(x=(current_slot-1)*0.5, color='red', linestyle='--', label='現在時刻')
                    ax.legend()
                    
                ax.set_ylabel("円/kWh")
                ax.set_xlabel("時間 (時)")
                ax.grid(True, alpha=0.3)
                # 0時〜24時まで見やすくメモリを設定
                ax.set_xticks(range(0, 25, 2))
                st.pyplot(fig)
                plt.close(fig) # メモリ節約のためにグラフを閉じる

else:
    st.error("JEPXからデータを読み込めませんでした。URLを確認してください。")