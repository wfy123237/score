import streamlit as st
import mysql.connector
import random
import os
import time
from datetime import datetime

# ================= 配置区域 =================
# 阿里云 OSS 图片前缀
CLOUD_BASE_URL = "https://score-1.oss-cn-beijing.aliyuncs.com/Image_3600/"


# ================= 1. 数据库连接 (增加缓存优化) =================

# 【关键优化1】加上这个装饰器，Streamlit 就不会每次操作都重新连接数据库，而是复用连接
# ttl=3600 表示连接缓存 1 小时，防止断连
@st.cache_resource(ttl=3600)
def get_db_connection():
    # 从 Streamlit Secrets 读取配置
    try:
        db_config = st.secrets["connections"]["tidb"]
        return mysql.connector.connect(
            host=db_config["host"],
            user=db_config["user"],
            password=db_config["password"],
            port=db_config["port"],
            database=db_config["database"],
            autocommit=True
        )
    except Exception as e:
        st.error(f"数据库配置错误: {e}")
        return None


def init_db():
    conn = get_db_connection()
    if conn:
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
        c.close()


# 初始化运行
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
    try:
        conn = get_db_connection()
        if not conn: return set()
        c = conn.cursor()
        # 增加 ping 确保连接存活
        if not conn.is_connected():
            conn.reconnect()

        c.execute("SELECT image_name FROM annotations WHERE user_id = %s", (user_id,))
        result = {row[0] for row in c.fetchall()}
        c.close()
        return result
    except Exception:
        return set()


def save_to_db(user_id, group_id, img_path, s1, s2, s3):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        conn = get_db_connection()
        if not conn: return False
        if not conn.is_connected():
            conn.reconnect()

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
                ) \
                """
        values = (user_id, group_id, img_path, s1, s2, s3, timestamp)
        c.execute(query, values)
        c.close()
        return True
    except Exception as e:
        st.error(f"保存失败: {e}")
        return False


# ================= 4. UI 组件封装 =================

def render_blind_slider(label, key):
    """
    渲染表单内的滑块。注意：移除了 on_change 回调，因为表单内不需要实时响应。
    """
    st.markdown(f"#### {label}")

    # 这里的 key 是用来在 session_state 里取值的
    val = st.slider(
        label, 0, 100,
        key=key,
        label_visibility="collapsed",
        format=" "
    )

    # 根据当前滑块的值显示评价文字（注意：在表单模式下，只有提交后这个文字才会变）
    # 如果想实时变，必须不用表单，但会卡。为了流畅，我们牺牲实时文字反馈，
    # 或者接受只有点提交那一刻文字才更新。
    # 这里我们只显示刻度尺，文字反馈可以简化。

    html_oneline = "<div style='position: relative; width: 100%; height: 30px; margin-top: -25px; font-size: 0.8rem; color: #888; line-height: 1.1; pointer-events: none;'><div style='position: absolute; left: 0%; transform: translateX(-50%); text-align: center; white-space: nowrap;'>|<br>极差</div><div style='position: absolute; left: 25%; transform: translateX(-50%); text-align: center; white-space: nowrap;'>|<br>差</div><div style='position: absolute; left: 50%; transform: translateX(-50%); text-align: center; white-space: nowrap;'>|<br>中等</div><div style='position: absolute; left: 75%; transform: translateX(-50%); text-align: center; white-space: nowrap;'>|<br>好</div><div style='position: absolute; left: 100%; transform: translateX(-50%); text-align: center; white-space: nowrap;'>|<br>极好</div></div>"
    st.markdown(html_oneline, unsafe_allow_html=True)

    return val


# ================= 5. 主程序 =================

def main():
    st.set_page_config(page_title="Underwater Aesthetics", layout="wide")
    st.markdown("""
        <style>
        header[data-testid="stHeader"] { display: none !important; }
        div[data-testid="stThumbValue"], div[data-testid="stTickBarMin"], div[data-testid="stTickBarMax"] { opacity: 0 !important; display: none !important; }
        .block-container { padding-top: 20px !important; padding-bottom: 2rem !important; }
        div[data-testid="stImage"] { display: flex; justify-content: center; }
        /* 隐藏表单边框，让它看起来像普通布局 */
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
        # 设置默认值
        st.session_state['default_val'] = 50

    img_list = st.session_state['image_list']
    idx = st.session_state['current_index']

    if idx >= len(img_list):
        st.success("🎉 本组实验已全部完成！")
        return

    current_img_rel_path = img_list[idx]

    # 显示图片
    try:
        full_image_url = CLOUD_BASE_URL + current_img_rel_path
        col1, col2, col3 = st.columns([1, 1, 1])
        with col2:
            st.image(full_image_url, width=300)
    except Exception as e:
        st.error(f"Error loading image: {e}")

    st.markdown("---")

    # 【关键修改】使用 st.form 包裹滑块
    # 这样，在点击“提交”按钮之前，滑动滑块绝对不会触发页面刷新！
    with st.form(key="rating_form", clear_on_submit=True):  # clear_on_submit会让滑块在提交后自动回弹

        c1, spacer1, c2, spacer2, c3 = st.columns([10, 1, 10, 1, 10])

        # 注意：这里我们给 slider 设置了 value=50 (默认值)，去掉了 on_change
        with c1: render_blind_slider("1. 内容 (Content)", "score_c")
        with spacer1: st.empty()
        with c2: render_blind_slider("2. 美学 (Aesthetics)", "score_a")
        with spacer2: st.empty()
        with c3: render_blind_slider("3. 质量 (Quality)", "score_q")

        st.markdown("<br>", unsafe_allow_html=True)

        # 提交按钮放在表单里
        # 居中放置按钮
        b1, b2, b3 = st.columns([1, 1, 1])
        with b2:
            # 这个按钮是唯一的“触发器”
            submit_btn = st.form_submit_button("✅ 提交评分 & 下一张", type="primary", use_container_width=True)

    # 逻辑处理：只有按下按钮，代码才会运行到这里
    if submit_btn:
        # 获取表单里的值
        # 注意：在 st.form 里，我们无法判断用户到底有没有动过滑块（因为没有实时回调）
        # 所以为了流畅度，我们取消了“必须滑动”的强制检测
        # 或者默认相信用户已经调整过了
        s1 = st.session_state.get("score_c", 50)
        s2 = st.session_state.get("score_a", 50)
        s3 = st.session_state.get("score_q", 50)

        with st.spinner("正在提交..."):
            saved = save_to_db(user_id, group_id_ui, current_img_rel_path, s1, s2, s3)

        if saved:
            if st.session_state['current_index'] < len(img_list) - 1:
                st.session_state['current_index'] += 1
                st.rerun()  # 强制刷新进入下一张
            else:
                st.balloons()
                st.success("所有图片已完成！")


if __name__ == "__main__":
    main()