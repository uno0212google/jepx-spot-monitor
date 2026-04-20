import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.ticker import MultipleLocator # 5円区切りの目盛りのために追加
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import requests
import io

# ページ設定
st.set_page_config(page_title="JEPX関西スポット価格", layout="wide")

# セッション状態でy_maxを管理（タブ切り替え時も値を保持するため）
# デフォルト値を35に設定
if 'y_max' not in st.session_state:
    st.session_state.y_max = 35

# タイトル部分
st.subheader("JEPX関西スポット価格")
# margin-topを負の値にして間隔を詰める
st.markdown("<p style='font-size: 14px; color: #666666; margin-top: -10px;'>※表示価格は手数料や託送料、税を含まない金額です。</p>", unsafe_allow_html=True)

# 日本時間を取得するための関数を用意
def get_jst_now():
    return datetime.now(ZoneInfo("Asia/Tokyo"))

@st.cache_data(ttl=3600)
def load_jepx_data():
    now = get_jst_now() # 日本時間で現在時刻を取得
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
    now = get_jst_now() # ここも日本時間に修正
    today = now.date()
    
    target_dates = {
        "本日": today,
        "明日": today + timedelta(days=1),
        "昨日": today - timedelta(days=1)
    }
    
    kansai_col = 'エリアプライス関西(円/kWh)'
    
    current_slot = (now.hour * 2) + (1 if now.minute >= 30 else 0) + 1
    start_m = 30 if now.minute >= 30 else 0
    end_h = now.hour + (1 if start_m == 30 else 0)
    end_m = 0 if start_m == 30 else 30
    time_range_str = f"{now.hour:02d}:{start_m:02d} - {end_h % 24:02d}:{end_m:02d}"
    
    df_today = data[data['date'] == pd.to_datetime(today)].copy()
    current_price = "データなし"
    if not df_today.empty:
        try:
            current_price = f"{df_today[df_today['時刻コード'] == current_slot][kansai_col].values[0]:.2f}"
        except IndexError:
            current_price = "取得中..."

    # 余白を狭く修正、区切り線なし
    st.markdown(f"""
    <div style="background-color: #f8f9fa; padding: 10px; border-radius: 10px; text-align: center; border: 2px solid #e0e0e0; margin-bottom: 5px;">
        <p style="font-size: 16px; margin: 0; color: #333;">現在時刻: <strong>{now.strftime('%H:%M')}</strong> ｜ 当該時間帯: <strong>{time_range_str}</strong></p>
        <h1 style="font-size: 40px; color: #D35400; margin: 5px 0;">現在単価: {current_price} <span style="font-size: 20px;">円/kWh</span></h1>
    </div>
    """, unsafe_allow_html=True)

    tab_today, tab_tomorrow, tab_yesterday = st.tabs(["📊 本日の価格推移", "📅 明日の価格推移", "⏪ 昨日の実績"])

    tabs_dict = {
        "本日": tab_today,
        "明日": tab_tomorrow,
        "昨日": tab_yesterday
    }

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
                
                # 線やマーカーが切れないように、x軸にマージンを持たせる
                ax.set_xlim(left=0, right=24)
                # Y軸の下限を-2にすることで、0円付近のマーカーが隠れるのを防ぎます
                ax.set_ylim(bottom=-2, top=st.session_state.y_max)

                if label == "本日":
                    ax.axvline(x=(current_slot-1)*0.5, color='red', linestyle='--', label='Current Time')
                    ax.legend()
                    
                ax.set_ylabel("Price (Yen/kWh)")
                ax.set_xlabel("Time (Hour)")
                
                # 5円ごとに横方向のグリッド線を引く
                ax.yaxis.set_major_locator(MultipleLocator(5))
                
                ax.grid(True, alpha=0.3)
                ax.set_xticks(range(0, 25, 2))
                st.pyplot(fig)
                plt.close(fig)

            # スライダー
            st.write("---")
            col_slider, _ = st.columns([1, 2])
            with col_slider:
                new_y_max = st.slider(
                    "📈 JEPX価格グラフのY軸上限を設定 (円/kWh)",
                    min_value=10,
                    max_value=100,
                    value=st.session_state.y_max,
                    step=5,
                    key=f"slider_{label}"
                )
                if new_y_max != st.session_state.y_max:
                    st.session_state.y_max = new_y_max
                    st.rerun()

else:
    st.error("JEPXからデータを読み込めませんでした。URLを確認してください。")