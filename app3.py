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
        autocommit=True
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


try:
    init_db()
except Exception as e:
    st.error(f"数据库连接失败，请检查 Secrets 配置。错误信息: {e}")


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


# ================= 4. UI 组件封装 (Form版) =================

def render_blind_slider(label, key):
    """
    渲染去数字化的盲测滑块 - 适配 Form 模式
    """
    st.markdown(f"#### {label}")

    # 注意：在Form模式下，文字无法随拖动实时变化，这是为了流畅性做的妥协
    # 我们这里只显示滑块和刻度

    val = st.slider(
        label, 0, 100,
        key=key,
        label_visibility="collapsed",
        format=" "  # 隐藏数字
    )

    # HTML 精准刻度尺
    html_oneline = "<div style='position: relative; width: 100%; height: 30px; margin-top: -25px; font-size: 0.8rem; color: #888; line-height: 1.1; pointer-events: none;'><div style='position: absolute; left: 0%; transform: translateX(-50%); text-align: center; white-space: nowrap;'>|<br>极差</div><div style='position: absolute; left: 25%; transform: translateX(-50%); text-align: center; white-space: nowrap;'>|<br>差</div><div style='position: absolute; left: 50%; transform: translateX(-50%); text-align: center; white-space: nowrap;'>|<br>中等</div><div style='position: absolute; left: 75%; transform: translateX(-50%); text-align: center; white-space: nowrap;'>|<br>好</div><div style='position: absolute; left: 100%; transform: translateX(-50%); text-align: center; white-space: nowrap;'>|<br>极好</div></div>"
    st.markdown(html_oneline, unsafe_allow_html=True)
    return val


# ================= 5. 主程序 =================

def main():
    st.set_page_config(page_title="Underwater Aesthetics", layout="wide")

    st.markdown("""
        <style>
        header[data-testid="stHeader"] { display: none !important; }

        /* 隐藏滑块原生的数字气泡 */
        div[data-testid="stThumbValue"], 
        div[data-testid="stTickBarMin"], 
        div[data-testid="stTickBarMax"] { 
            opacity: 0 !important; 
            display: none !important; 
        }

        .block-container { 
            padding-top: 1rem !important; 
            padding-bottom: 2rem !important; 
            max-width: 95% !important; 
        }

        div[data-testid="stImage"] { display: flex; justify-content: center; }
        div[data-testid="column"] { gap: 0.5rem; }

        /* 调整按钮样式 */
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

        # 初始化分数，确保 session state 中有值
        if 's_content' not in st.session_state: st.session_state['s_content'] = 50
        if 's_aesthetic' not in st.session_state: st.session_state['s_aesthetic'] = 50
        if 's_quality' not in st.session_state: st.session_state['s_quality'] = 50

    img_list = st.session_state['image_list']
    idx = st.session_state['current_index']

    if idx >= len(img_list):
        st.success("🎉 本组实验已全部完成！")
        return

    current_img_rel_path = img_list[idx]

    # --- 1. 图片显示区域 ---
    # 图片放在 Form 外部，避免不必要的重新加载
    try:
        full_image_url = CLOUD_BASE_URL + current_img_rel_path

        # 宽屏适配：[1, 10, 1] 比例
        col1, col2, col3 = st.columns([1, 10, 1])
        with col2:
            # 修复 use_container_width 警告，改用 width="stretch"
            st.image(full_image_url, width="stretch")
    except Exception as e:
        st.error(f"Error loading image: {e}")

    st.markdown("---")

    # ================= 核心修改：Form 包裹区域 =================
    # 将滑块和按钮放入 Form 中，阻断滑动时的自动刷新
    with st.form(key="rating_form"):

        c1, spacer1, c2, spacer2, c3 = st.columns([10, 1, 10, 1, 10])

        # 这里的滑块不再有 callbacks，滑动不会触发后台
        with c1:
            render_blind_slider("1. 内容 (Content)", "s_content")
        with spacer1:
            st.empty()
        with c2:
            render_blind_slider("2. 美学 (Aesthetics)", "s_aesthetic")
        with spacer2:
            st.empty()
        with c3:
            render_blind_slider("3. 质量 (Quality)", "s_quality")

        st.write("")  # 间距

        # --- 按钮区域 (作为 Form 的提交按钮) ---
        b1, b2, b3 = st.columns([1, 2, 1])

        with b1:
            if idx > 0:
                # 必须使用 form_submit_button
                prev_clicked = st.form_submit_button("⬅️ 上一张", width="stretch")
            else:
                prev_clicked = False
                st.empty()

        with b3:
            # 下一张也是提交按钮
            next_clicked = st.form_submit_button("下一张 ➡️", type="primary", width="stretch")

    # ================= 逻辑处理区 (Form 提交后执行) =================

    if next_clicked:
        with st.spinner("Saving..."):
            # 直接保存 session_state 中的值（Form 提交时已自动更新）
            save_to_db(user_id, group_id_ui, current_img_rel_path,
                       st.session_state['s_content'],
                       st.session_state['s_aesthetic'],
                       st.session_state['s_quality'])

        if st.session_state['current_index'] < len(img_list) - 1:
            st.session_state['current_index'] += 1
            # 重置分数
            st.session_state['s_content'] = 50
            st.session_state['s_aesthetic'] = 50
            st.session_state['s_quality'] = 50
            st.rerun()  # 刷新进入下一张
        else:
            st.balloons()

    if prev_clicked:
        if st.session_state['current_index'] > 0:
            st.session_state['current_index'] -= 1
            st.rerun()


if __name__ == "__main__":
    main()