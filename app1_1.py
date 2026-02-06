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
    print(f"用户[{user_id}]的随机种子数: {seed_val}")
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


# ================= 3. 交互检测与弹窗 =================

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


# ================= 4. UI 组件封装 =================

def render_blind_slider(label, key, touch_callback):
    """
    渲染去数字化的盲测滑块，保留详细刻度尺
    """
    st.markdown(f"#### {label}")

    # 1. 实时反馈文字
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

    # 2. 滑块
    val = st.slider(
        label, 0, 100,
        key=key,
        label_visibility="collapsed",
        on_change=touch_callback,
        format=" "
    )

    # 3. HTML 精准刻度尺 (完整版)
    html_oneline = "<div style='position: relative; width: 100%; height: 30px; margin-top: -25px; font-size: 0.8rem; color: #888; line-height: 1.1; pointer-events: none;'><div style='position: absolute; left: 0%; transform: translateX(-50%); text-align: center; white-space: nowrap;'>|<br>极差</div><div style='position: absolute; left: 25%; transform: translateX(-50%); text-align: center; white-space: nowrap;'>|<br>差</div><div style='position: absolute; left: 50%; transform: translateX(-50%); text-align: center; white-space: nowrap;'>|<br>中等</div><div style='position: absolute; left: 75%; transform: translateX(-50%); text-align: center; white-space: nowrap;'>|<br>好</div><div style='position: absolute; left: 100%; transform: translateX(-50%); text-align: center; white-space: nowrap;'>|<br>极好</div></div>"

    st.markdown(html_oneline, unsafe_allow_html=True)

    return val


# ================= 5. 主程序 =================

def main():
    st.set_page_config(page_title="Underwater Aesthetics", layout="wide")

    st.markdown("""
        <style>
        /* 1. 彻底隐藏 Streamlit 顶部的黑条导航栏 */
        header[data-testid="stHeader"] { display: none !important; }

        /* 2. 隐藏滑块数字 */
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

        /* 3. 调整顶部间距和宽度 */
        .block-container { 
            padding-top: 1rem !important; 
            padding-bottom: 2rem !important;
            max-width: 95% !important; /* 宽屏适配 */
        }

        /* 4. 图片居中 */
        div[data-testid="stImage"] {
            display: flex;
            justify-content: center; 
        }

        /* 5. 调整列间距 */
        div[data-testid="column"] { gap: 0.5rem; }

        /* 6. 调整按钮高度 */
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
        st.info("⚠️ 注意：必须滑动所有三个滑块才能提交。")

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

        st.session_state['s_content'] = 50
        st.session_state['s_aesthetic'] = 50
        st.session_state['s_quality'] = 50
        st.session_state['touched_content'] = False
        st.session_state['touched_aesthetic'] = False
        st.session_state['touched_quality'] = False

    img_list = st.session_state['image_list']
    idx = st.session_state['current_index']
    group_path = st.session_state['group_path']

    if not img_list: return
    if idx >= len(img_list):
        st.success("🎉 本组实验已全部完成！感谢您的参与。")
        return

    current_img_name = img_list[idx]

    # --- 图片显示区 (大图模式) ---
    try:
        img_full_path = group_path / current_img_name
        image = Image.open(img_full_path)

        # 【修改】使用 width="stretch" 替代 use_container_width=True
        col1, col2, col3 = st.columns([1, 10, 1])
        with col2:
            st.image(image, width="stretch")

    except Exception as e:
        st.error(f"Error loading image: {e}")

    # 分隔线
    st.markdown("---")

    # --- 盲测滑块区 ---
    with st.container():
        c1, spacer1, c2, spacer2, c3 = st.columns([10, 1, 10, 1, 10])

        with c1: render_blind_slider("1. 内容 (Content)", "s_content", mark_content_touched)
        with spacer1: st.empty()
        with c2: render_blind_slider("2. 美学 (Aesthetics)", "s_aesthetic", mark_aesthetic_touched)
        with spacer2: st.empty()
        with c3: render_blind_slider("3. 质量 (Quality)", "s_quality", mark_quality_touched)

    st.write("")  # 微小缓冲

    # --- 导航逻辑 ---
    def next_action():
        if not (st.session_state.get('touched_content', False) and
                st.session_state.get('touched_aesthetic', False) and
                st.session_state.get('touched_quality', False)):
            show_warning_dialog()
            return

        saved = save_to_db(user_id, group_id_ui, current_img_name,
                           st.session_state['s_content'],
                           st.session_state['s_aesthetic'],
                           st.session_state['s_quality'])
        if saved:
            if st.session_state['current_index'] < len(img_list) - 1:
                st.session_state['current_index'] += 1
                st.session_state['s_content'] = 50
                st.session_state['s_aesthetic'] = 50
                st.session_state['s_quality'] = 50
                st.session_state['touched_content'] = False
                st.session_state['touched_aesthetic'] = False
                st.session_state['touched_quality'] = False
                # 注意：这里删除了 st.rerun()，以消除黄色警告
            else:
                st.balloons()

    def prev_action():
        if st.session_state['current_index'] > 0:
            st.session_state['current_index'] -= 1
            # 注意：这里删除了 st.rerun()，以消除黄色警告

    # --- 按钮区域 (上移) ---
    # 【修改】这里将 st.button 的 use_container_width=True 严格替换为 width="stretch"
    b1, b2, b3 = st.columns([1, 2, 1])
    with b1:
        if idx > 0:
            st.button("⬅️ 上一张", on_click=prev_action, width="stretch")
    with b3:
        st.button("下一张 ➡️", on_click=next_action, type="primary", width="stretch")


if __name__ == "__main__":
    main()