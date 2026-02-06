import streamlit as st
import mysql.connector
import random
import os
import time
from datetime import datetime

# ================= 配置区域 =================
# 阿里云 OSS 图片前缀
CLOUD_BASE_URL = "https://score-1.oss-cn-beijing.aliyuncs.com/Image_3600/"


# ================= 1. 数据库连接 (稳定版：移除缓存) =================
def get_db_connection():
    """每次调用建立一个新的连接，用完自动关闭"""
    try:
        db_config = st.secrets["connections"]["tidb"]
        return mysql.connector.connect(
            host=db_config["host"],
            user=db_config["user"],
            password=db_config["password"],
            port=db_config["port"],
            database=db_config["database"],
            autocommit=True,
            connection_timeout=10
        )
    except Exception as e:
        st.error(f"数据库连接失败: {e}")
        return None


def init_db():
    """初始化建表，增加了重试机制"""
    conn = None
    try:
        conn = get_db_connection()
        if conn and conn.is_connected():
            c = conn.cursor()
            c.execute('''
                      CREATE TABLE IF NOT EXISTS annotations
                      (
                          user_id VARCHAR(50),
                          group_id VARCHAR(50),
                          image_name VARCHAR(255),
                          score_content INT,
                          score_aesthetic INT,
                          score_quality INT,
                          timestamp DATETIME,
                          PRIMARY KEY (user_id, image_name)
                      )
                      ''')
            c.close()
    except Exception as e:
        st.error(f"初始化数据库失败: {e}")
    finally:
        if conn and conn.is_connected():
            conn.close()


init_db()


# ================= 2. 核心逻辑功能 =================
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
    conn = None
    try:
        conn = get_db_connection()
        if not conn:
            return set()

        c = conn.cursor()
        c.execute("SELECT image_name FROM annotations WHERE user_id = %s", (user_id,))
        result = {row[0] for row in c.fetchall()}
        c.close()
        return result
    except Exception:
        return set()
    finally:
        if conn and conn.is_connected():
            conn.close()


def get_saved_scores(user_id, image_name):
    """获取用户对指定图片已保存的评分，用于回退时恢复滑块值"""
    conn = None
    try:
        conn = get_db_connection()
        if not conn:
            return 50, 50, 50

        c = conn.cursor()
        c.execute("""
            SELECT score_content, score_aesthetic, score_quality 
            FROM annotations 
            WHERE user_id = %s AND image_name = %s
        """, (user_id, image_name))
        result = c.fetchone()
        c.close()
        # 如果有保存的评分则返回，否则返回默认值50
        return result if result else (50, 50, 50)
    except Exception:
        return 50, 50, 50
    finally:
        if conn and conn.is_connected():
            conn.close()


def save_to_db(user_id, group_id, img_path, s1, s2, s3):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = None
    try:
        conn = get_db_connection()
        if not conn:
            return False

        c = conn.cursor()
        query = """
                REPLACE INTO annotations 
                (user_id, group_id, image_name, score_content, score_aesthetic, score_quality, timestamp)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """
        values = (user_id, group_id, img_path, s1, s2, s3, timestamp)
        c.execute(query, values)
        c.close()
        return True
    except Exception as e:
        st.error(f"保存失败: {e}")
        return False
    finally:
        if conn and conn.is_connected():
            conn.close()


# ================= 4. UI 组件封装 =================
def render_blind_slider(label, key, default_val=50):
    st.markdown(f"#### {label}")
    val = st.slider(
        label, 0, 100,
        value=default_val,  # 新增：支持传入默认值（恢复已保存的评分）
        key=key,
        label_visibility="collapsed",
        format=" "
    )

    html_oneline = "<div style='position: relative; width: 100%; height: 30px; margin-top: -25px; font-size: 0.8rem; color: #888; line-height: 1.1; pointer-events: none;'><div style='position: absolute; left: 0%; transform: translateX(-50%); text-align: center; white-space: nowrap;'>|<br>极差</div><div style='position: absolute; left: 25%; transform: translateX(-50%); text-align: center; white-space: nowrap;'>|<br>差</div><div style='position: absolute; left: 50%; transform: translateX(-50%); text-align: center; white-space: nowrap;'>|<br>中等</div><div style='position: absolute; left: 75%; transform: translateX(-50%); text-align: center; white-space: nowrap;'>|<br>好</div><div style='position: absolute; left: 100%; transform: translateX(-50%); text-align: center; white-space: nowrap;'>|<br>极好</div></div>"
    st.markdown(html_oneline, unsafe_allow_html=True)

    return val


# ================= 5. 主程序 =================
def main():
    st.set_page_config(
        page_title="Underwater Aesthetics",
        layout="wide",
        initial_sidebar_state="expanded"
    )

    st.markdown("""
        <style>
        div[data-testid="stThumbValue"], 
        div[data-testid="stTickBarMin"], 
        div[data-testid="stTickBarMax"] {
            opacity: 0 !important;
            display: none !important;
        }
        .current-rating { font-size: 1.1rem; font-weight: bold; color: #FF4B4B; margin-bottom: 5px; }
        .block-container { padding-top: 20px !important; padding-bottom: 2rem !important; }
        div[data-testid="stImage"] { display: flex; justify-content: center; }
        div[data-testid="stForm"] { border: none; padding: 0; }
        </style>
    """, unsafe_allow_html=True)

    with st.sidebar:
        st.title("🌊 实验登录")
        user_id = st.text_input("User ID", placeholder="输入编号 (如 User_01)").strip()
        group_id_ui = st.selectbox("Select Group", [f"Group {i}" for i in range(1, 7)])
        st.info("⚠️ 滑动下方三个滑块，然后点击按钮提交。")

    if not user_id:
        st.title("👋 欢迎参加实验")
        st.write("请在左侧侧边栏输入 ID 并选择分组。")
        return

    # 会话状态初始化
    session_key = f"{user_id}_{group_id_ui}"
    if 'session_key' not in st.session_state or st.session_state['session_key'] != session_key:
        st.session_state['session_key'] = session_key
        img_list = get_cloud_image_list(user_id, group_id_ui)
        st.session_state['image_list'] = img_list
        if not img_list:
            st.stop()

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

    # 所有图片完成的提示
    if idx >= len(img_list):
        st.success("🎉 本组实验已全部完成！")
        return

    current_img_rel_path = img_list[idx]
    # 获取当前图片已保存的评分（回退时恢复滑块值）
    saved_c, saved_a, saved_q = get_saved_scores(user_id, current_img_rel_path)

    # 显示图片
    try:
        full_image_url = CLOUD_BASE_URL + current_img_rel_path
        col1, col2, col3 = st.columns([1, 1, 1])
        with col2:
            st.image(full_image_url, width=300)
    except Exception as e:
        st.error(f"Error loading image: {e}")

    st.markdown("---")

    # 评分表单
    with st.form(key="rating_form", clear_on_submit=True):
        c1, spacer1, c2, spacer2, c3 = st.columns([10, 1, 10, 1, 10])
        with c1:
            render_blind_slider("1. 内容 (Content)", "score_c", saved_c)
        with spacer1:
            st.empty()
        with c2:
            render_blind_slider("2. 美学 (Aesthetics)", "score_a", saved_a)
        with spacer2:
            st.empty()
        with c3:
            render_blind_slider("3. 质量 (Quality)", "score_q", saved_q)

        st.markdown("<br>", unsafe_allow_html=True)

        # 按钮布局：上一张 + 提交/下一张
        b1, b2, b3 = st.columns([1, 1, 1])
        with b1:
            # 上一张按钮：仅当当前索引>0时显示
            prev_btn = st.form_submit_button("⬅️ 上一张", use_container_width=True)
        with b2:
            submit_btn = st.form_submit_button("✅ 提交评分 & 下一张", type="primary", use_container_width=True)
        with b3:
            st.empty()  # 占位，保持布局对称

    # 处理上一张逻辑
    if prev_btn:
        if idx > 0:
            st.session_state['current_index'] -= 1
            st.rerun()  # 重新渲染页面，显示上一张图片

    # 处理提交/下一张逻辑
    if submit_btn:
        s1 = st.session_state.get("score_c", 50)
        s2 = st.session_state.get("score_a", 50)
        s3 = st.session_state.get("score_q", 50)

        with st.spinner("正在提交..."):
            saved = save_to_db(user_id, group_id_ui, current_img_rel_path, s1, s2, s3)

        if saved:
            if idx < len(img_list) - 1:
                st.session_state['current_index'] += 1
                st.rerun()
            else:
                st.balloons()
                st.success("所有图片已完成！")


if __name__ == "__main__":
    main()