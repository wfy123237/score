import streamlit as st
import mysql.connector
import random
import os
import time
from datetime import datetime

# ================= 配置区域 =================
CLOUD_BASE_URL = "https://score-1.oss-cn-beijing.aliyuncs.com/Image_3600/"


# ================= 1. 数据库连接 =================

def get_db_connection():
    db_config = st.secrets["connections"]["tidb"]
    return mysql.connector.connect(
        host=db_config["host"],
        user=db_config["user"],
        password=db_config["password"],
        port=db_config["port"],
        database=db_config["database"],
        autocommit=True
    )


def init_db():
    try:
        conn = get_db_connection()
        c = conn.cursor()
        c.execute('''
                  CREATE TABLE IF NOT EXISTS annotations
                  (
                      user_id
                      VARCHAR
                  (
                      50
                  ),
                      group_id VARCHAR
                  (
                      50
                  ),
                      image_name VARCHAR
                  (
                      255
                  ),
                      score_content INT,
                      score_aesthetic INT,
                      score_quality INT,
                      timestamp DATETIME,
                      PRIMARY KEY
                  (
                      user_id,
                      image_name
                  )
                      )
                  ''')
        conn.close()
    except Exception as e:
        print(f"DB Init Error: {e}")


try:
    init_db()
except Exception as e:
    st.error(f"数据库连接失败: {e}")


# ================= 2. 核心逻辑 =================

def get_cloud_image_list(user_id, group_id_str):
    txt_file = "image_names.txt"
    if not os.path.exists(txt_file):
        st.error("❌ 找不到 image_names.txt")
        return []

    with open(txt_file, "r", encoding="utf-8") as f:
        all_images = [line.strip() for line in f.readlines()]

    target_folder = group_id_str.replace(" ", "_")
    current_group_images = [img for img in all_images if img.startswith(target_folder + "/")]

    if not current_group_images:
        return []

    seed_val = sum(ord(c) for c in user_id)
    rng = random.Random(seed_val)
    rng.shuffle(current_group_images)

    return current_group_images


def get_completed_images(user_id):
    try:
        conn = get_db_connection()
        c = conn.cursor()
        c.execute("SELECT image_name FROM annotations WHERE user_id = %s", (user_id,))
        result = {row[0] for row in c.fetchall()}
        conn.close()
        return result
    except Exception as e:
        return set()


def save_to_db(user_id, group_id, img_path, s1, s2, s3):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = None
    try:
        conn = get_db_connection()
        c = conn.cursor()
        query = """
                REPLACE \
                INTO annotations 
                (user_id, group_id, image_name, score_content, score_aesthetic, score_quality, timestamp)
                VALUES ( \
                %s, \
                %s, \
                %s, \
                %s, \
                %s, \
                %s, \
                %s \
                )
                """
        values = (user_id, group_id, img_path, s1, s2, s3, timestamp)
        c.execute(query, values)
        return True
    except Exception as e:
        st.error(f"保存失败: {e}")
        return False
    finally:
        if conn and conn.is_connected():
            conn.close()


# ================= 3. UI 组件 (无状态渲染) =================

def render_blind_slider(label, unique_key):
    """
    渲染滑块。
    unique_key: 必须是随图片变化的唯一值，这样切图时滑块会自动重置，防止报错。
    """
    # 强制文字不换行 CSS
    st.markdown(f"""
        <div style="
            font-size: 1.1rem; 
            font-weight: 600; 
            white-space: nowrap; 
            overflow: visible;
            margin-bottom: 5px;
            color: white; 
        ">
        {label}
        </div>
        """, unsafe_allow_html=True)

    # 这里的 key 是动态的 (例如 s_content_5)，所以每次换图都是一个新控件
    # 默认值 50，无需手动 session_state 赋值
    val = st.slider(
        label, 0, 100, 50,
        key=unique_key,
        label_visibility="collapsed",
        format=" "
    )

    html_oneline = "<div style='position: relative; width: 100%; height: 30px; margin-top: -25px; font-size: 0.8rem; color: #888; line-height: 1.1; pointer-events: none;'><div style='position: absolute; left: 0%; transform: translateX(-50%); text-align: center; white-space: nowrap;'>|<br>极差</div><div style='position: absolute; left: 25%; transform: translateX(-50%); text-align: center; white-space: nowrap;'>|<br>差</div><div style='position: absolute; left: 50%; transform: translateX(-50%); text-align: center; white-space: nowrap;'>|<br>中等</div><div style='position: absolute; left: 75%; transform: translateX(-50%); text-align: center; white-space: nowrap;'>|<br>好</div><div style='position: absolute; left: 100%; transform: translateX(-50%); text-align: center; white-space: nowrap;'>|<br>极好</div></div>"
    st.markdown(html_oneline, unsafe_allow_html=True)
    return val  # 虽然在 Form 里用不到返回值，但保持逻辑完整


# ================= 4. 主程序 =================

def main():
    st.set_page_config(page_title="Underwater Aesthetics", layout="wide")

    st.markdown("""
        <style>
        header[data-testid="stHeader"] { display: none !important; }
        div[data-testid="stThumbValue"], div[data-testid="stTickBarMin"], div[data-testid="stTickBarMax"] { opacity: 0 !important; display: none !important; }

        .block-container { 
            padding-top: 1rem !important; 
            padding-bottom: 2rem !important; 
            max-width: 95% !important; 
        }
        div[data-testid="stImage"] { display: flex; justify-content: center; }
        div[data-testid="column"] { gap: 0.5rem; }
        div.stButton > button { width: 100%; border-radius: 8px; height: 3em; }
        </style>
    """, unsafe_allow_html=True)

    with st.sidebar:
        st.title("🌊 实验登录")
        user_id = st.text_input("User ID", placeholder="User_01").strip()
        group_id_ui = st.selectbox("Select Group", [f"Group {i}" for i in range(1, 7)])

    if not user_id:
        st.title("👋 欢迎参加实验")
        st.write("请在左侧侧边栏输入 ID 并选择分组。")
        return

    session_key = f"{user_id}_{group_id_ui}"
    if 'session_key' not in st.session_state or st.session_state['session_key'] != session_key:
        st.session_state['session_key'] = session_key
        img_list = get_cloud_image_list(user_id, group_id_ui)
        st.session_state['image_list'] = img_list
        if not img_list: st.stop()

        completed = get_completed_images(user_id)
        start_idx = 0
        for idx, name in enumerate(img_list):
            if name not in completed:
                start_idx = idx
                break
        if len(img_list) > 0 and start_idx == 0 and img_list[0] in completed:
            start_idx = len(img_list) - 1
        st.session_state['current_index'] = start_idx

    img_list = st.session_state['image_list']
    idx = st.session_state['current_index']

    if idx >= len(img_list):
        st.success("🎉 本组实验已全部完成！")
        return

    current_img_rel_path = img_list[idx]

    # --- 图片显示 (Form外) ---
    try:
        full_image_url = CLOUD_BASE_URL + current_img_rel_path
        col1, col2, col3 = st.columns([1, 10, 1])
        with col2:
            st.image(full_image_url, width="stretch")
    except Exception as e:
        st.error(f"Error loading image: {e}")

    st.markdown("---")

    # --- 评分表单 ---
    # 使用 Form 解决卡顿问题
    with st.form(key=f"rating_form_{idx}"):  # Form key 也可以动态，确保完全隔离

        c1, spacer1, c2, spacer2, c3 = st.columns([10, 1, 10, 1, 10])

        # 关键修改：Key 绑定了当前的 idx
        # 当 idx 改变时，Key 改变，Streamlit 自动创建新滑块（默认值50），无需手动重置！
        # 从而避免了 StreamlitAPIException
        k_content = f"s_content_{idx}"
        k_aesthetic = f"s_aesthetic_{idx}"
        k_quality = f"s_quality_{idx}"

        with c1:
            render_blind_slider("1. 内容 (Content)", k_content)
        with spacer1:
            st.empty()
        with c2:
            render_blind_slider("2. 美学 (Aesthetics)", k_aesthetic)
        with spacer2:
            st.empty()
        with c3:
            render_blind_slider("3. 质量 (Quality)", k_quality)

        st.write("")

        b1, b2, b3 = st.columns([1, 2, 1])
        with b1:
            if idx > 0:
                prev_clicked = st.form_submit_button("⬅️ 上一张", width="stretch")
            else:
                prev_clicked = False
                st.empty()
        with b3:
            next_clicked = st.form_submit_button("下一张 ➡️", type="primary", width="stretch")

    # --- 逻辑处理 ---

    if next_clicked:
        # 获取当前动态 Key 的值
        val_content = st.session_state.get(k_content, 50)
        val_aesthetic = st.session_state.get(k_aesthetic, 50)
        val_quality = st.session_state.get(k_quality, 50)

        with st.spinner("Saving..."):
            save_to_db(user_id, group_id_ui, current_img_rel_path,
                       val_content, val_aesthetic, val_quality)

        if st.session_state['current_index'] < len(img_list) - 1:
            st.session_state['current_index'] += 1
            # 注意：这里不需要手动重置 session_state 了！
            # 因为下一张图的 Key 是 s_content_{idx+1}，是全新的，自动就是 50。
            st.rerun()
        else:
            st.balloons()

    if prev_clicked:
        if st.session_state['current_index'] > 0:
            st.session_state['current_index'] -= 1
            st.rerun()


if __name__ == "__main__":
    main()