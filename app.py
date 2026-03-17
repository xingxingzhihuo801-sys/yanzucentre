import streamlit as st
import pandas as pd
import datetime
import time
import io
import random
import extra_streamlit_components as stx
from supabase import create_client, Client

# --- 1. 系统配置 ---
st.set_page_config(
    page_title="颜祖美学·执行中枢 V42.11",
    page_icon="🏛️",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# --- 常量定义 ---
MATRIX_EXCLUDE_USERS = ['liujingting', 'jiangjing', 'admin']
MATRIX_START_DATE = datetime.date(2026, 2, 11)
MATRIX_HOLIDAY_START = datetime.date(2026, 2, 17)
MATRIX_HOLIDAY_END = datetime.date(2026, 2, 23)
CST_TZ = datetime.timezone(datetime.timedelta(hours=8)) # 北京时间

# --- 2. CSS 美化 ---
st.markdown("""
    <style>
        /* 全局字体与间距 */
        html, body, [class*="css"] {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Noto Sans SC", sans-serif;
        }
        .block-container {
            padding-top: 2rem;
            padding-bottom: 2rem;
        }
        
        #MainMenu {visibility: hidden;}
        header {visibility: hidden;}
        footer {visibility: hidden;}
        .stDeployButton {display:none;}
        div[data-testid="stToolbar"] {visibility: hidden;}
        
        section[data-testid="stSidebar"] {
            background: linear-gradient(180deg, #1a1a2e 0%, #16213e 100%);
            color: white;
        }
        section[data-testid="stSidebar"] .stMarkdown { color: #e0e0e0; }
        
        .scrolling-text {
            width: 100%;
            background: linear-gradient(90deg, #fff3cd, #ffeaa7);
            color: #856404;
            padding: 10px;
            text-align: center;
            font-weight: bold;
            border-bottom: 1px solid #ffeeba;
            margin-bottom: 15px;
            border-radius: 8px;
            box-shadow: 0 1px 4px rgba(0,0,0,0.06);
        }
        
        .highlight-data { font-weight: bold; color: #31333F; background-color: #e8f0fe; padding: 2px 8px; border-radius: 4px; border: 1px solid #d2e3fc; }
        .strat-tag { font-size: 0.8em; color: #fff; background-color: #6c757d; padding: 2px 6px; border-radius: 4px; margin-right: 5px; }
        .strat-tag-active { background-color: #0d6efd; }
        .rnd-tag { font-size: 0.8em; color: #fff; background-color: #6f42c1; padding: 2px 6px; border-radius: 4px; margin-right: 5px; font-weight: bold; }
        
        .todo-doing { border-left: 4px solid #ffc107; background-color: #fff9db; padding: 10px; margin-bottom: 8px; border-radius: 4px; color: #333; }
        .todo-done { border-left: 4px solid #28a745; background-color: #d4edda; color: #155724; padding: 10px; margin-bottom: 8px; border-radius: 4px; text-decoration: line-through; }
        
        .stButton button { width: 100%; }
        div[data-testid="stExpander"] { border: 1px solid #e0e0e0; border-radius: 8px; transition: box-shadow 0.2s ease; }
        div[data-testid="stExpander"]:hover { box-shadow: 0 2px 8px rgba(0,0,0,0.05); }
    </style>
""", unsafe_allow_html=True)

# --- 3. 数据库连接 ---
try:
    url = st.secrets["supabase"]["url"]
    key = st.secrets["supabase"]["key"]
    supabase: Client = create_client(url, key)
except Exception:
    st.error("🚨 数据库连接配置有误，请检查 Secrets。")
    st.stop()

# --- 4. Cookie 管理器 ---
cookie_manager = stx.CookieManager(key="yanzu_v42_11_tz_fix")

# --- 5. 核心工具函数定义 ---

@st.cache_data(ttl=2) 
def run_query(table_name):
    schemas = {
        'tasks': ['id', 'title', 'battlefield_id', 'status', 'deadline', 'is_rnd', 'assignee', 'difficulty', 'std_time', 'quality', 'created_at', 'completed_at', 'description', 'feedback', 'type'],
        'campaigns': ['id', 'title', 'deadline', 'order_index', 'status'],
        'battlefields': ['id', 'title', 'campaign_id', 'order_index'],
        'users': ['username', 'password', 'role'],
        'penalties': ['id', 'username', 'reason', 'occurred_at'],
        'rewards': ['id', 'username', 'amount', 'reason', 'created_at'],
        'messages': ['id', 'username', 'content', 'created_at'],
        'daily_todos': ['id', 'username', 'date', 'content', 'category', 'is_completed'],
        'leaves': ['id', 'username', 'leave_date', 'period', 'reason', 'is_emergency', 'status', 'admin_comment', 'created_at']
    }
    try:
        response = supabase.table(table_name).select("*").execute()
        df = pd.DataFrame(response.data)
        if df.empty: return pd.DataFrame(columns=schemas.get(table_name, []))
        for col in schemas.get(table_name, []):
            if col not in df.columns: df[col] = None 
        if 'order_index' in df.columns:
            df['order_index'] = pd.to_numeric(df['order_index'], errors='coerce').fillna(0)
            df = df.sort_values('order_index', ascending=True)
        elif 'id' in df.columns:
            df = df.sort_values('id', ascending=True)
        return df
    except: return pd.DataFrame(columns=schemas.get(table_name, []))

def force_refresh():
    st.cache_data.clear()
    st.rerun()

# V42.11 核心净化器：强行剥离一切时区
def parse_naive_datetime(series):
    dt_series = pd.to_datetime(series, errors='coerce')
    try:
        # 如果带有 tz (timezone)，强行 localize(None) 剥离掉
        if dt_series.dt.tz is not None:
            return dt_series.dt.tz_localize(None)
    except: pass
    return dt_series

def get_announcement():
    try:
        res = supabase.table("messages").select("content").eq("username", "__NOTICE__").order("created_at", desc=True).limit(1).execute()
        return res.data[0]['content'] if res.data else "欢迎来到颜祖美学执行中枢！"
    except: return "公告加载中..."

def update_announcement(text):
    supabase.table("messages").delete().eq("username", "__NOTICE__").execute()
    supabase.table("messages").insert({"username": "__NOTICE__", "content": text}).execute()

def format_deadline(d_val):
    if pd.isna(d_val) or str(d_val) in ['NaT', 'None', '']:
        return "♾️ 无期限"
    try: return str(pd.to_datetime(d_val).date())
    except: return str(d_val)

def get_task_label(bid, is_rnd=False):
    batts = run_query("battlefields")
    camps = run_query("campaigns")
    label_html = ""
    if is_rnd: label_html += "<span class='rnd-tag'>🟣 产品研发</span>"
    if pd.isna(bid): return label_html + "未归类"
    try:
        b_row = batts[batts['id'] == bid].iloc[0]
        c_row = camps[camps['id'] == b_row['campaign_id']].iloc[0]
        style_class = "strat-tag" if c_row['id'] == -1 else "strat-tag strat-tag-active"
        label_html += f"<span class='{style_class}'>{c_row['title']} / {b_row['title']}</span>"
        return label_html
    except: return label_html + "未知"

def render_task_card(task, batts_df, camps_df):
    color_map = {"进行中": "#3b82f6", "返工": "#ef4444", "待验收": "#f59e0b", "完成": "#10b981", "待领取": "#9ca3af"}
    border_color = color_map.get(task['status'], '#6b7280')
    label_html = ""
    if task.get('is_rnd'): label_html += "<span class='rnd-tag'>🟣 产品研发</span>"
    bid = task.get('battlefield_id')
    if not pd.isna(bid):
        try:
            b_row = batts_df[batts_df['id'] == bid]
            if not b_row.empty:
                b_row = b_row.iloc[0]
                c_row = camps_df[camps_df['id'] == b_row['campaign_id']]
                if not c_row.empty:
                    c_row = c_row.iloc[0]
                    style_class = "strat-tag" if c_row['id'] == -1 else "strat-tag strat-tag-active"
                    label_html += f"<span class='{style_class}'>{c_row['title']} / {b_row['title']}</span>"
        except: pass
    st.markdown(f"""
        <div style="border-left: 5px solid {border_color}; 
                    padding: 12px 15px; margin-bottom: 10px; 
                    border-radius: 4px; 
                    background: white; box-shadow: 0 1px 3px rgba(0,0,0,0.1);">
            <div style="margin-bottom:4px;">{label_html}</div>
            <div style="font-weight:600; font-size:1.1em; color:#1f2937;">{task['title']}</div>
            <div style="color:#6b7280; font-size:0.85em; margin-top:6px; display:flex; justify-content:space-between;">
                <span>📅 {format_deadline(task.get('deadline'))}</span>
                <span>⚙️ D{task['difficulty']} / T{task['std_time']}</span>
            </div>
        </div>
    """, unsafe_allow_html=True)

def safe_float(val):
    try:
        if val is None or str(val).strip() == "": return 0.0
        return float(val)
    except: return 0.0

def show_task_history(username, role):
    st.divider()
    st.subheader("📜 任务历史档案")
    df = run_query("tasks")
    if df.empty:
        st.info("暂无数据")
        return
    my_history = df[(df['assignee'] == username) & (df['status'] == '完成')].copy()
    if 'is_rnd' not in my_history.columns: my_history['is_rnd'] = False
    my_history['is_rnd'] = my_history['is_rnd'].fillna(False)
    if my_history.empty:
        st.info("暂无已完成的任务记录")
    else:
        if 'completed_at' in my_history.columns:
            my_history = my_history.sort_values("completed_at", ascending=False).head(15)
        for i, r in my_history.iterrows():
            with st.container(border=True):
                st.markdown(f"**✅ {r['title']}**")
                c1, c2, c3 = st.columns(3)
                earned = 0.0
                if not r['is_rnd']:
                    earned = safe_float(r.get('difficulty')) * safe_float(r.get('std_time')) * safe_float(r.get('quality'))
                c1.write(f"💰 **+{round(earned, 2)}**")
                c2.caption(f"归档: {r.get('completed_at', '-')}")
                c3.caption("研发任务" if r['is_rnd'] else "普通任务")

def calculate_net_yvp(username, tasks_df, pen_df, rew_df, days_lookback=None):
    try:
        gross = 0.0
        if not tasks_df.empty:
            df_t = tasks_df.copy()
            my_done = df_t[(df_t['assignee'] == username) & (df_t['status'] == '完成')].copy()
            if not my_done.empty:
                my_done['is_rnd'] = my_done['is_rnd'].fillna(False)
                my_done['val'] = my_done.apply(lambda x: 0.0 if x['is_rnd'] else (safe_float(x.get('difficulty')) * safe_float(x.get('std_time')) * safe_float(x.get('quality'))), axis=1)
                
                # 剥离时区
                my_done['c_dt'] = parse_naive_datetime(my_done['completed_at'])
                if days_lookback:
                    cutoff = pd.Timestamp.now() - pd.Timedelta(days=days_lookback)
                    my_done = my_done[my_done['c_dt'] >= cutoff]
                gross = my_done['val'].sum()

        total_fine = 0.0
        if not pen_df.empty:
            df_p = pen_df[pen_df['username'] == username].copy()
            if not df_p.empty:
                # 剥离时区
                df_p['o_dt'] = parse_naive_datetime(df_p['occurred_at'])
                if days_lookback:
                    cutoff = pd.Timestamp.now() - pd.Timedelta(days=days_lookback)
                    df_p = df_p[df_p['o_dt'] >= cutoff]
                
                if not df_p.empty and not tasks_df.empty:
                    df_t_base = tasks_df[(tasks_df['assignee'] == username) & (tasks_df['status'] == '完成')].copy()
                    if not df_t_base.empty:
                        df_t_base['c_dt'] = parse_naive_datetime(df_t_base['completed_at'])
                        df_t_base['is_rnd'] = df_t_base['is_rnd'].fillna(False)
                        df_t_base['val'] = df_t_base.apply(lambda x: 0.0 if x['is_rnd'] else (safe_float(x.get('difficulty')) * safe_float(x.get('std_time')) * safe_float(x.get('quality'))), axis=1)
                        
                        for _, pen in df_p.iterrows():
                            if pd.isna(pen['o_dt']): continue
                            w_start = pen['o_dt'] - pd.Timedelta(days=7)
                            w_tasks = df_t_base[(df_t_base['c_dt'] >= w_start) & (df_t_base['c_dt'] <= pen['o_dt'])]
                            total_fine += w_tasks['val'].sum() * 0.2
        
        total_reward = 0.0
        if not rew_df.empty:
            df_r = rew_df[rew_df['username'] == username].copy()
            if not df_r.empty:
                df_r['amount_val'] = df_r['amount'].apply(safe_float)
                # 剥离时区
                df_r['c_dt'] = parse_naive_datetime(df_r['created_at'])
                if days_lookback:
                    cutoff = pd.Timestamp.now() - pd.Timedelta(days=days_lookback)
                    df_r = df_r[df_r['c_dt'] >= cutoff]
                total_reward = df_r['amount_val'].sum()

        return round(gross - total_fine + total_reward, 2)
    except Exception as e:
        print(f"Error calculating YVP for {username}: {e}")
        return 0.0

def calculate_period_stats(start_date, end_date):
    try:
        users = run_query("users")
        if users.empty: return pd.DataFrame()
        members = users[users['role'] != 'admin']['username'].tolist()
        tasks = run_query("tasks"); pens = run_query("penalties"); rews = run_query("rewards")
        
        stats_data = []
        ts_start = pd.Timestamp(start_date)
        ts_end = pd.Timestamp(end_date) + pd.Timedelta(days=1)
        
        for m in members:
            gross = 0.0
            if not tasks.empty:
                df_t = tasks[(tasks['assignee'] == m) & (tasks['status'] == '完成')].copy()
                if not df_t.empty:
                    df_t['is_rnd'] = df_t['is_rnd'].fillna(False)
                    # 剥离时区
                    df_t['c_dt'] = parse_naive_datetime(df_t['completed_at'])
                    in_range = df_t[(df_t['c_dt'] >= ts_start) & (df_t['c_dt'] <= ts_end)]
                    gross = in_range[in_range['is_rnd']==False].apply(lambda x: safe_float(x.get('difficulty')) * safe_float(x.get('std_time')) * safe_float(x.get('quality')), axis=1).sum()
            
            fine = 0.0
            
            reward_val = 0.0
            if not rews.empty:
                df_r = rews[rews['username'] == m].copy()
                # 剥离时区
                df_r['c_dt'] = parse_naive_datetime(df_r['created_at'])
                in_range_r = df_r[(df_r['c_dt'] >= ts_start) & (df_r['c_dt'] <= ts_end)]
                reward_val = in_range_r['amount'].apply(safe_float).sum()
                
            net = gross - fine + reward_val
            stats_data.append({"成员": m, "任务产出": round(gross, 2), "罚款": round(fine, 2), "奖励": round(reward_val, 2), "💰 应发YVP": round(net, 2)})
        
        return pd.DataFrame(stats_data).sort_values("💰 应发YVP", ascending=False) if stats_data else pd.DataFrame()
    except Exception as e: 
        st.error(f"分润统计出现异常: {e}")
        return pd.DataFrame()

@st.dialog("🎉 恭喜")
def show_success_modal(msg="操作成功！"):
    st.markdown(f"### {msg}")
    st.balloons()
    if st.button("关闭并刷新", type="primary"): force_refresh()

def get_or_create_matrix_battlefield():
    camps = supabase.table("campaigns").select("*").eq("title", "矩阵战役").execute()
    if not camps.data:
        res_c = supabase.table("campaigns").insert({"title": "矩阵战役", "order_index": 99}).execute()
        camp_id = res_c.data[0]['id']
    else: camp_id = camps.data[0]['id']
    batts = supabase.table("battlefields").select("*").eq("title", "黑丸视频投放").eq("campaign_id", camp_id).execute()
    if not batts.data:
        res_b = supabase.table("battlefields").insert({"title": "黑丸视频投放", "campaign_id": camp_id, "order_index": 1}).execute()
        batt_id = res_b.data[0]['id']
    else: batt_id = batts.data[0]['id']
    return int(batt_id)

def global_matrix_task_dispatch():
    today = datetime.datetime.now(CST_TZ).date()
    is_holiday = MATRIX_HOLIDAY_START <= today <= MATRIX_HOLIDAY_END
    if today >= MATRIX_START_DATE and today.weekday() <= 4 and not is_holiday:
        today_str = str(today)
        users_df = run_query("users")
        if users_df.empty: return
        target_users = users_df[~users_df['username'].isin(MATRIX_EXCLUDE_USERS)]['username'].tolist()
        all_tasks = run_query("tasks")
        target_bid = get_or_create_matrix_battlefield()
        matrix_desc = """【必做任务】\n1. 在自己的矩阵号上发布至少3条黑丸本土化视频。\n2. 奖励机制：\n   - 单篇点赞>1000：+1点\n   - 单篇点赞>5000：+2点\n   - 单篇点赞>1w：+5点\n   - 单篇点赞>10w：+30点\n   - 单篇点赞>100w：+150点\n3. ⚠️ 惩罚：未完成将直接按【缺勤】处理。"""
        new_tasks = []
        for u in target_users:
            task_title = f"{u} {today.month}.{today.day} 矩阵任务"
            is_exist = False
            if not all_tasks.empty:
                check = all_tasks[(all_tasks['assignee'] == u) & (all_tasks['title'] == task_title)]
                if not check.empty: is_exist = True
            if not is_exist:
                new_tasks.append({
                    "title": task_title, "description": matrix_desc, "difficulty": 1.0, "std_time": 2.0,
                    "status": "进行中", "assignee": u, "type": "matrix_daily", "deadline": today_str,
                    "battlefield_id": target_bid, "is_rnd": False
                })
        if new_tasks:
            supabase.table("tasks").insert(new_tasks).execute()

def check_and_create_matrix_tasks(username):
    today = datetime.datetime.now(CST_TZ).date()
    is_holiday = MATRIX_HOLIDAY_START <= today <= MATRIX_HOLIDAY_END
    if today >= MATRIX_START_DATE and today.weekday() <= 4 and not is_holiday:
        today_str = str(today)
        tasks = run_query("tasks")
        task_title = f"{username} {today.month}.{today.day} 矩阵任务"
        has_task = False
        if not tasks.empty:
            exists = tasks[(tasks['assignee'] == username) & (tasks['title'] == task_title)]
            if not exists.empty: has_task = True
        if not has_task:
            target_bid = get_or_create_matrix_battlefield()
            matrix_desc = """【必做任务】\n1. 在自己的矩阵号上发布至少3条黑丸本土化视频。\n2. 奖励机制：\n   - 单篇点赞>1000：+1点\n   - 单篇点赞>5000：+2点\n   - 单篇点赞>1w：+5点\n   - 单篇点赞>10w：+30点\n   - 单篇点赞>100w：+150点\n3. ⚠️ 惩罚：未完成将直接按【缺勤】处理。"""
            supabase.table("tasks").insert({
                "title": task_title, "description": matrix_desc, "difficulty": 1.0, "std_time": 2.0,
                "status": "进行中", "assignee": username, "type": "matrix_daily", "deadline": today_str,
                "battlefield_id": target_bid, "is_rnd": False
            }).execute()
            st.toast(f"📅 已生成：{task_title}")

# --- 6. 鉴权与自动登录 ---
if 'user' not in st.session_state:
    st.session_state.user = None
    st.session_state.role = None

if st.session_state.user is None:
    time.sleep(0.1)
    c_user = cookie_manager.get("yanzu_user")
    if c_user:
        try:
            res = supabase.table("users").select("role").eq("username", c_user).execute()
            if res.data:
                st.session_state.user = c_user
                st.session_state.role = res.data[0]['role']
                if res.data[0]['role'] != 'admin': check_and_create_matrix_tasks(c_user)
                else: global_matrix_task_dispatch()
            else: cookie_manager.delete("yanzu_user")
        except:
            st.session_state.user = c_user
            st.session_state.role = cookie_manager.get("yanzu_role") or 'member'
        st.rerun()

if st.session_state.user is None:
    st.markdown("""
        <div style="text-align:center; padding: 40px 0 20px 0;">
            <h1 style="font-size:3em;">🏛️ 颜祖美学·执行中枢</h1>
            <p style="color:#666; font-size:1.2em;">团队协作 · 任务驱动 · 数据透明</p>
        </div>
    """, unsafe_allow_html=True)
    _, center, _ = st.columns([1, 2, 1])
    with center:
        with st.form("login"):
            st.markdown("### 🔑 成员登录")
            u = st.text_input("用户名")
            p = st.text_input("密码", type="password")
            if st.form_submit_button("🚀 登录", type="primary"):
                try:
                    res = supabase.table("users").select("*").eq("username", u).eq("password", p).execute()
                    if res.data:
                        st.session_state.user = u
                        st.session_state.role = res.data[0]['role']
                        cookie_manager.set("yanzu_user", u, expires_at=datetime.datetime.now() + datetime.timedelta(days=30))
                        cookie_manager.set("yanzu_role", res.data[0]['role'], expires_at=datetime.datetime.now() + datetime.timedelta(days=30))
                        if res.data[0]['role'] != 'admin': check_and_create_matrix_tasks(u)
                        else: global_matrix_task_dispatch()
                        st.rerun()
                    else: st.error("账号或密码错误")
                except: st.error("连接超时，请重试")
    st.stop()

user = st.session_state.user
role = st.session_state.role

# 侧边栏
with st.sidebar:
    st.header(f"👤 {user}")
    st.caption(f"身份: {'👑 统帅' if role=='admin' else '⚔️ 成员'}")
    if role == 'admin': st.success("统帅万岁！请及时备份数据。")
    else:
        tasks_all = run_query("tasks")
        pens_all = run_query("penalties")
        rews_all = run_query("rewards")
        yvp_7 = calculate_net_yvp(user, tasks_all, pens_all, rews_all, 7)
        yvp_all = calculate_net_yvp(user, tasks_all, pens_all, rews_all)
        st.metric("7天净收益", yvp_7)
        st.metric("总净资产", yvp_all)
    st.divider()
    if st.button("注销退出"):
        cookie_manager.delete("yanzu_user")
        cookie_manager.delete("yanzu_role")
        st.session_state.user = None
        st.session_state.role = None
        st.rerun()

ann_text = get_announcement()
st.markdown(f"""<div class="scrolling-text"><marquee scrollamount="6">🔔 公告：{ann_text}</marquee></div>""", unsafe_allow_html=True)
st.title(f"🏛️ 帝国中枢 · {user}")

nav = st.radio("NAV", ["☀️ 今日清单", "📅 请假中心", "🔭 战略作战室", "📋 任务大厅", "🗣️ 颜祖广场", "🏆 风云榜", "🏰 个人中心"], horizontal=True, label_visibility="collapsed")
st.divider()

# ================= 业务路由 =================

# --- 0. ☀️ 今日清单 ---
if nav == "☀️ 今日清单":
    st.header("☀️ 今日清单 (Daily Plan)")
    st.info("📅 制定今日计划，保持大脑清晰。")
    now = datetime.datetime.now(CST_TZ)
    if now.hour < 3: business_date = now.date() - datetime.timedelta(days=1)
    else: business_date = now.date()
    today_str = str(business_date)
    
    with st.form("add_todo_form", clear_on_submit=True):
        col_in1, col_in2, col_in3 = st.columns([3, 1, 1])
        new_todo = col_in1.text_input("💡 添加事项", placeholder="例如：交付799报告...", label_visibility="collapsed")
        new_cat = col_in2.selectbox("类型", ["核心必办", "余力选办"], label_visibility="collapsed")
        submitted = col_in3.form_submit_button("➕ 添加", type="primary", use_container_width=True)
        if submitted and new_todo:
            supabase.table("daily_todos").insert({
                "username": user, "content": new_todo, "category": new_cat, "date": today_str
            }).execute()
            st.rerun()

    todos = run_query("daily_todos")
    st.subheader(f"📝 我的清单 ({today_str})")
    if not todos.empty:
        my_todos = todos[(todos['username'] == user) & (todos['date'].astype(str) == today_str)].sort_values('id')
        if not my_todos.empty:
            for _, t in my_todos.iterrows():
                if t['is_completed']:
                    container_style = st.container(border=True)
                    container_style.markdown(f"✅ ~~{t['content']}~~ <span style='color:grey;font-size:0.8em'>({t['category']})</span>", unsafe_allow_html=True)
                    c_act1, c_act2 = container_style.columns([1, 6])
                    if c_act1.button("↩️ 撤销", key=f"undo_{t['id']}"):
                        supabase.table("daily_todos").update({"is_completed": False}).eq("id", int(t['id'])).execute()
                        st.rerun()
                else:
                    with st.container(border=True):
                        c_t1, c_t2, c_t3, c_t4, c_t5 = st.columns([4, 1, 1, 0.5, 0.5])
                        c_t1.markdown(f"**{t['content']}**")
                        color = "red" if t['category'] == '核心必办' else "blue"
                        c_t2.markdown(f"<span style='color:{color};font-weight:bold'>{t['category']}</span>", unsafe_allow_html=True)
                        if c_t3.button("✅ 完成", key=f"done_{t['id']}", type="primary"):
                            supabase.table("daily_todos").update({"is_completed": True}).eq("id", int(t['id'])).execute()
                            show_success_modal(f"太棒了！已完成：{t['content']}")
                        with c_t4.popover("✏️"):
                            edit_txt = st.text_input("修改", t['content'], key=f"etxt_{t['id']}")
                            edit_cat = st.selectbox("类型", ["核心必办", "余力选办"], index=0 if t['category']=="核心必办" else 1, key=f"ecat_{t['id']}")
                            if st.button("保存", key=f"esave_{t['id']}"):
                                supabase.table("daily_todos").update({"content": edit_txt, "category": edit_cat}).eq("id", int(t['id'])).execute()
                                st.rerun()
                        if c_t5.button("🗑️", key=f"del_td_{t['id']}"):
                            supabase.table("daily_todos").delete().eq("id", int(t['id'])).execute()
                            st.rerun()
        else:
            st.markdown("""<div style="text-align:center; padding:30px; color:#aaa;"><div style="font-size:3em;">📋</div><p>今天还没有计划，添加一条开始吧！</p></div>""", unsafe_allow_html=True)
    else: st.info("数据加载中...")

    st.divider()
    st.subheader("👀 团队今日动态")
    with st.expander("展开查看全员进度", expanded=True):
        if not todos.empty:
            team_todos = todos[todos['date'].astype(str) == today_str]
            if not team_todos.empty:
                users_active = team_todos['username'].unique()
                cols = st.columns(len(users_active) if len(users_active) < 3 else 3)
                for i, u_name in enumerate(users_active):
                    with cols[i % 3]:
                        with st.container(border=True):
                            st.markdown(f"#### 👤 {u_name}")
                            u_tasks = team_todos[team_todos['username'] == u_name]
                            c_ing, c_fin = st.columns(2)
                            with c_ing:
                                st.caption("🔴 进行中")
                                doing = u_tasks[u_tasks['is_completed'] == False]
                                if not doing.empty:
                                    for _, t in doing.iterrows():
                                        cat_icon = "🔥" if t['category'] == '核心必办' else "☕"
                                        st.markdown(f"<div class='todo-doing'><b>[{cat_icon}]</b> {t['content']}</div>", unsafe_allow_html=True)
                                else: st.caption("-")
                            with c_fin:
                                st.caption("🟢 已完成")
                                done = u_tasks[u_tasks['is_completed'] == True]
                                if not done.empty:
                                    for _, t in done.iterrows():
                                        cat_icon = "🔥" if t['category'] == '核心必办' else "☕"
                                        st.markdown(f"<div class='todo-done'><b>[{cat_icon}]</b> {t['content']}</div>", unsafe_allow_html=True)
                                else: st.caption("-")
            else: st.info("今日团队暂无动态")
            
    st.divider()
    with st.expander("📜 团队清单历史 (近10日)", expanded=False):
        if not todos.empty:
            ten_days_ago = datetime.date.today() - datetime.timedelta(days=10)
            hist_todos = todos[pd.to_datetime(todos['date']).dt.date >= ten_days_ago].copy()
            if not hist_todos.empty:
                hist_todos['Status'] = hist_todos['is_completed'].apply(lambda x: '✅ 完成' if x else '🔴 未完')
                hist_todos = hist_todos[['date', 'username', 'category', 'content', 'Status']].sort_values(['date', 'username'], ascending=False)
                st.dataframe(hist_todos, use_container_width=True, hide_index=True)
            else: st.info("暂无历史数据")

# --- 📅 请假中心 ---
elif nav == "📅 请假中心":
    st.header("📅 请假中心 (Leave Center)")
    st.info("""
    📢 **请假管理办法**
    1. **常规请假**：必需在 **前一日 22:00 前** 提交申请。
    2. **补假/突发**：如选择 **过去日期** 或 **晚于22:00**，必须勾选“🔴 突发/补假”。
    3. **时段说明**：上午(10:00-12:00)，下午(14:00-17:00)。
    """)
    
    with st.container(border=True):
        st.subheader("📝 提交请假申请")
        with st.form("leave_form", clear_on_submit=True):
            c1, c2 = st.columns(2)
            l_date = c1.date_input("请假日期") 
            l_period = c2.selectbox("时段", ["全天", "上午 (10:00-12:00)", "下午 (14:00-17:00)"])
            l_type = st.radio("类型", ["❌ 不参与 (缺勤)", "⚠️ 晚到"], horizontal=True)
            l_reason = st.text_area("请假理由 (必填)")
            l_emergency = st.checkbox("🔴 突发/补假 (超时或补填请勾选)")
            
            if st.form_submit_button("🚀 提交申请", type="primary"):
                is_valid = True
                today_d = datetime.date.today()
                
                if l_date < today_d and not l_emergency:
                    st.error("❌ 补填过去日期的请假，请务必勾选“🔴 突发/补假”。")
                    is_valid = False
                
                deadline = datetime.datetime.combine(l_date - datetime.timedelta(days=1), datetime.time(22, 0))
                if datetime.datetime.now() > deadline and not l_emergency:
                    st.error(f"❌ 常规请假需在前一日 22:00 前提交。如为突发，请勾选“🔴 突发/补假”。")
                    is_valid = False
                
                if is_valid:
                    if not l_reason:
                        st.error("请填写请假理由！")
                    else:
                        full_reason = f"【{l_type.split(' ')[1]}】{l_reason}"
                        supabase.table("leaves").insert({
                            "username": user,
                            "leave_date": str(l_date),
                            "period": l_period,
                            "reason": full_reason,
                            "is_emergency": l_emergency,
                            "status": "待审批"
                        }).execute()
                        st.success("✅ 申请已提交，等待管理员审批。")
                        time.sleep(1); force_refresh()

    st.divider()
    st.subheader("🗓️ 团队请假公示 (近30日)")
    leaves = run_query("leaves")
    if not leaves.empty:
        d_30 = datetime.date.today() - datetime.timedelta(days=30)
        view_leaves = leaves[pd.to_datetime(leaves['leave_date']).dt.date >= d_30].copy()
        if not view_leaves.empty:
            view_leaves = view_leaves.sort_values(['leave_date', 'created_at'], ascending=False)
            st.dataframe(
                view_leaves[['username', 'leave_date', 'period', 'is_emergency', 'reason', 'status', 'admin_comment']],
                use_container_width=True, hide_index=True,
                column_config={"is_emergency": st.column_config.CheckboxColumn("突发?", disabled=True)}
            )
        else: st.info("近30天无请假记录")
    else: st.info("暂无数据")

    if role == 'admin':
        st.divider()
        st.header("⚖️ 管理员审批台")
        pending = leaves[leaves['status'] == '待审批'] if not leaves.empty else pd.DataFrame()
        if not pending.empty:
            st.warning(f"🔔 有 {len(pending)} 条申请待处理")
            for _, p in pending.iterrows():
                with st.container(border=True):
                    c1, c2, c3 = st.columns([3, 1, 1])
                    tag = "🔴 [突发]" if p['is_emergency'] else "🔵 [常规]"
                    c1.markdown(f"**{p['username']}** | {p['leave_date']} {p['period']} | {tag}")
                    c1.caption(f"理由: {p['reason']}")
                    if c2.button("✅ 批准", key=f"ok_{p['id']}"):
                        supabase.table("leaves").update({"status": "已批准"}).eq("id", int(p['id'])).execute()
                        st.rerun()
                    if c3.button("🚫 驳回", key=f"no_{p['id']}"):
                        supabase.table("leaves").update({"status": "驳回"}).eq("id", int(p['id'])).execute()
                        st.rerun()
        else: st.success("🎉 所有申请已处理完毕")

        with st.expander("➕ 补录历史记录 (管理员通道)", expanded=False):
            udf = run_query("users")
            all_mems = udf['username'].tolist() if not udf.empty else []
            with st.form("admin_add_leave"):
                ac1, ac2 = st.columns(2)
                a_user = ac1.selectbox("选择成员", all_mems)
                a_date = ac2.date_input("日期")
                ac3, ac4 = st.columns(2)
                a_period = ac3.selectbox("时段", ["全天", "上午 (10:00-12:00)", "下午 (14:00-17:00)"], key="adm_per")
                a_type = ac4.radio("类型", ["❌ 不参与", "⚠️ 晚到"], horizontal=True, key="adm_type")
                a_reason = st.text_input("备注/理由")
                if st.form_submit_button("🚀 确认添加"):
                    full_rsn = f"【{a_type.split(' ')[1]}】(管理员补录) {a_reason}"
                    supabase.table("leaves").insert({
                        "username": a_user,
                        "leave_date": str(a_date),
                        "period": a_period,
                        "reason": full_rsn,
                        "is_emergency": False,
                        "status": "已批准",
                        "admin_comment": "系统补录"
                    }).execute()
                    st.success(f"已为 {a_user} 添加记录"); time.sleep(1); force_refresh()

        with st.expander("🛠️ 修改现有记录 (上帝模式)"):
            if not leaves.empty:
                lid = st.selectbox("选择记录", leaves['id'], format_func=lambda x: f"{leaves[leaves['id']==x]['username'].values[0]} - {leaves[leaves['id']==x]['leave_date'].values[0]}")
                target = leaves[leaves['id']==lid].iloc[0]
                ce1, ce2 = st.columns(2)
                n_date = ce1.date_input("改日期", value=pd.to_datetime(target['leave_date']).date())
                n_period = ce2.selectbox("改时段", ["全天", "上午 (10:00-12:00)", "下午 (14:00-17:00)"], index=0)
                n_status = st.selectbox("改状态", ["待审批", "已批准", "驳回"], index=["待审批", "已批准", "驳回"].index(target['status']))
                n_comm = st.text_input("管理员批注", value=target['admin_comment'] or "")
                if st.button("💾 保存修改", type="primary"):
                    supabase.table("leaves").update({"leave_date": str(n_date), "period": n_period, "status": n_status, "admin_comment": n_comm}).eq("id", int(lid)).execute()
                    st.success("记录已修正"); force_refresh()

# --- 1. 战略作战室 ---
if nav == "🔭 战略作战室":
    st.header("🔭 战略作战室 (Strategy War Room)")
    camps = run_query("campaigns")
    batts = run_query("battlefields")
    all_tasks = run_query("tasks")
    
    col_mode, col_create = st.columns([2, 3])
    edit_mode = False
    if role == 'admin':
        with col_mode:
            edit_mode = st.toggle("👁️ 开启上帝视角 (编辑/调动模式)", value=False)
            if edit_mode: st.info("🔥 指挥模式已激活")
        with col_create:
            if edit_mode:
                with st.expander("🚩 新建战役", expanded=False):
                    new_camp_t = st.text_input("战役名称")
                    new_camp_d = st.date_input("战役截止", value=None)
                    new_camp_idx = st.number_input("排序权重", value=0, step=1)
                    if st.button("确立战役"):
                         d_val = str(new_camp_d) if new_camp_d else None
                         supabase.table("campaigns").insert({"title": new_camp_t, "deadline": d_val, "order_index": new_camp_idx}).execute()
                         st.success("✅ 建立成功！"); force_refresh()
    st.divider()
    
    if not camps.empty:
        for _, camp in camps.iterrows():
            with st.container(border=True):
                c1, c2, c3 = st.columns([3, 1.5, 0.5])
                status_icon = "👑" if camp['id'] == -1 else "🚩"
                c1.subheader(f"{status_icon} {camp['title']}")
                if camp['deadline']: c2.caption(f"🏁 截止: {camp['deadline']}")
                
                if edit_mode and role == 'admin' and camp['id'] != -1:
                    with c3.popover("⚙️"):
                        ec_t = st.text_input("名称", value=camp['title'], key=f"ec_{camp['id']}")
                        ec_d = st.date_input("截止", value=camp['deadline'], key=f"ecd_{camp['id']}")
                        ec_idx = st.number_input("排序", value=int(camp.get('order_index', 0)), step=1, key=f"ecidx_{camp['id']}")
                        if st.button("保存", key=f"sv_c_{camp['id']}"):
                            supabase.table("campaigns").update({"title": ec_t, "deadline": str(ec_d) if ec_d else None, "order_index": ec_idx}).eq("id", int(camp['id'])).execute()
                            st.success("✅ 保存成功"); force_refresh()
                        st.divider()
                        if st.button("🗑️ 删除", key=f"del_c_{camp['id']}", type="primary"):
                            has_batt = not batts.empty and not batts[batts['campaign_id'] == camp['id']].empty
                            if has_batt: st.error("请先清空战场！")
                            else: 
                                supabase.table("campaigns").delete().eq("id", int(camp['id'])).execute()
                                st.success("✅ 删除成功"); force_refresh()

                camp_batts = pd.DataFrame()
                if not batts.empty:
                    camp_batts = batts[batts['campaign_id'] == camp['id']]
                    if 'order_index' in camp_batts.columns: camp_batts = camp_batts.sort_values('order_index')
                
                camp_tasks = pd.DataFrame()
                if not all_tasks.empty and not camp_batts.empty:
                    camp_batt_ids = camp_batts['id'].tolist()
                    if 'battlefield_id' in all_tasks.columns:
                        camp_tasks = all_tasks[all_tasks['battlefield_id'].isin(camp_batt_ids)]
                
                if not camp_tasks.empty:
                    done_count = len(camp_tasks[camp_tasks['status'] == '完成'])
                    prog = done_count / len(camp_tasks)
                    st.progress(prog, text=f"战役总进度: {int(prog*100)}%")
                else: st.progress(0, text="整备中...")

                if not camp_batts.empty:
                    for _, batt in camp_batts.iterrows():
                        with st.expander(f"🛡️ {batt['title']}", expanded=True):
                            if edit_mode and role == 'admin' and batt['id'] != -1:
                                with st.container(border=True):
                                    st.caption("⚙️ 战场管理")
                                    c_edit_1, c_edit_2, c_edit_3 = st.columns([2, 1, 1])
                                    eb_t = c_edit_1.text_input("名称", value=batt['title'], key=f"ebt_{int(batt['id'])}")
                                    eb_idx = c_edit_2.number_input("排序", value=int(batt.get('order_index', 0)), step=1, key=f"ebidx_{int(batt['id'])}")
                                    if c_edit_3.button("💾 保存", key=f"bsv_{int(batt['id'])}"):
                                        supabase.table("battlefields").update({"title": eb_t, "order_index": eb_idx}).eq("id", int(batt['id'])).execute()
                                        st.success("✅ 已更新"); force_refresh()
                                    if c_edit_3.button("🗑️ 删除", key=f"bdel_{int(batt['id'])}", type="primary"):
                                        has_task = False
                                        if not all_tasks.empty and 'battlefield_id' in all_tasks.columns:
                                             if not all_tasks[all_tasks['battlefield_id'] == batt['id']].empty: has_task = True
                                        if has_task: st.error("请先清空任务")
                                        else:
                                            supabase.table("battlefields").delete().eq("id", int(batt['id'])).execute()
                                            st.success("✅ 已删除"); force_refresh()

                            if edit_mode and role == 'admin':
                                if st.button("➕ 在此发布任务", key=f"qp_btn_{batt['id']}"):
                                    quick_publish_modal(camp['id'], batt['id'], batt['title'])
                            
                            b_tasks = pd.DataFrame()
                            if not all_tasks.empty and 'battlefield_id' in all_tasks.columns:
                                b_tasks = all_tasks[all_tasks['battlefield_id'] == batt['id']]
                            if not b_tasks.empty:
                                b_done = len(b_tasks[b_tasks['status'] == '完成'])
                                st.progress(b_done/len(b_tasks), text="战场进度")
                                active_bt = b_tasks[b_tasks['status'].isin(['待领取', '进行中', '返工', '待验收'])]
                                if not active_bt.empty:
                                    for idx, task in active_bt.iterrows():
                                        cols_task = st.columns([0.85, 0.15]) if edit_mode else [st.container()]
                                        with cols_task[0]:
                                            render_task_card(task, batts, camps)
                                        if edit_mode and role == 'admin':
                                            with cols_task[1]:
                                                if st.button("🔀", key=f"mv_{task['id']}", help="全域调动"):
                                                    move_task_modal(task['id'], task['title'], batt['id'])
                                else: st.caption("暂无活跃任务")
                            else: st.caption("战场整备中")

                if edit_mode and role == 'admin':
                    cid_safe = int(camp['id'])
                    with st.expander("➕ 开辟新战场", expanded=False):
                        nb_t = st.text_input("新战场名称", key=f"nbt_{cid_safe}")
                        nb_idx = st.number_input("排序权重", value=0, step=1, key=f"nbidx_{cid_safe}")
                        if st.button("确认开辟", key=f"nb_btn_{cid_safe}"):
                            supabase.table("battlefields").insert({"campaign_id": cid_safe, "title": nb_t, "order_index": nb_idx}).execute()
                            st.success("✅ 开辟成功！"); force_refresh()

# --- 2. 任务大厅 ---
elif nav == "📋 任务大厅":
    st.header("🛡️ 任务大厅")
    tdf = run_query("tasks")
    batts = run_query("battlefields")
    camps = run_query("campaigns")
    
    st.subheader("🔥 待抢任务池")
    if not tdf.empty and 'status' in tdf.columns:
        pool = tdf[(tdf['status']=='待领取') & (tdf['type']=='公共任务池')]
        if not pool.empty:
            cols = st.columns(3)
            for i, (idx, row) in enumerate(pool.iterrows()):
                with cols[i % 3]:
                    render_task_card(row, batts, camps)
                    with st.expander("👁️ 查看详情"):
                        st.write(row.get('description', '无详情'))
                    if st.button("⚡️ 抢单", key=f"g_{row['id']}", type="primary"):
                        can_grab = True
                        if role != 'admin':
                            my_ongoing = tdf[(tdf['assignee'] == user) & (tdf['status'].isin(['进行中', '返工'])) & (tdf['type'] == '公共任务池')]
                            if len(my_ongoing) >= 2: can_grab = False
                        if can_grab:
                            supabase.table("tasks").update({"status": "进行中", "assignee": user}).eq("id", int(row['id'])).execute()
                            show_success_modal("任务抢夺成功！")
                        else: st.warning("✋ 贪多嚼不烂！您已有 2 个公共任务在进行中（含返工）。")
    st.divider()
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("🔭 实时动态 (最近35条)")
        if not tdf.empty and 'status' in tdf.columns:
            active = tdf[tdf['status'].isin(['进行中', '返工', '待验收'])].sort_values("created_at", ascending=False).head(35)
            if not active.empty:
                active['Deadline'] = active['deadline'].apply(format_deadline)
                st.dataframe(active[['title', 'assignee', 'status', 'Deadline']], use_container_width=True, hide_index=True)
            else: st.caption("暂无活跃任务")
        else: st.caption("暂无数据")
    with c2:
        st.subheader("📜 荣誉记录 (最近35条)")
        if not tdf.empty and 'status' in tdf.columns:
            done = tdf[tdf['status']=='完成'].sort_values('completed_at', ascending=False).head(35)
            if not done.empty:
                done['P'] = done.apply(lambda x: "研发任务" if x.get('is_rnd') else f"D{x['difficulty']}/T{x['std_time']}/Q{x['quality']}", axis=1)
                done['💰 获益'] = done.apply(lambda x: 0 if x.get('is_rnd') else (safe_float(x.get('difficulty')) * safe_float(x.get('std_time')) * safe_float(x.get('quality'))), axis=1)
                st.dataframe(done[['title', 'assignee', 'P', '💰 获益']], use_container_width=True, hide_index=True)
            else: st.caption("暂无完成记录")
        else: st.caption("暂无数据")

# --- 3. 颜祖广场 ---
elif nav == "🗣️ 颜祖广场":
    st.header("🗣️ 颜祖广场")
    with st.form("msg_form", clear_on_submit=True):
        txt = st.text_input("💬 说点什么...")
        if st.form_submit_button("发送"):
            if txt:
                supabase.table("messages").insert({"username": user, "content": txt}).execute()
                st.rerun()
    msgs = run_query("messages")
    if not msgs.empty:
        msgs = msgs.sort_values("created_at", ascending=False).head(50)
        for _, m in msgs.iterrows():
            if m['username'] == "__NOTICE__": continue
            with st.chat_message("user" if m['username']==user else "assistant"):
                st.write(f"**{m['username']}**: {m['content']}")
                st.caption(f"{m['created_at']}")

# --- 4. 风云榜 ---
elif nav == "🏆 风云榜":
    st.header("🏆 风云榜 (Live Leaderboard)")
    
    users = run_query("users")
    if not users.empty:
        members = users[users['role'] != 'admin']['username'].tolist()
        
        all_tasks = run_query("tasks")
        all_pens = run_query("penalties")
        all_rews = run_query("rewards")
        
        leader_data = []
        for m in members:
            val_7 = calculate_net_yvp(m, all_tasks, all_pens, all_rews, 7)
            val_30 = calculate_net_yvp(m, all_tasks, all_pens, all_rews, 30)
            val_total = calculate_net_yvp(m, all_tasks, all_pens, all_rews)
            leader_data.append({
                "成员": m,
                "📅 7天净值": val_7,
                "🗓️ 30天净值": val_30,
                "💰 总净资产": val_total
            })
        
        df_leader = pd.DataFrame(leader_data).sort_values("💰 总净资产", ascending=False)
        
        if len(df_leader) >= 3:
            medals = ["🥇", "🥈", "🥉"]
            cols = st.columns(3)
            for i, col in enumerate(cols):
                row = df_leader.iloc[i]
                col.markdown(f"""
                    <div style="text-align:center; padding:20px; 
                                background:{'#fff9db' if i==0 else '#f8f9fa'}; 
                                border-radius:12px; border:1px solid #e0e0e0;">
                        <div style="font-size:2.5em;">{medals[i]}</div>
                        <div style="font-size:1.2em; font-weight:bold;">{row['成员']}</div>
                        <div style="font-size:1.5em; color:#d4a017;">{row['💰 总净资产']}</div>
                    </div>
                """, unsafe_allow_html=True)
        
        st.dataframe(df_leader, use_container_width=True, hide_index=True)
            
    st.divider()
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("🚨 警示录 (最近缺勤)")
        pens = run_query("penalties")
        if not pens.empty:
            st.dataframe(pens[['username', 'reason', 'occurred_at']].sort_values('occurred_at', ascending=False).head(10), use_container_width=True, hide_index=True)
        else: st.info("暂无违规记录")
    
    with c2:
        st.subheader("🎁 荣誉榜 (最近赏赐)")
        rews = run_query("rewards")
        if not rews.empty:
            st.dataframe(rews[['username', 'amount', 'reason', 'created_at']].sort_values('created_at', ascending=False).head(10), use_container_width=True, hide_index=True)
        else: st.info("暂无赏赐记录")

# --- 5. 个人中心 ---
elif nav == "🏰 个人中心":
    if role == 'admin':
        st.header("👑 统帅后台")
        if datetime.date.today().day in [10, 20, 30]:
            st.warning("📅 **今日为备份提醒日，请前往备份页签下载全量备份！**")
        
        tabs = st.tabs(["⚡️ 我的战场", "💰 分润统计", "🚀 发布任务", "🛠️ 全量管理", "🎁 人员与奖惩", "⚖️ 裁决审核", "📢 公告维护", "💾 备份恢复"])
        
        with tabs[0]: 
            st.subheader("⚡️ 快捷派发")
            qc1, qc2 = st.columns([3, 1])
            quick_t = qc1.text_input("内容", key="adm_q_t")
            quick_d = qc2.date_input("截止", value=None, key="adm_q_d")
            if st.button("派发给我", type="primary", key="adm_q_btn"):
                supabase.table("tasks").insert({"title": quick_t, "difficulty": 0, "std_time": 0, "status": "进行中", "assignee": user, "type": "AdminSelf", "deadline": str(quick_d) if quick_d else None, "battlefield_id": -1}).execute()
                show_success_modal("已添加")
            st.divider()
            st.subheader("🛡️ 进行中")
            tdf = run_query("tasks")
            if not tdf.empty and 'status' in tdf.columns:
                my_adm = tdf[(tdf['assignee'] == user) & (tdf['status'] == '进行中')]
                for i, r in my_adm.iterrows():
                    with st.container(border=True):
                        ic1, ic2 = st.columns([4, 1])
                        with ic1:
                            st.markdown(f"**{r['title']}**")
                            st.write(f"📅 **截止**: {format_deadline(r.get('deadline'))}")
                        if ic2.button("✅ 完成", key=f"fin_{r['id']}"):
                            supabase.table("tasks").update({"status": "完成", "quality": 1.0, "completed_at": str(datetime.date.today()), "feedback": "统帅自结"}).eq("id", int(r['id'])).execute()
                            show_success_modal("已归档")
            show_task_history(user, role)

        with tabs[1]: # 分润
            st.subheader("💰 周期分润统计")
            c_d1, c_d2 = st.columns(2)
            d_start = c_d1.date_input("开始日期", value=datetime.date.today().replace(day=1), key="stats_d1")
            d_end = c_d2.date_input("结束日期", value=datetime.date.today(), key="stats_d2")
            if st.button("📊 开始统计", type="primary"):
                report = calculate_period_stats(d_start, d_end)
                if not report.empty:
                    st.dataframe(report, use_container_width=True, hide_index=True)
                    csv = report.to_csv(index=False).encode('utf-8')
                    st.download_button("📥 下载报表", csv, f"yvp_report.csv", "text/csv")
                else: st.warning("无数据或计算报错，请检查控制台。")

        with tabs[2]: # 发布
            camps = run_query("campaigns")
            batts = run_query("battlefields")
            c1, c2 = st.columns(2)
            t_name = c1.text_input("任务标题", key="pub_t")
            t_desc = st.text_area("详情", key="pub_desc")
            st.markdown("---")
            st.markdown("⚔️ **战略归属**")
            sc1, sc2 = st.columns(2)
            camp_opts = camps['title'].tolist() if not camps.empty else []
            if not camp_opts: st.warning("请先建立战役！"); st.stop()
            sel_camp_t = sc1.selectbox("所属战役", camp_opts, key="pub_sel_camp")
            sel_camp_id = camps[camps['title']==sel_camp_t].iloc[0]['id']
            batt_opts_df = pd.DataFrame()
            if not batts.empty: batt_opts_df = batts[batts['campaign_id'] == sel_camp_id]
            if not batt_opts_df.empty:
                batt_opts = batt_opts_df['title'].tolist()
                sel_batt_t = sc2.selectbox("所属战场", batt_opts, key="pub_sel_batt")
                sel_batt_id = batt_opts_df[batt_opts_df['title']==sel_batt_t].iloc[0]['id']
            else: sc2.warning("无战场"); sel_batt_id = None
            st.markdown("---")
            is_rnd_task = st.checkbox("🟣 标记为【产品研发任务】", key="pub_is_rnd")
            col_d, col_c = c1.columns([3,2])
            d_inp = col_d.date_input("截止日期", key="pub_d")
            no_d = col_c.checkbox("无截止日期", key="pub_no_d")
            if is_rnd_task: diff=0.0; stdt=0.0; c2.info("研发任务不设工时")
            else: 
                diff = c2.number_input("难度", value=1.0, min_value=0.0, step=0.1, format="%.1f")
                stdt = c2.number_input("工时", value=1.0, min_value=0.0, step=0.1, format="%.1f")
            ttype = c2.radio("模式", ["公共任务池", "指派成员"], key="pub_type")
            
            selected_assignees = []
            if ttype == "指派成员":
                udf = run_query("users")
                all_members = udf[udf['role']!='admin']['username'].tolist() if not udf.empty else []
                assign_all = st.checkbox("⚡️ 一键指派给全员 (除管理员)", key="pub_all")
                if assign_all:
                    selected_assignees = all_members
                    st.info(f"已选择全员：{', '.join(all_members)}")
                else:
                    selected_assignees = st.multiselect("选择人员 (可多选)", all_members, key="pub_ass")
            else:
                selected_assignees = ["待定"]

            if st.button("🚀 确认发布", type="primary", key="pub_btn"):
                if sel_batt_id:
                    tasks_to_insert = []
                    for assignee in selected_assignees:
                        tasks_to_insert.append({
                            "title": t_name, "description": t_desc, "difficulty": diff, "std_time": stdt, 
                            "status": "待领取" if ttype=="公共任务池" else "进行中", "assignee": assignee, 
                            "deadline": None if no_d else str(d_inp), "type": ttype, "battlefield_id": int(sel_batt_id), "is_rnd": is_rnd_task
                        })
                    if tasks_to_insert:
                        supabase.table("tasks").insert(tasks_to_insert).execute()
                        show_success_modal(f"成功发布 {len(tasks_to_insert)} 条任务！")
                    else: st.error("请选择至少一名执行者")

        with tabs[3]: # 全量管理
            st.subheader("🛠️ 精准修正")
            tdf = run_query("tasks"); udf = run_query("users")
            all_users = list(udf['username'].unique()) if not udf.empty else []
            cf1, cf2 = st.columns(2)
            fu = cf1.selectbox("筛选人员", ["全部"] + all_users, key="mng_u")
            sk = cf2.text_input("搜标题", key="mng_k")
            fil = tdf.copy()
            if not fil.empty:
                if fu != "全部": fil = fil[fil['assignee'] == fu]
                if sk: fil = fil[fil['title'].str.contains(sk, case=False, na=False)]
            if not fil.empty:
                tid = st.selectbox("选择任务", fil['id'], format_func=lambda x: f"ID:{x}|{fil[fil['id']==x]['title'].values[0]}", key="mng_sel")
                tar = fil[fil['id']==tid].iloc[0]
                with st.container(border=True):
                    c_edit_1, c_edit_2 = st.columns([3, 1])
                    new_title = c_edit_1.text_input("标题", tar['title'], key=f"et_{tid}")
                    curr_ass = tar['assignee']
                    try: ass_idx = all_users.index(curr_ass)
                    except: ass_idx = 0
                    new_assignee = c_edit_2.selectbox("指派给", all_users, index=ass_idx, key=f"eass_{tid}")
                    new_desc = st.text_area("详情", value=tar.get('description') or "", key=f"edesc_{tid}")
                    
                    curr_is_rnd = tar.get('is_rnd', False)
                    edit_is_rnd = st.checkbox("🟣 产品研发任务", value=curr_is_rnd, key=f"e_rnd_{tid}")
                    c_p1, c_p2, c_p3 = st.columns(3)
                    if edit_is_rnd: new_diff=0.0; new_stdt=0.0
                    else: 
                        new_diff = c_p1.number_input("难度", value=float(tar['difficulty'] or 0), min_value=0.0, step=0.1, format="%.1f", key=f"ed_{tid}")
                        new_stdt = c_p2.number_input("工时", value=float(tar['std_time'] or 0), min_value=0.0, step=0.1, format="%.1f", key=f"est_{tid}")
                    new_qual = c_p3.number_input("质量", value=float(tar['quality'] or 0), key=f"eq_{tid}")
                    
                    c_s1, c_s2, c_s3 = st.columns([2, 2, 1])
                    new_status = c_s1.selectbox("状态", ["待领取", "进行中", "待验收", "完成", "返工"], index=["待领取", "进行中", "待验收", "完成", "返工"].index(tar['status']), key=f"es_{tid}")
                    curr_d = pd.to_datetime(tar['deadline']).date() if tar['deadline'] else None
                    new_d = c_s2.date_input("截止", value=curr_d, key=f"edd_{tid}")
                    no_d = c_s3.checkbox("无截止", value=(curr_d is None), key=f"end_{tid}")

                    if st.button("💾 保存修改", key=f"eb_{tid}", type="primary"):
                        supabase.table("tasks").update({"title": new_title, "description": new_desc, "assignee": new_assignee, "deadline": None if no_d else str(new_d), "difficulty": new_diff, "std_time": new_stdt, "quality": new_qual, "status": new_status, "is_rnd": edit_is_rnd}).eq("id", int(tid)).execute()
                        show_success_modal("更新成功")
                    with st.popover("🗑️ 删除"):
                        if st.button("确认", key=f"btn_del_task_{tid}", type="primary"):
                            supabase.table("tasks").delete().eq("id", int(tid)).execute()
                            show_success_modal("删除成功")

        with tabs[4]: # 奖惩
            udf = run_query("users")
            members = udf[udf['role']!='admin']['username'].tolist() if not udf.empty else []
            c_p, c_r = st.columns(2)
            with c_p:
                st.markdown("#### 🚨 考勤管理")
                target_p = st.selectbox("缺勤成员", members, key="pen_u")
                date_p = st.date_input("缺勤日期", key="pen_d")
                if st.button("🔴 记录缺勤", key="btn_pen"):
                    supabase.table("penalties").insert({"username": target_p, "occurred_at": str(date_p), "reason": "缺勤"}).execute()
                    show_success_modal("已记录")
                st.caption("最近记录 (可撤销)")
                pens = run_query("penalties")
                if not pens.empty:
                    for i, p in pens.sort_values('occurred_at', ascending=False).head(5).iterrows():
                        c1, c2 = st.columns([4,1])
                        c1.write(f"{p['username']} - {p['occurred_at']}")
                        if c2.button("🗑️", key=f"del_pen_{p['id']}"):
                            supabase.table("penalties").delete().eq("id", int(p['id'])).execute(); st.rerun()
            with c_r:
                st.markdown("#### 🎁 手动赏赐")
                target_r = st.selectbox("赏赐成员", members, key="rew_u")
                amt_r = st.number_input("奖励YVP", min_value=0.0, step=0.1, key="rew_a") 
                reason_r = st.text_input("理由", key="rew_re")
                
                if st.button("🎁 确认赏赐", type="primary", key="btn_rew"):
                    try:
                        # V42.11 强行剥离时区冲突写入
                        supabase.table("rewards").insert({
                            "username": target_r, 
                            "amount": float(amt_r), 
                            "reason": reason_r
                        }).execute()
                        show_success_modal(f"已赏赐 {target_r} {amt_r} 点")
                    except Exception as e:
                        st.error(f"❌ 写入失败！数据库拒绝访问。请去 Supabase SQL Editor 执行: ALTER TABLE rewards DISABLE ROW LEVEL SECURITY;\n\n详细报错: {e}")

                st.caption("最近记录 (可撤销/修改)")
                rews = run_query("rewards")
                if not rews.empty:
                    for i, r in rews.sort_values('created_at', ascending=False).head(10).iterrows():
                        with st.container(border=True):
                            c1, c2 = st.columns([4,1])
                            c1.markdown(f"**{r['username']}**: {r['reason']} (+{r['amount']})")
                            with c2.popover("⚙️"):
                                new_rew_r = st.text_input("改理由", r['reason'], key=f"err_{r['id']}")
                                new_rew_a = st.number_input("改金额", value=float(r['amount']), key=f"era_{r['id']}")
                                if st.button("保存", key=f"ersv_{r['id']}"):
                                    supabase.table("rewards").update({"reason": new_rew_r, "amount": new_rew_a}).eq("id", int(r['id'])).execute()
                                    st.rerun()
                                if st.button("🗑️", key=f"del_rew_{r['id']}"):
                                    supabase.table("rewards").delete().eq("id", int(r['id'])).execute(); st.rerun()

        with tabs[5]: # 裁决
            pend = run_query("tasks")
            if not pend.empty and 'status' in pend.columns:
                pend = pend[pend['status'] == '待验收']
                if not pend.empty:
                    sel_p = st.selectbox("待审任务", pend['id'], format_func=lambda x: pend[pend['id']==x]['title'].values[0])
                    with st.container(border=True):
                        res = st.selectbox("裁决结果", ["完成", "返工"])
                        if res == "完成": qual = st.slider("质量评分", 0.0, 3.0, 1.0, 0.1)
                        else: qual = None 
                        fb = st.text_area("御批反馈")
                        if st.button("提交审核"):
                            cat = str(datetime.date.today()) if res=="完成" else None
                            q_val = qual if res=="完成" else 0.0
                            supabase.table("tasks").update({"quality": q_val, "status": res, "feedback": fb, "completed_at": cat}).eq("id", int(sel_p)).execute()
                            show_success_modal("已裁决")
                else: st.info("暂无待审任务")

        with tabs[6]: # 公告
            new_ann = st.text_input("输入新公告内容", placeholder=get_announcement())
            if st.button("发布公告"): update_announcement(new_ann); st.success("已更新")

        with tabs[7]: # 备份与恢复
            st.subheader("💾 备份与恢复")
            d1=run_query("users"); d2=run_query("tasks"); d3=run_query("penalties"); d4=run_query("messages"); d5=run_query("rewards"); d6=run_query("daily_todos")
            buf = io.StringIO()
            buf.write("===USERS===\n"); d1.to_csv(buf, index=False)
            buf.write("\n===TASKS===\n"); d2.to_csv(buf, index=False)
            buf.write("\n===PENALTIES===\n"); d3.to_csv(buf, index=False)
            buf.write("\n===MESSAGES===\n"); d4.to_csv(buf, index=False)
            buf.write("\n===REWARDS===\n"); d5.to_csv(buf, index=False)
            buf.write("\n===DAILY_TODOS===\n"); d6.to_csv(buf, index=False)
            st.download_button("📥 下载全量备份 (Backup)", buf.getvalue(), f"backup_{datetime.date.today()}.txt")
            st.divider()
            upf = st.file_uploader("📤 上传备份文件进行恢复", type=['txt'], key="up_f")
            if upf:
                if st.button("🚨 确认覆盖恢复", type="primary"):
                    try:
                        content = upf.getvalue().decode("utf-8")
                        s_u = content.split("===USERS===\n")[1].split("===TASKS===")[0].strip()
                        s_t = content.split("===TASKS===\n")[1].split("===PENALTIES===")[0].strip()
                        s_p = content.split("===PENALTIES===\n")[1].split("===MESSAGES===")[0].strip()
                        s_m = content.split("===MESSAGES===\n")[1].split("===REWARDS===")[0].strip()
                        s_r = content.split("===REWARDS===\n")[1].split("===DAILY_TODOS===")[0].strip()
                        s_d = content.split("===DAILY_TODOS===\n")[1].strip()
                        supabase.table("users").delete().neq("username", "_").execute()
                        supabase.table("tasks").delete().neq("id", -1).execute()
                        supabase.table("penalties").delete().neq("id", -1).execute()
                        supabase.table("messages").delete().neq("id", -1).execute()
                        supabase.table("rewards").delete().neq("id", -1).execute()
                        supabase.table("daily_todos").delete().neq("id", -1).execute()
                        if s_u: supabase.table("users").insert(pd.read_csv(io.StringIO(s_u)).to_dict('records')).execute()
                        if s_t: supabase.table("tasks").insert(pd.read_csv(io.StringIO(s_t)).to_dict('records')).execute()
                        if s_p: supabase.table("penalties").insert(pd.read_csv(io.StringIO(s_p)).to_dict('records')).execute()
                        if s_m: supabase.table("messages").insert(pd.read_csv(io.StringIO(s_m)).to_dict('records')).execute()
                        if s_r: supabase.table("rewards").insert(pd.read_csv(io.StringIO(s_r)).to_dict('records')).execute()
                        if s_d: supabase.table("daily_todos").insert(pd.read_csv(io.StringIO(s_d)).to_dict('records')).execute()
                        st.success("✅ 恢复完成！"); time.sleep(1); st.rerun()
                    except Exception as e: st.error(f"恢复失败: {e}")

    else: # 成员界面
        st.header("⚔️ 我的战场")
        batts = run_query("battlefields")
        camps = run_query("campaigns")
        tdf = run_query("tasks")
        if not tdf.empty and 'status' in tdf.columns:
            my = tdf[(tdf['assignee']==user) & (tdf['status'].isin(['进行中', '返工']))].copy()
            my['deadline_dt'] = pd.to_datetime(my['deadline'], errors='coerce')
            my = my.sort_values(by='deadline_dt', ascending=True, na_position='last')
            for i, r in my.iterrows():
                # V42.0 使用统一卡片渲染
                render_task_card(r, batts, camps)
                with st.expander("📄 详情"):
                    st.write(r.get('description', '无'))
                    if r['status'] == '返工': st.error(f"返工原因: {r.get('feedback', '无')}")
                if st.button("✅ 交付验收", key=f"dev_{r['id']}", type="primary"):
                    supabase.table("tasks").update({"status": "待验收"}).eq("id", int(r['id'])).execute()
                    show_success_modal("已交付")
        show_task_history(user, role)
        st.divider()
        with st.expander("🔐 修改密码"):
            np = st.text_input("新密码", type="password", key="m_p")
            if st.button("确认更改", key="m_p_btn"):
                supabase.table("users").update({"password": np}).eq("username", user).execute()
                st.success("已更新")
