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
    page_title="颜祖美学·执行中枢 V36.4",
    page_icon="🏛️",
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
            background-color: #fff3cd;
            color: #856404;
            padding: 10px;
            text-align: center;
            font-weight: bold;
            border-bottom: 1px solid #ffeeba;
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
except Exception:
    st.error("🚨 数据库连接配置有误，请检查 Secrets。")
    st.stop()

# --- 3. Cookie 管理器 ---
cookie_manager = stx.CookieManager(key="yanzu_v36_4_move_fix")

# --- 4. 核心工具函数 ---
@st.cache_data(ttl=2) 
def run_query(table_name):
    schemas = {
        'tasks': ['id', 'title', 'battlefield_id', 'status', 'deadline', 'is_rnd', 'assignee', 'difficulty', 'std_time', 'quality', 'created_at', 'completed_at', 'description', 'feedback', 'type'],
        'campaigns': ['id', 'title', 'deadline', 'order_index', 'status'],
        'battlefields': ['id', 'title', 'campaign_id', 'order_index'],
        'users': ['username', 'password', 'role'],
        'penalties': ['id', 'username', 'reason', 'occurred_at'],
        'rewards': ['id', 'username', 'amount', 'reason', 'created_at'],
        'messages': ['id', 'username', 'content', 'created_at']
    }
    try:
        response = supabase.table(table_name).select("*").execute()
        df = pd.DataFrame(response.data)
        if df.empty: return pd.DataFrame(columns=schemas.get(table_name, []))
        for col in schemas.get(table_name, []):
            if col not in df.columns: df[col] = None 
        for col in ['created_at', 'deadline', 'completed_at', 'occurred_at']:
            if col in df.columns:
                try: df[col] = pd.to_datetime(df[col], errors='coerce').dt.date
                except: pass
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

def get_announcement():
    try:
        res = supabase.table("messages").select("content").eq("username", "__NOTICE__").order("created_at", desc=True).limit(1).execute()
        return res.data[0]['content'] if res.data else "欢迎来到颜祖美学执行中枢！"
    except: return "公告加载中..."

def update_announcement(text):
    supabase.table("messages").delete().eq("username", "__NOTICE__").execute()
    supabase.table("messages").insert({"username": "__NOTICE__", "content": text, "created_at": str(datetime.datetime.now())}).execute()

def calculate_net_yvp(username, days_lookback=None):
    users = run_query("users")
    if users.empty: return 0.0
    user_row = users[users['username']==username]
    if not user_row.empty and user_row.iloc[0]['role'] == 'admin': return 0.0

    tasks = run_query("tasks")
    gross = 0.0
    if not tasks.empty:
        my_done = tasks[(tasks['assignee'] == username) & (tasks['status'] == '完成')].copy()
        if not my_done.empty:
            if 'is_rnd' not in my_done.columns: my_done['is_rnd'] = False
            else: my_done['is_rnd'] = my_done['is_rnd'].fillna(False)
            my_done['val'] = my_done.apply(lambda x: 0.0 if x['is_rnd'] else (x['difficulty'] * x['std_time'] * x['quality']), axis=1)
            my_done['completed_at'] = pd.to_datetime(my_done['completed_at'])
            if days_lookback:
                cutoff = pd.Timestamp.now() - pd.Timedelta(days=days_lookback)
                my_done = my_done[my_done['completed_at'] >= cutoff]
            gross = my_done['val'].sum()

    total_fine = 0.0
    penalties = run_query("penalties")
    if not penalties.empty:
        my_pens = penalties[penalties['username'] == username].copy()
        if not my_pens.empty:
            my_pens['occurred_at'] = pd.to_datetime(my_pens['occurred_at'])
            if days_lookback:
                cutoff = pd.Timestamp.now() - pd.Timedelta(days=days_lookback)
                my_pens = my_pens[my_pens['occurred_at'] >= cutoff]
            for _, pen in my_pens.iterrows():
                if not tasks.empty:
                    w_start = pen['occurred_at'] - pd.Timedelta(days=7)
                    base_tasks = tasks[(tasks['assignee'] == username) & (tasks['status'] == '完成')].copy()
                    if not base_tasks.empty:
                        base_tasks['is_rnd'] = base_tasks['is_rnd'].fillna(False)
                        base_tasks['val'] = base_tasks.apply(lambda x: 0.0 if x['is_rnd'] else (x['difficulty'] * x['std_time'] * x['quality']), axis=1)
                        base_tasks['completed_at'] = pd.to_datetime(base_tasks['completed_at'])
                        w_tasks = base_tasks[(base_tasks['completed_at'] >= w_start) & (base_tasks['completed_at'] <= pen['occurred_at'])]
                        total_fine += w_tasks['val'].sum() * 0.2
    
    total_reward = 0.0
    rewards = run_query("rewards")
    if not rewards.empty:
        my_rewards = rewards[rewards['username'] == username].copy()
        if not my_rewards.empty:
            my_rewards['created_at'] = pd.to_datetime(my_rewards['created_at'])
            if days_lookback:
                cutoff = pd.Timestamp.now() - pd.Timedelta(days=days_lookback)
                my_rewards = my_rewards[my_rewards['created_at'] >= cutoff]
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
                m_tasks['is_rnd'] = m_tasks['is_rnd'].fillna(False)
                m_tasks['c_dt'] = pd.to_datetime(m_tasks['completed_at'])
                in_range = m_tasks[(m_tasks['c_dt'] >= ts_start) & (m_tasks['c_dt'] <= ts_end)]
                gross = in_range[in_range['is_rnd']==False].apply(lambda x: x['difficulty'] * x['std_time'] * x['quality'], axis=1).sum()
        fine = 0.0
        if not pens.empty:
            m_pens = pens[(pens['username'] == m)].copy()
            m_pens['o_dt'] = pd.to_datetime(m_pens['occurred_at'])
            in_range_pens = m_pens[(m_pens['o_dt'] >= ts_start) & (m_pens['o_dt'] <= ts_end)]
            for _, p in in_range_pens.iterrows(): fine += 0 
        reward_val = 0.0
        if not rews.empty:
            m_rews = rews[rews['username'] == m].copy()
            m_rews['c_dt'] = pd.to_datetime(m_rews['created_at'])
            reward_val = m_rews[(m_rews['c_dt'] >= ts_start) & (m_rews['c_dt'] <= ts_end)]['amount'].sum()
        net = gross - fine + reward_val
        stats_data.append({"成员": m, "任务产出": round(gross, 2), "罚款": round(fine, 2), "奖励": round(reward_val, 2), "💰 应发YVP": round(net, 2)})
    return pd.DataFrame(stats_data).sort_values("💰 应发YVP", ascending=False) if stats_data else pd.DataFrame()

def format_deadline(d_val):
    return str(d_val) if (not pd.isna(d_val) and str(d_val) not in ['NaT', 'None', '']) else "♾️ 无期限"

def show_task_history(username, role):
    st.divider()
    st.subheader("📜 任务历史档案")
    df = run_query("tasks")
    if df.empty:
        st.info("暂无数据")
        return
    my_history = df[(df['assignee'] == username) & (df['status'] == '完成')].copy()
    my_history['is_rnd'] = my_history['is_rnd'].fillna(False)
    if my_history.empty:
        st.info("暂无已完成的任务记录")
    else:
        my_history = my_history.sort_values("completed_at", ascending=False).head(15)
        for i, r in my_history.iterrows():
            with st.container(border=True):
                st.markdown(f"**✅ {r['title']}**")
                c1, c2, c3 = st.columns(3)
                earned = 0 if r['is_rnd'] else (r['difficulty'] * r['std_time'] * r['quality'])
                c1.write(f"💰 **+{round(earned, 2)}**")
                c2.caption(f"归档: {r['completed_at']}")
                c3.caption("研发任务" if r['is_rnd'] else "普通任务")

@st.dialog("✅ 系统提示")
def show_success_modal(msg="操作成功！"):
    st.write(msg)
    if st.button("关闭", type="primary"): force_refresh()

# --- 快捷发布任务弹窗 ---
@st.dialog("➕ 在此发布任务")
def quick_publish_modal(camp_id, batt_id, batt_title):
    st.markdown(f"🛡️ **目标战场：{batt_title}**")
    t_name = st.text_input("任务标题", key=f"qp_t_{batt_id}")
    t_desc = st.text_area("详情", key=f"qp_desc_{batt_id}")
    st.markdown("---")
    is_rnd_task = st.checkbox("🟣 标记为【产品研发任务】", key=f"qp_rnd_{batt_id}")
    c1, c2 = st.columns(2)
    d_inp = c1.date_input("截止日期", key=f"qp_d_{batt_id}")
    no_d = c2.checkbox("无截止", key=f"qp_nd_{batt_id}")
    if is_rnd_task:
        diff = 0.0; stdt = 0.0; st.caption("研发任务不设难度与工时")
    else:
        diff = st.number_input("难度", value=1.0, key=f"qp_diff_{batt_id}")
        stdt = st.number_input("工时", value=1.0, key=f"qp_std_{batt_id}")
    ttype = st.radio("模式", ["公共任务池", "指派成员"], key=f"qp_type_{batt_id}")
    assign = "待定"
    if ttype == "指派成员":
        udf = run_query("users")
        user_list = udf['username'].tolist() if not udf.empty else []
        assign = st.selectbox("人员", user_list, key=f"qp_ass_{batt_id}")
    if st.button("🚀 确认发布", type="primary"):
        supabase.table("tasks").insert({
            "title": t_name, "description": t_desc, "difficulty": diff, "std_time": stdt, 
            "status": "待领取" if ttype=="公共任务池" else "进行中", "assignee": assign, 
            "deadline": None if no_d else str(d_inp), "type": ttype, "battlefield_id": int(batt_id), "is_rnd": is_rnd_task
        }).execute()
        st.success("发布成功！"); force_refresh()

# --- 任务调动弹窗 (曲线救国：两步选择法) ---
@st.dialog("🔀 任务战略转移")
def move_task_modal(task_id, task_title, current_camp_id, current_batt_id):
    st.markdown(f"🔥 正在调动：**{task_title}**")
    st.info("请依次选择目标战役和战场：")
    
    # 1. 拿数据
    camps = run_query("campaigns")
    batts = run_query("battlefields")
    
    if camps.empty: st.error("无战役数据"); return
    
    # 2. 第一步：选战役
    camp_dict = {int(row['id']): row['title'] for _, row in camps.iterrows()}
    
    # 默认选中当前的战役
    default_camp_idx = 0
    camp_ids_list = list(camp_dict.keys())
    if int(current_camp_id) in camp_ids_list:
        default_camp_idx = camp_ids_list.index(int(current_camp_id))
        
    selected_camp_id = st.selectbox("📌 第一步：选择目标战役", options=camp_ids_list, format_func=lambda x: camp_dict[x], index=default_camp_idx)
    
    # 3. 第二步：选战场 (根据战役筛选)
    filtered_batts = batts[batts['campaign_id'] == selected_camp_id]
    
    if filtered_batts.empty:
        st.warning("⚠️ 该战役下暂无战场，请先去开辟！")
        return
    
    batt_dict = {int(row['id']): row['title'] for _, row in filtered_batts.iterrows()}
    
    # 默认选中当前的战场 (如果还在同战役下)
    default_batt_idx = 0
    batt_ids_list = list(batt_dict.keys())
    if int(current_batt_id) in batt_ids_list:
        default_batt_idx = batt_ids_list.index(int(current_batt_id))
        
    selected_batt_id = st.selectbox("🛡️ 第二步：选择目标战场", options=batt_ids_list, format_func=lambda x: batt_dict[x], index=default_batt_idx)
    
    st.divider()
    
    if st.button("🚀 确认调动", type="primary"):
        if selected_batt_id == int(current_batt_id):
            st.warning("任务已在当前战场，未发生变动。")
        else:
            supabase.table("tasks").update({"battlefield_id": int(selected_batt_id)}).eq("id", int(task_id)).execute()
            st.success(f"✅ 调动成功！已转移至：{camp_dict[selected_camp_id]} > {batt_dict[selected_batt_id]}")
            time.sleep(0.5)
            force_refresh()

# --- 5. 鉴权与自动登录 ---
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
            else:
                cookie_manager.delete("yanzu_user")
        except:
            st.session_state.user = c_user
            st.session_state.role = cookie_manager.get("yanzu_role") or 'member'
        st.rerun()

if st.session_state.user is None:
    st.title("🏛️ 颜祖美学·执行中枢")
    QUOTES = ["没有执行力，一切战略都是空谈。", "管理者的跃升，是从'对任务负责'到'对目标负责'。", "极致的交付，是最高级的才华。"]
    st.markdown(f"""<div class="scrolling-text"><marquee scrollamount="6">🔥 {random.choice(QUOTES)}</marquee></div>""", unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    with c1:
        with st.form("login"):
            st.markdown("### 🔑 登录")
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
                        st.rerun()
                    else: st.error("账号或密码错误")
                except: st.error("连接超时，请重试")
    with c2:
        with st.expander("📝 注册新成员"):
            nu = st.text_input("用户名", key="reg_u")
            np = st.text_input("密码", type="password", key="reg_p")
            if st.button("提交注册", key="btn_reg"):
                try:
                    supabase.table("users").insert({"username": nu, "password": np, "role": "member"}).execute()
                    st.success("注册成功！请直接登录。")
                except: st.warning("用户名已存在")
    st.stop()

user = st.session_state.user
role = st.session_state.role

# 侧边栏
with st.sidebar:
    st.header(f"👤 {user}")
    st.caption(f"身份: {'👑 统帅' if role=='admin' else '⚔️ 成员'}")
    if role == 'admin': st.success("运筹帷幄之中，决胜千里之外。")
    else:
        yvp_7 = calculate_net_yvp(user, 7)
        yvp_all = calculate_net_yvp(user)
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

nav = st.radio("NAV", ["🔭 战略作战室", "📋 任务大厅", "🗣️ 颜祖广场", "🏆 风云榜", "🏰 个人中心"], horizontal=True, label_visibility="collapsed")
st.divider()

# ================= 业务路由 =================

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
                with st.popover("🚩 新建战役"):
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
                    st.progress(prog, text=f"进度: {int(prog*100)}%")
                else: st.progress(0, text="整备中...")

                if not camp_batts.empty:
                    for _, batt in camp_batts.iterrows():
                        bc1, bc2 = st.columns([0.9, 0.1])
                        if edit_mode and role == 'admin' and batt['id'] != -1:
                            with bc2.popover("⚙️", key=f"b_pop_{batt['id']}"):
                                eb_t = st.text_input("战场名称", value=batt['title'], key=f"ebt_{batt['id']}")
                                eb_idx = st.number_input("排序", value=int(batt.get('order_index', 0)), step=1, key=f"ebidx_{batt['id']}")
                                if st.button("保存", key=f"bsv_{batt['id']}"):
                                    supabase.table("battlefields").update({"title": eb_t, "order_index": eb_idx}).eq("id", int(batt['id'])).execute()
                                    st.success("✅ 保存成功"); force_refresh()
                                st.divider()
                                if st.button("🗑️ 删除", key=f"bdel_{batt['id']}", type="primary"):
                                    has_task = False
                                    if not all_tasks.empty and 'battlefield_id' in all_tasks.columns:
                                         if not all_tasks[all_tasks['battlefield_id'] == batt['id']].empty: has_task = True
                                    if has_task: st.error("请先清空任务！")
                                    else:
                                        supabase.table("battlefields").delete().eq("id", int(batt['id'])).execute()
                                        st.success("✅ 删除成功"); force_refresh()

                        with bc1.expander(f"🛡️ {batt['title']}", expanded=True):
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
                                            t_icon = "🟣" if task.get('is_rnd') else "⚔️"
                                            t_dead = format_deadline(task.get('deadline'))
                                            st.markdown(f"**{t_icon} {task['title']}** <span style='color:grey;font-size:0.8em'>({task['assignee']} | {task['status']} | 📅 {t_dead})</span>", unsafe_allow_html=True)
                                        if edit_mode and role == 'admin':
                                            with cols_task[1]:
                                                if st.button("🔀", key=f"mv_{task['id']}", help="全域调动"):
                                                    # 核心修改：传递战役ID，启动两步法
                                                    move_task_modal(task['id'], task['title'], camp['id'], batt['id'])
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
    
    def get_task_label(bid, is_rnd=False):
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

    st.subheader("🔥 待抢任务池")
    if not tdf.empty and 'status' in tdf.columns:
        pool = tdf[(tdf['status']=='待领取') & (tdf['type']=='公共任务池')]
        if not pool.empty:
            cols = st.columns(3)
            for i, (idx, row) in enumerate(pool.iterrows()):
                with cols[i % 3]:
                    with st.container(border=True):
                        st.markdown(get_task_label(row.get('battlefield_id'), row.get('is_rnd')), unsafe_allow_html=True)
                        st.markdown(f"**{row['title']}**")
                        if row.get('is_rnd'): st.caption("🟣 研发任务 (不计工时)")
                        else: st.write(f"⚙️ **难度**: {row['difficulty']} | ⏱️ **工时**: {row['std_time']}")
                        st.write(f"📅 **截止**: {format_deadline(row.get('deadline'))}")
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
                done['💰 获益'] = done.apply(lambda x: 0 if x.get('is_rnd') else (x['difficulty'] * x['std_time'] * x['quality']), axis=1)
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
                supabase.table("messages").insert({"username": user, "content": txt, "created_at": str(datetime.datetime.now())}).execute()
                st.rerun()
    msgs = run_query("messages")
    if not msgs.empty:
        msgs = msgs.sort_values("created_at", ascending=False).head(50)
        for _, m in msgs.iterrows():
            if m['username'] == "__NOTICE__": continue
            with st.chat_message("user" if m['username']==user else "assistant"):
                st.write(f"**{m['username']}**: {m['content']}")
                st.caption(f"{m['created_at']}")

# --- 4. 风云榜 (全功能恢复) ---
elif nav == "🏆 风云榜":
    st.header("🏆 风云榜 (Live Leaderboard)")
    
    users = run_query("users")
    if not users.empty:
        members = users[users['role'] != 'admin']['username'].tolist()
        
        leader_data = []
        for m in members:
            val_7 = calculate_net_yvp(m, 7)
            val_30 = calculate_net_yvp(m, 30)
            val_total = calculate_net_yvp(m)
            leader_data.append({
                "成员": m,
                "📅 7天净值": val_7,
                "🗓️ 30天净值": val_30,
                "💰 总净资产": val_total
            })
        
        df_leader = pd.DataFrame(leader_data).sort_values("💰 总净资产", ascending=False)
        st.dataframe(df_leader, use_container_width=True, hide_index=True)
        
        if not df_leader.empty:
            top1 = df_leader.iloc[0]
            st.balloons()
            st.success(f"👑 **当前帝国首富：{top1['成员']}** (总资产 {top1['💰 总净资产']})")
            
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
                else: st.warning("无数据")

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
            else: diff = c2.number_input("难度", 1.0); stdt = c2.number_input("工时", 1.0)
            ttype = c2.radio("模式", ["公共任务池", "指派成员"], key="pub_type")
            assign = "待定"
            if ttype == "指派成员":
                udf = run_query("users")
                assign = st.selectbox("人员", udf['username'].tolist() if not udf.empty else [], key="pub_ass")
            if st.button("🚀 确认发布", type="primary", key="pub_btn"):
                if sel_batt_id:
                    supabase.table("tasks").insert({"title": t_name, "description": t_desc, "difficulty": diff, "std_time": stdt, "status": "待领取" if ttype=="公共任务池" else "进行中", "assignee": assign, "deadline": None if no_d else str(d_inp), "type": ttype, "battlefield_id": int(sel_batt_id), "is_rnd": is_rnd_task}).execute()
                    show_success_modal("发布成功")

        with tabs[3]: # 全量管理
            st.subheader("🛠️ 精准修正")
            tdf = run_query("tasks"); udf = run_query("users")
            cf1, cf2 = st.columns(2)
            user_list = ["全部"] + (list(udf['username'].unique()) if not udf.empty else [])
            fu = cf1.selectbox("筛选人员", user_list, key="mng_u")
            sk = cf2.text_input("搜标题", key="mng_k")
            fil = tdf.copy()
            if not fil.empty:
                if fu != "全部": fil = fil[fil['assignee'] == fu]
                if sk: fil = fil[fil['title'].str.contains(sk, case=False, na=False)]
            if not fil.empty:
                tid = st.selectbox("选择任务", fil['id'], format_func=lambda x: f"ID:{x}|{fil[fil['id']==x]['title'].values[0]}", key="mng_sel")
                tar = fil[fil['id']==tid].iloc[0]
                with st.container(border=True):
                    new_title = st.text_input("标题", tar['title'], key=f"et_{tid}")
                    curr_is_rnd = tar.get('is_rnd', False)
                    edit_is_rnd = st.checkbox("🟣 产品研发任务", value=curr_is_rnd, key=f"e_rnd_{tid}")
                    if edit_is_rnd: new_diff=0.0; new_stdt=0.0
                    else: new_diff = st.number_input("难度", value=float(tar['difficulty']), key=f"ed_{tid}"); new_stdt = st.number_input("工时", value=float(tar['std_time']), key=f"est_{tid}")
                    new_qual = st.number_input("质量", value=float(tar['quality']), key=f"eq_{tid}")
                    new_status = st.selectbox("状态", ["待领取", "进行中", "待验收", "完成", "返工"], index=["待领取", "进行中", "待验收", "完成", "返工"].index(tar['status']), key=f"es_{tid}")
                    if st.button("💾 保存", key=f"eb_{tid}"):
                        supabase.table("tasks").update({"title": new_title, "difficulty": new_diff, "std_time": new_stdt, "quality": new_qual, "status": new_status, "is_rnd": edit_is_rnd}).eq("id", int(tid)).execute()
                        show_success_modal("保存成功")
                    with st.popover("🗑️ 删除任务"):
                        if st.button("确认删除", key=f"btn_del_task_{tid}", type="primary"):
                            supabase.table("tasks").delete().eq("id", int(tid)).execute()
                            show_success_modal("删除成功")

        with tabs[4]: # 奖惩管理 (恢复增删改查)
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
                            supabase.table("penalties").delete().eq("id", int(p['id'])).execute()
                            st.rerun()

            with c_r:
                st.markdown("#### 🎁 奖励赏赐")
                target_r = st.selectbox("赏赐成员", members, key="rew_u")
                amt_r = st.number_input("奖励YVP", min_value=1.0, key="rew_a")
                reason_r = st.text_input("理由", key="rew_re")
                if st.button("🎁 赏赐", type="primary", key="btn_rew"):
                    supabase.table("rewards").insert({"username": target_r, "amount": amt_r, "reason": reason_r}).execute()
                    show_success_modal(f"已赏赐")
                st.caption("最近记录 (可撤销)")
                rews = run_query("rewards")
                if not rews.empty:
                    for i, r in rews.sort_values('created_at', ascending=False).head(5).iterrows():
                        c1, c2 = st.columns([4,1])
                        c1.write(f"{r['username']} (+{r['amount']})")
                        if c2.button("🗑️", key=f"del_rew_{r['id']}"):
                            supabase.table("rewards").delete().eq("id", int(r['id'])).execute()
                            st.rerun()

            st.divider(); st.markdown("#### 👥 成员管理")
            if not udf.empty:
                for i, m in udf[udf['role']!='admin'].iterrows():
                    with st.container(border=True):
                        c_n, c_p, c_d = st.columns([2,2,1])
                        c_n.write(f"**{m['username']}**")
                        n_pass = c_p.text_input("重置密码", key=f"rp_{m['username']}")
                        if c_p.button("重置", key=f"btn_rp_{m['username']}"):
                            supabase.table("users").update({"password": n_pass}).eq("username", m['username']).execute(); st.toast("密码已改")
                        with c_d.popover("驱逐"):
                            if st.button("确认注销", key=f"del_{m['username']}"):
                                supabase.table("users").delete().eq("username", m['username']).execute(); st.rerun()

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

        with tabs[7]: # 备份与恢复 (恢复上传功能)
            st.subheader("💾 备份与恢复")
            d1=run_query("users"); d2=run_query("tasks"); d3=run_query("penalties"); d4=run_query("messages"); d5=run_query("rewards")
            buf = io.StringIO()
            buf.write("===USERS===\n"); d1.to_csv(buf, index=False)
            buf.write("\n===TASKS===\n"); d2.to_csv(buf, index=False)
            buf.write("\n===PENALTIES===\n"); d3.to_csv(buf, index=False)
            buf.write("\n===MESSAGES===\n"); d4.to_csv(buf, index=False)
            buf.write("\n===REWARDS===\n"); d5.to_csv(buf, index=False)
            st.download_button("📥 下载全量备份 (Backup)", buf.getvalue(), f"backup_{datetime.date.today()}.txt")
            st.divider()
            upf = st.file_uploader("📤 上传备份文件进行恢复 (慎用！覆盖当前数据)", type=['txt'], key="up_f")
            if upf:
                if st.button("🚨 确认覆盖恢复", type="primary"):
                    try:
                        content = upf.getvalue().decode("utf-8")
                        s_u = content.split("===USERS===\n")[1].split("===TASKS===")[0].strip()
                        s_t = content.split("===TASKS===\n")[1].split("===PENALTIES===")[0].strip()
                        s_p = content.split("===PENALTIES===\n")[1].split("===MESSAGES===")[0].strip()
                        s_m = content.split("===MESSAGES===\n")[1].split("===REWARDS===")[0].strip()
                        s_r = content.split("===REWARDS===\n")[1].strip()
                        supabase.table("users").delete().neq("username", "_").execute()
                        supabase.table("tasks").delete().neq("id", -1).execute()
                        supabase.table("penalties").delete().neq("id", -1).execute()
                        supabase.table("messages").delete().neq("id", -1).execute()
                        supabase.table("rewards").delete().neq("id", -1).execute()
                        if s_u: supabase.table("users").insert(pd.read_csv(io.StringIO(s_u)).to_dict('records')).execute()
                        if s_t: supabase.table("tasks").insert(pd.read_csv(io.StringIO(s_t)).to_dict('records')).execute()
                        if s_p: supabase.table("penalties").insert(pd.read_csv(io.StringIO(s_p)).to_dict('records')).execute()
                        if s_m: supabase.table("messages").insert(pd.read_csv(io.StringIO(s_m)).to_dict('records')).execute()
                        if s_r: supabase.table("rewards").insert(pd.read_csv(io.StringIO(s_r)).to_dict('records')).execute()
                        st.success("✅ 恢复完成！"); time.sleep(1); st.rerun()
                    except Exception as e: st.error(f"恢复失败: {e}")

    else: # 成员界面
        st.header("⚔️ 我的战场")
        tdf = run_query("tasks")
        batts = run_query("battlefields")
        camps = run_query("campaigns")
        
        def get_task_label(bid, is_rnd=False):
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

        if not tdf.empty and 'status' in tdf.columns:
            my = tdf[(tdf['assignee']==user) & (tdf['status'].isin(['进行中', '返工']))].copy()
            my['deadline_dt'] = pd.to_datetime(my['deadline'], errors='coerce')
            my = my.sort_values(by='deadline_dt', ascending=True, na_position='last')
            for i, r in my.iterrows():
                with st.container(border=True):
                    st.markdown(get_task_label(r.get('battlefield_id'), r.get('is_rnd')), unsafe_allow_html=True)
                    prefix = "🔴 [需返工] " if r['status'] == '返工' else ""
                    st.markdown(f"**{prefix}{r['title']}**")
                    d_val = r['deadline']; d_show = format_deadline(d_val)
                    c_d1, c_d2, c_d3 = st.columns(3)
                    if r.get('is_rnd'):
                        c_d1.markdown("⚙️ 难度: N/A"); c_d2.markdown("⏱️ 工时: N/A")
                    else:
                        c_d1.markdown(f"⚙️ 难度: {r['difficulty']}"); c_d2.markdown(f"⏱️ 工时: {r['std_time']}")
                    c_d3.markdown(f"📅 {d_show}")
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
