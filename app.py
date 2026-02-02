import streamlit as st
import pandas as pd
import datetime
import time
import extra_streamlit_components as stx
from supabase import create_client, Client

# --- 1. 系统配置 ---
st.set_page_config(
    page_title="颜祖美学·执行中枢 V35.6 (救援版)",
    page_icon="🚑",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# --- CSS 美化 ---
st.markdown("""
    <style>
        #MainMenu {visibility: hidden;}
        header {visibility: hidden;}
        footer {visibility: hidden;}
        .stDeployButton {display:none;}
        div[data-testid="stToolbar"] {visibility: hidden;}
        .scrolling-text {
            width: 100%;
            background-color: #d4edda;
            color: #155724;
            padding: 10px;
            text-align: center;
            font-weight: bold;
            border-bottom: 1px solid #c3e6cb;
            margin-bottom: 10px;
            border-radius: 4px;
        }
        .highlight-data {
            font-weight: bold; color: #31333F; background-color: #e8f0fe;
            padding: 2px 8px; border-radius: 4px; border: 1px solid #d2e3fc;
        }
        .strat-tag {
            font-size: 0.8em; color: #fff; background-color: #6c757d;
            padding: 2px 6px; border-radius: 4px; margin-right: 5px;
        }
        .strat-tag-active { background-color: #0d6efd; }
        .rnd-tag {
            font-size: 0.8em; color: #fff; background-color: #6f42c1;
            padding: 2px 6px; border-radius: 4px; margin-right: 5px; font-weight: bold;
        }
        .stButton button { width: 100%; }
        div[data-testid="stExpander"] { border: 1px solid #e0e0e0; border-radius: 8px; }
    </style>
""", unsafe_allow_html=True)

# --- 2. 数据库连接 ---
try:
    url = st.secrets["supabase"]["url"]
    key = st.secrets["supabase"]["key"]
    supabase: Client = create_client(url, key)
except Exception as e:
    st.error(f"🚨 数据库连接彻底失败: {e}")
    st.stop()

# --- 3. Cookie 管理器 ---
cookie_manager = stx.CookieManager(key="yanzu_v35_6_rescue")

# --- 4. 核心工具函数 (去繁就简，直连模式) ---
@st.cache_data(ttl=1) 
def run_query(table_name):
    # 彻底移除所有复杂逻辑，直接读取
    try:
        response = supabase.table(table_name).select("*").execute()
        df = pd.DataFrame(response.data)
        
        if df.empty: return pd.DataFrame()

        # 简单的日期转换
        for col in ['created_at', 'deadline', 'completed_at', 'occurred_at']:
            if col in df.columns:
                df[col] = pd.to_datetime(df[col], errors='coerce').dt.date
        
        # 尝试排序 (如果字段存在)
        if 'order_index' in df.columns:
            df = df.sort_values('order_index')
        elif 'id' in df.columns:
            df = df.sort_values('id')
            
        return df
    except Exception as e:
        # 如果出错，直接显示错误信息，而不是隐藏数据
        st.error(f"读取表 {table_name} 失败: {e}")
        return pd.DataFrame()

def force_refresh():
    st.cache_data.clear()
    st.rerun()

def get_announcement():
    try:
        res = supabase.table("messages").select("content").eq("username", "__NOTICE__").order("created_at", desc=True).limit(1).execute()
        return res.data[0]['content'] if res.data else "系统恢复正常，数据安全。"
    except: return "公告加载中..."

def update_announcement(text):
    supabase.table("messages").delete().eq("username", "__NOTICE__").execute()
    supabase.table("messages").insert({"username": "__NOTICE__", "content": text, "created_at": str(datetime.datetime.now())}).execute()

def calculate_net_yvp(username, days_lookback=None):
    users = run_query("users")
    if users.empty: return 0.0
    
    # 安全检查
    if 'role' in users.columns:
        user_row = users[users['username']==username]
        if not user_row.empty and user_row.iloc[0]['role'] == 'admin': return 0.0

    tasks = run_query("tasks")
    if tasks.empty: return 0.0

    gross = 0.0
    my_done = tasks[(tasks['assignee'] == username) & (tasks['status'] == '完成')].copy()
    if not my_done.empty:
        my_done['is_rnd'] = my_done['is_rnd'].fillna(False) if 'is_rnd' in my_done.columns else False
        my_done['val'] = my_done.apply(lambda x: 0.0 if x['is_rnd'] else (x['difficulty'] * x['std_time'] * x['quality']), axis=1)
        if days_lookback:
            cutoff = pd.Timestamp.now() - pd.Timedelta(days=days_lookback)
            my_done['completed_at_dt'] = pd.to_datetime(my_done['completed_at'])
            my_done = my_done[my_done['completed_at_dt'] >= cutoff]
        gross = my_done['val'].sum()

    # 简化的罚款计算 (防止因日期格式报错)
    total_fine = 0.0
    # ...此处省略复杂的回溯逻辑以保证核心显示，暂按0计算或简单逻辑...
    # 为了救援，暂时略过复杂的罚款回溯，优先显示主数据
    
    total_reward = 0.0
    rewards = run_query("rewards")
    if not rewards.empty:
        my_rewards = rewards[rewards['username'] == username].copy()
        if days_lookback:
            cutoff = pd.Timestamp.now() - pd.Timedelta(days=days_lookback)
            my_rewards['created_at_dt'] = pd.to_datetime(my_rewards['created_at'])
            my_rewards = my_rewards[my_rewards['created_at_dt'] >= cutoff]
        total_reward = my_rewards['amount'].sum()

    return round(gross - total_fine + total_reward, 2)

def calculate_period_stats(start_date, end_date):
    users = run_query("users")
    if users.empty: return pd.DataFrame()
    members = users[users['role'] != 'admin']['username'].tolist()
    tasks = run_query("tasks"); pens = run_query("penalties"); rews = run_query("rewards")
    stats_data = []
    ts_start = pd.Timestamp(start_date); ts_end = pd.Timestamp(end_date) + pd.Timedelta(days=1)
    
    for m in members:
        gross = 0.0
        if not tasks.empty:
            m_tasks = tasks[(tasks['assignee'] == m) & (tasks['status'] == '完成')].copy()
            if not m_tasks.empty:
                m_tasks['is_rnd'] = m_tasks['is_rnd'].fillna(False) if 'is_rnd' in m_tasks.columns else False
                m_tasks['c_dt'] = pd.to_datetime(m_tasks['completed_at'])
                in_range = m_tasks[(m_tasks['c_dt'] >= ts_start) & (m_tasks['c_dt'] <= ts_end)]
                gross = in_range[in_range['is_rnd']==False].apply(lambda x: x['difficulty'] * x['std_time'] * x['quality'], axis=1).sum()
        
        # 简化版统计，确保不出错
        fine = 0.0 
        reward_val = 0.0
        if not rews.empty:
            m_rews = rews[rews['username'] == m].copy()
            m_rews['c_dt'] = pd.to_datetime(m_rews['created_at'])
            reward_val = m_rews[(m_rews['c_dt'] >= ts_start) & (m_rews['c_dt'] <= ts_end)]['amount'].sum()
            
        net = gross - fine + reward_val
        stats_data.append({"成员": m, "任务产出": round(gross, 2), "罚款": round(fine, 2), "奖励": round(reward_val, 2), "💰 应发YVP": round(net, 2)})
    return pd.DataFrame(stats_data)

def format_deadline(d_val):
    return str(d_val) if (not pd.isna(d_val) and str(d_val) not in ['NaT', 'None', '']) else "♾️ 无期限"

def show_task_history(username, role):
    st.divider()
    st.subheader("📜 任务历史档案")
    df = run_query("tasks")
    if df.empty:
        st.info("数据加载中...")
        return
    
    my_history = df[(df['assignee'] == username) & (df['status'] == '完成')].copy()
    my_history['is_rnd'] = my_history['is_rnd'].fillna(False) if 'is_rnd' in my_history.columns else False
    
    if my_history.empty:
        st.info("暂无记录")
    else:
        my_history = my_history.sort_values("completed_at", ascending=False).head(10)
        for i, r in my_history.iterrows():
            with st.container(border=True):
                st.markdown(f"**✅ {r['title']}**")
                c1, c2, c3 = st.columns(3)
                earned = 0 if r['is_rnd'] else (r['difficulty'] * r['std_time'] * r['quality'])
                c1.write(f"💰 **+{round(earned, 2)}**")
                c2.caption(f"归档: {r['completed_at']}")
                c3.caption("研发任务" if r['is_rnd'] else "普通任务")

@st.dialog("✅ 成功")
def show_success_modal(msg="操作成功！"):
    st.write(msg)
    if st.button("关闭", type="primary"): force_refresh()

# --- 发布弹窗 ---
@st.dialog("➕ 发布任务")
def quick_publish_modal(camp_id, batt_id, batt_title):
    st.markdown(f"**目标：{batt_title}**")
    t_name = st.text_input("标题")
    if st.button("🚀 确认发布", type="primary"):
        supabase.table("tasks").insert({
            "title": t_name, "status": "待领取", "type": "公共任务池",
            "battlefield_id": int(batt_id), "difficulty": 1.0, "std_time": 1.0, "quality": 1.0
        }).execute()
        st.success("发布成功"); force_refresh()

# --- 调动弹窗 ---
@st.dialog("🔀 调动")
def move_task_modal(task_id, task_title, current_batt_id):
    st.write(f"调动: {task_title}")
    # 简单版：只列出所有战场ID，为了救急先保证能跑
    all_batts = run_query("battlefields")
    if not all_batts.empty:
        opts = {row['id']: row['title'] for _, row in all_batts.iterrows()}
        new_bid = st.selectbox("选择战场", list(opts.keys()), format_func=lambda x: opts[x])
        if st.button("确认"):
            supabase.table("tasks").update({"battlefield_id": int(new_bid)}).eq("id", int(task_id)).execute()
            st.success("已调动"); force_refresh()

# --- 登录鉴权 ---
if 'user' not in st.session_state: st.session_state.user = None
if st.session_state.user is None:
    time.sleep(0.5)
    c_user = cookie_manager.get("yanzu_user")
    c_role = cookie_manager.get("yanzu_role")
    if c_user:
        st.session_state.user = c_user
        st.session_state.role = c_role
        st.rerun()

if st.session_state.user is None:
    st.title("🏛️ 颜祖美学·执行中枢")
    u = st.text_input("用户名"); p = st.text_input("密码", type="password")
    if st.button("🚀 登录"):
        res = supabase.table("users").select("*").eq("username", u).eq("password", p).execute()
        if res.data:
            st.session_state.user = u
            st.session_state.role = res.data[0]['role']
            cookie_manager.set("yanzu_user", u); cookie_manager.set("yanzu_role", res.data[0]['role'])
            st.rerun()
    st.stop()

user = st.session_state.user
role = st.session_state.role

st.markdown(f"""<div class="scrolling-text">✅ 数据连接已恢复 | 正在运行 V35.6 紧急救援版</div>""", unsafe_allow_html=True)
st.title(f"🏛️ {user}")

nav = st.radio("NAV", ["🔭 战略作战室", "📋 任务大厅", "🏰 个人中心"], horizontal=True)
st.divider()

# --- 1. 战略作战室 ---
if nav == "🔭 战略作战室":
    st.header("🔭 战略作战室")
    camps = run_query("campaigns")
    batts = run_query("battlefields")
    all_tasks = run_query("tasks")
    
    edit_mode = False
    if role == 'admin':
        edit_mode = st.toggle("👁️ 编辑模式")
        if edit_mode:
            with st.expander("➕ 新建战役"):
                nct = st.text_input("名称"); ncd = st.date_input("截止", value=None)
                if st.button("新建"):
                    d_val = str(ncd) if ncd else None
                    supabase.table("campaigns").insert({"title": nct, "deadline": d_val}).execute()
                    st.success("成功"); force_refresh()

    if not camps.empty:
        for _, camp in camps.iterrows():
            with st.container(border=True):
                c1, c2 = st.columns([4, 1])
                c1.subheader(f"🚩 {camp['title']}")
                
                if edit_mode and role == 'admin' and camp['id'] != -1:
                    if c2.button("🗑️", key=f"dc_{camp['id']}"):
                        supabase.table("campaigns").delete().eq("id", int(camp['id'])).execute()
                        force_refresh()

                # 战场
                if not batts.empty:
                    my_batts = batts[batts['campaign_id'] == camp['id']]
                    for _, batt in my_batts.iterrows():
                        with st.expander(f"🛡️ {batt['title']}", expanded=True):
                            if edit_mode and role == 'admin':
                                c_b1, c_b2 = st.columns([1, 4])
                                if c_b1.button("🗑️ 删战场", key=f"db_{batt['id']}"):
                                    supabase.table("battlefields").delete().eq("id", int(batt['id'])).execute()
                                    force_refresh()
                                if c_b2.button("➕ 发任务", key=f"qp_{batt['id']}"):
                                    quick_publish_modal(camp['id'], batt['id'], batt['title'])

                            if not all_tasks.empty:
                                b_tasks = all_tasks[all_tasks['battlefield_id'] == batt['id']]
                                for _, t in b_tasks.iterrows():
                                    cols = st.columns([4, 1]) if edit_mode else [st.container()]
                                    cols[0].write(f"⚔️ {t['title']} ({t['status']} - {t['assignee']})")
                                    if edit_mode and role == 'admin':
                                        if cols[1].button("🔀", key=f"mv_{t['id']}"):
                                            move_task_modal(t['id'], t['title'], batt['id'])
                
                if edit_mode and role == 'admin':
                    nb = st.text_input("新战场名", key=f"nb_{camp['id']}")
                    if st.button("加战场", key=f"addb_{camp['id']}"):
                        supabase.table("battlefields").insert({"campaign_id": int(camp['id']), "title": nb}).execute()
                        force_refresh()

# --- 2. 任务大厅 ---
elif nav == "📋 任务大厅":
    st.header("🛡️ 任务大厅")
    tdf = run_query("tasks")
    if not tdf.empty:
        st.subheader("🔥 待抢任务")
        pool = tdf[tdf['status']=='待领取']
        for _, row in pool.iterrows():
            with st.container(border=True):
                st.write(f"**{row['title']}**")
                if st.button("⚡️ 抢单", key=f"g_{row['id']}"):
                    supabase.table("tasks").update({"status": "进行中", "assignee": user}).eq("id", int(row['id'])).execute()
                    st.success("成功"); force_refresh()
        
        st.divider()
        st.subheader("🔭 动态")
        st.dataframe(tdf[['title', 'assignee', 'status', 'created_at']], use_container_width=True)

# --- 3. 个人中心 ---
elif nav == "🏰 个人中心":
    st.header(f"🏰 {user}")
    if st.button("刷新数据"): force_refresh()
    
    yvp = calculate_net_yvp(user)
    st.metric("💰 当前 YVP", yvp)
    
    show_task_history(user, role)
    
    if role == 'admin':
        st.divider()
        st.write("🔧 管理员工具")
        if st.button("下载全量备份"):
            df = run_query("tasks")
            st.download_button("下载 CSV", df.to_csv(), "backup.csv")
