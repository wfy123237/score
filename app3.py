import streamlit as st
import sqlite3
import random
import os
import time
from datetime import datetime
from pathlib import Path
from PIL import Image

# ================= 配置区域 =================
# 请确保此路径在您的电脑上存在
REAL_IMAGE_ROOT = r"D:\PyCharm\PythonProject4\Image_3600"
DB_NAME = "underwater_aesthetics.db"


# ================= 1. 数据库初始化 =================

def init_db():
    conn = sqlite3.connect(DB_NAME, check_same_thread=False, timeout=15)
    c = conn.cursor()
    c.execute('''
              CREATE TABLE IF NOT EXISTS annotations
              (
                  user_id
                  TEXT,
                  group_id
                  TEXT,
                  image_name
                  TEXT,
                  score_content
                  INTEGER,
                  score_aesthetic
                  INTEGER,
                  score_quality
                  INTEGER,
                  timestamp
                  DATETIME,
                  PRIMARY
                  KEY
              (
                  user_id,
                  image_name
              )
                  )
              ''')
    conn.commit()
    return conn


conn = init_db()


# ================= 2. 核心逻辑功能 =================

def get_deterministic_image_list(user_id, group_id_str):
    folder_name = group_id_str.replace(" ", "_")
    group_path = Path(REAL_IMAGE_ROOT) / folder_name

    if not group_path.exists():
        st.error(f"❌ 找不到文件夹: {group_path}")
        return [], group_path

    images = [f.name for f in group_path.iterdir() if f.suffix.lower() in ['.jpg', '.jpeg', '.png', '.bmp']]
    images.sort()

    seed_val = sum(ord(c) for c in user_id)
    # print(f"用户[{user_id}]的随机种子数: {seed_val}")
    rng = random.Random(seed_val)
    rng.shuffle(images)

    return images, group_path


def get_completed_images(user_id):
    try:
        c = conn.cursor()
        c.execute("SELECT image_name FROM annotations WHERE user_id = ?", (user_id,))
        return {row[0] for row in c.fetchall()}
    except Exception:
        return set()


def save_to_db(user_id, group_id, img_name, s1, s2, s3):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    for attempt in range(5):
        try:
            c = conn.cursor()
            c.execute("""
                INSERT OR REPLACE INTO annotations 
                (user_id, group_id, image_name, score_content, score_aesthetic, score_quality, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (user_id, group_id, img_name, s1, s2, s3, timestamp))
            conn.commit()
            return True
        except sqlite3.OperationalError as e:
            if "locked" in str(e):
                time.sleep(0.1 * (attempt + 1))
            else:
                return False
    return False


# ================= 4. UI 组件封装 =================

def render_blind_slider(label, key):
    """
    渲染去数字化的盲测滑块 - Form 版 (去掉了回调函数)
    """
    st.markdown(f"#### {label}")

    # 1. 实时反馈文字
    # 注意：在 Form 中，session_state 只有在提交后才会更新，
    # 所以滑动时这里的文字不会实时变，这是 Form 的特性。
    # 为了体验，我们这里直接读取当前的 key 值 (默认为50)
    current_val = st.session_state.get(key, 50)

    # 2. 滑块
    # 关键修改：移除了 on_change，完全由 Form 控制
    val = st.slider(
        label, 0, 100,
        key=key,
        label_visibility="collapsed",
        format=" "
    )

    # 3. HTML 精准刻度尺
    html_oneline = "<div style='position: relative; width: 100%; height: 30px; margin-top: -25px; font-size: 0.8rem; color: #888; line-height: 1.1; pointer-events: none;'><div style='position: absolute; left: 0%; transform: translateX(-50%); text-align: center; white-space: nowrap;'>|<br>极差</div><div style='position: absolute; left: 25%; transform: translateX(-50%); text-align: center; white-space: nowrap;'>|<br>差</div><div style='position: absolute; left: 50%; transform: translateX(-50%); text-align: center; white-space: nowrap;'>|<br>中等</div><div style='position: absolute; left: 75%; transform: translateX(-50%); text-align: center; white-space: nowrap;'>|<br>好</div><div style='position: absolute; left: 100%; transform: translateX(-50%); text-align: center; white-space: nowrap;'>|<br>极好</div></div>"

    st.markdown(html_oneline, unsafe_allow_html=True)

    return val


# ================= 5. 主程序 =================

def main():
    st.set_page_config(page_title="Underwater Aesthetics", layout="wide")

    st.markdown("""
        <style>
        header[data-testid="stHeader"] { display: none !important; }

        div[data-testid="stThumbValue"], 
        div[data-testid="stTickBarMin"], 
        div[data-testid="stTickBarMax"] {
            opacity: 0 !important;
            color: transparent !important;
            display: none !important;
        }

        .current-rating {
            font-size: 1.1rem; 
            font-weight: bold;
            color: #FF4B4B;
            margin-bottom: 5px;
        }

        .block-container { 
            padding-top: 1rem !important; 
            padding-bottom: 2rem !important;
            max-width: 95% !important;
        }

        div[data-testid="stImage"] {
            display: flex;
            justify-content: center; 
        }

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
        user_id = st.text_input("User ID", placeholder="输入编号 (如 User_01)").strip()
        group_id_ui = st.selectbox("Select Group", [f"Group {i}" for i in range(1, 7)])

    if not user_id:
        st.title("👋 欢迎参加实验")
        st.write("请在左侧侧边栏输入 ID 并选择分组。")
        return

    # --- 状态初始化 ---
    session_key = f"{user_id}_{group_id_ui}"
    if 'session_key' not in st.session_state or st.session_state['session_key'] != session_key:
        st.session_state['session_key'] = session_key

        img_list, group_path = get_deterministic_image_list(user_id, group_id_ui)
        st.session_state['image_list'] = img_list
        st.session_state['group_path'] = group_path

        completed = get_completed_images(user_id)
        start_idx = 0
        for idx, name in enumerate(img_list):
            if name not in completed:
                start_idx = idx
                break
        if len(img_list) > 0 and start_idx == 0 and img_list[0] in completed:
            start_idx = len(img_list) - 1

        st.session_state['current_index'] = start_idx

        # 初始化滑块值
        if 's_content' not in st.session_state: st.session_state['s_content'] = 50
        if 's_aesthetic' not in st.session_state: st.session_state['s_aesthetic'] = 50
        if 's_quality' not in st.session_state: st.session_state['s_quality'] = 50

    img_list = st.session_state['image_list']
    idx = st.session_state['current_index']
    group_path = st.session_state['group_path']

    if not img_list: return
    if idx >= len(img_list):
        st.success("🎉 本组实验已全部完成！感谢您的参与。")
        return

    current_img_name = img_list[idx]

    # --- 图片显示区 ---
    # 图片放在 Form 外面，避免提交时重新加载导致的闪烁
    try:
        img_full_path = group_path / current_img_name
        image = Image.open(img_full_path)

        col1, col2, col3 = st.columns([1, 10, 1])
        with col2:
            st.image(image, width="stretch")

    except Exception as e:
        st.error(f"Error loading image: {e}")

    st.markdown("---")

    # ================= 核心修改：使用 st.form 包裹交互区 =================
    # 只有点击 Form 内的 Submit 按钮（下一张/上一张）时，才会刷新页面
    with st.form(key="rating_form"):

        c1, spacer1, c2, spacer2, c3 = st.columns([10, 1, 10, 1, 10])

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

        st.write("")

        # --- 按钮区域 (作为表单的提交按钮) ---
        b1, b2, b3 = st.columns([1, 2, 1])
        with b1:
            # 只有 idx > 0 才显示上一张，但为了布局对齐，可以用 empty 占位
            if idx > 0:
                prev_submitted = st.form_submit_button("⬅️ 上一张", width="stretch")
            else:
                prev_submitted = False
                st.empty()  # 占位

        with b3:
            # 下一张是主要的提交按钮
            next_submitted = st.form_submit_button("下一张 ➡️", type="primary", width="stretch")

    # ================= 逻辑处理区 (在 Form 外部处理提交结果) =================

    if next_submitted:
        # 1. 保存数据 (直接读取 session_state 中的值)
        # 移除了"是否触摸"的强制检测，确保流畅
        save_to_db(user_id, group_id_ui, current_img_name,
                   st.session_state['s_content'],
                   st.session_state['s_aesthetic'],
                   st.session_state['s_quality'])

        # 2. 只有在最后一张之前才跳转
        if st.session_state['current_index'] < len(img_list) - 1:
            st.session_state['current_index'] += 1
            # 重置滑块为 50
            st.session_state['s_content'] = 50
            st.session_state['s_aesthetic'] = 50
            st.session_state['s_quality'] = 50
            st.rerun()
        else:
            st.balloons()

    if prev_submitted:
        if st.session_state['current_index'] > 0:
            st.session_state['current_index'] -= 1
            # 这里可以不重置滑块，或者重置，看需求。目前保持状态。
            st.rerun()


if __name__ == "__main__":
    main()