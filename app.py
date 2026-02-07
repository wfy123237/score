import streamlit as st
import mysql.connector
import random
import os
import time
from datetime import datetime

# ================= 配置区域 =================
# 阿里云 OSS 图片前缀
CLOUD_BASE_URL = "https://score-1.oss-cn-beijing.aliyuncs.com/Image_3600/"


# ================= 1. 数据库连接 (MySQL/TiDB) =================

def get_db_connection():
    # 从 Streamlit Secrets 读取配置
    db_config = st.secrets["connections"]["tidb"]

    return mysql.connector.connect(
        host=db_config["host"],
        user=db_config["user"],
        password=db_config["password"],
        port=db_config["port"],
        database=db_config["database"],
        autocommit=True  # 自动提交事务
    )


def init_db():
    """初始化数据库表"""
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


# 初始化运行一次
try:
    init_db()
except Exception as e:
    st.error(f"数据库连接失败，请检查 Secrets 配置。错误信息: {e}")


# ================= 2. 核心逻辑功能 =================

def get_cloud_image_list(user_id, group_id_str):
    """读取 Github 上的 image_names.txt"""
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
    """从 MySQL 读取该用户已完成的图片"""
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


# ================= 3. 交互检测与 UI =================

def mark_content_touched(): st.session_state['touched_content'] = True


def mark_aesthetic_touched(): st.session_state['touched_aesthetic'] = True


def mark_quality_touched(): st.session_state['touched_quality'] = True


@st.dialog("⚠️ 还有未确认的评分")
def show_warning_dialog():
    st.write("为了保证实验数据的有效性，**所有三个维度**都必须经过您的确认。")
    st.warning("检测到您有滑块未被移动过。")
    st.write("即使您认为 50 分是合适的，也请**轻微拖动一下滑块**（例如拖到 51 再拖回 50），让系统确认您已思考过。")
    if st.button("我明白了，去修改", type="primary"):
        st.rerun()


def render_blind_slider(label, key, touch_callback):
    st.markdown(f"#### {label}")
    current_val = st.session_state.get(key, 50)
    rating_text = ""
    if 0 <= current_val <= 20:
        rating_text = "极差"
    elif 21 <= current_val <= 40:
        rating_text = "差"
    elif 41 <= current_val <= 60:
        rating_text = "中等"
    elif 61 <= current_val <= 80:
        rating_text = "好"
    elif 81 <= current_val <= 100:
        rating_text = "极好"

    st.markdown(f"<div class='current-rating'>当前评价: {rating_text}</div>", unsafe_allow_html=True)
    val = st.slider(label, 0, 100, key=key, label_visibility="collapsed", on_change=touch_callback, format=" ")

    # --- 恢复：原本详细的刻度尺 HTML 代码 ---
    html_oneline = "<div style='position: relative; width: 100%; height: 30px; margin-top: -25px; font-size: 0.8rem; color: #888; line-height: 1.1; pointer-events: none;'><div style='position: absolute; left: 0%; transform: translateX(-50%); text-align: center; white-space: nowrap;'>|<br>极差</div><div style='position: absolute; left: 25%; transform: translateX(-50%); text-align: center; white-space: nowrap;'>|<br>差</div><div style='position: absolute; left: 50%; transform: translateX(-50%); text-align: center; white-space: nowrap;'>|<br>中等</div><div style='position: absolute; left: 75%; transform: translateX(-50%); text-align: center; white-space: nowrap;'>|<br>好</div><div style='position: absolute; left: 100%; transform: translateX(-50%); text-align: center; white-space: nowrap;'>|<br>极好</div></div>"
    st.markdown(html_oneline, unsafe_allow_html=True)
    return val


# ================= 5. 主程序 =================

def main():
    st.set_page_config(page_title="Underwater Aesthetics", layout="wide")

    st.markdown("""
        <style>
        header[data-testid="stHeader"] { display: none !important; }

        /* 调整整体容器的上间距，尽量靠上 */
        .block-container { 
            padding-top: 1rem !important; 
            padding-bottom: 2rem !important; 
            max-width: 95% !important; /* 宽屏模式 */
        }

        /* 隐藏原生数值显示 */
        div[data-testid="stThumbValue"], div[data-testid="stTickBarMin"], div[data-testid="stTickBarMax"] { opacity: 0 !important; display: none !important; }

        .current-rating { font-size: 1.1rem; font-weight: bold; color: #FF4B4B; margin-bottom: 5px; }

        div[data-testid="stImage"] { display: flex; justify-content: center; }

        /* 调整列间距 */
        div[data-testid="column"] { gap: 0.5rem; }

        /* 调整按钮高度 */
        div.stButton > button {
            width: 100%;
            border-radius: 8px;
            height: 3em;
        }
        </style>
    """, unsafe_allow_html=True)

    with st.sidebar:
        st.title("🌊 实验登录")
        user_id = st.text_input("User ID", placeholder="User_01").strip()
        group_id_ui = st.selectbox("Select Group", [f"Group {i}" for i in range(1, 7)])
        st.info("⚠️ 必须滑动所有三个滑块才能提交。")

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
        st.session_state['s_content'] = 50
        st.session_state['s_aesthetic'] = 50
        st.session_state['s_quality'] = 50
        st.session_state['touched_content'] = False
        st.session_state['touched_aesthetic'] = False
        st.session_state['touched_quality'] = False

    img_list = st.session_state['image_list']
    idx = st.session_state['current_index']

    if idx >= len(img_list):
        st.success("🎉 本组实验已全部完成！")
        return

    current_img_rel_path = img_list[idx]

    # --- 1. 图片显示区域 (大图) ---
    try:
        full_image_url = CLOUD_BASE_URL + current_img_rel_path

        # 使用 [1, 10, 1] 比例让图片区域尽可能大
        col1, col2, col3 = st.columns([1, 10, 1])
        with col2:
            # use_container_width=True 让图片撑满列宽
            st.image(full_image_url, use_container_width=True)
    except Exception as e:
        st.error(f"Error loading image: {e}")

    # 分隔线
    st.markdown("---")

    # --- 2. 评分滑块区域 ---
    with st.container():
        c1, spacer1, c2, spacer2, c3 = st.columns([10, 1, 10, 1, 10])
        with c1: render_blind_slider("1. 内容 (Content)", "s_content", mark_content_touched)
        with spacer1: st.empty()
        with c2: render_blind_slider("2. 美学 (Aesthetics)", "s_aesthetic", mark_aesthetic_touched)
        with spacer2: st.empty()
        with c3: render_blind_slider("3. 质量 (Quality)", "s_quality", mark_quality_touched)

    # --- 这里移除了原来的 st.markdown("---") 虚线 ---

    # 增加一点点间距，避免按钮贴到刻度尺文字上
    st.write("")

    # --- 按钮逻辑 ---
    def next_action():
        if not (st.session_state.get('touched_content', False) and
                st.session_state.get('touched_aesthetic', False) and
                st.session_state.get('touched_quality', False)):
            show_warning_dialog()
            return

        with st.spinner("Saving..."):
            save_to_db(user_id, group_id_ui, current_img_rel_path,
                       st.session_state['s_content'],
                       st.session_state['s_aesthetic'],
                       st.session_state['s_quality'])

        if st.session_state['current_index'] < len(img_list) - 1:
            st.session_state['current_index'] += 1
            st.session_state['s_content'] = 50
            st.session_state['s_aesthetic'] = 50
            st.session_state['s_quality'] = 50
            st.session_state['touched_content'] = False
            st.session_state['touched_aesthetic'] = False
            st.session_state['touched_quality'] = False
        else:
            st.balloons()

    def prev_action():
        if st.session_state['current_index'] > 0:
            st.session_state['current_index'] -= 1

    # --- 3. 按钮区域 (上移，紧跟滑块) ---
    b1, b2, b3 = st.columns([1, 2, 1])
    with b1:
        if idx > 0:
            st.button("⬅️ 上一张", on_click=prev_action, use_container_width=True)
    with b3:
        st.button("下一张 ➡️", on_click=next_action, type="primary", use_container_width=True)


if __name__ == "__main__":
    main()