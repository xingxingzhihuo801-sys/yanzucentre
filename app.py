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
    page_title="颜祖美学·执行中枢 V27.2",
    page_icon="🏛️",
    layout="wide",
    initial_sidebar_state="collapsed"
)

st.markdown("""
    <style>
        #MainMenu {visibility: hidden;}
        header {visibility: hidden;}
        footer {visibility: hidden;}
        .stDeployButton {display:none;}
        div[data-testid="stToolbar"] {visibility: hidden;}
        div[data-testid="stDecoration"] {visibility: hidden;}
        div[data-testid="stStatusWidget"] {visibility: hidden;}
        div[data-testid="stRadio"] > div {
            flex-direction: row;
            justify-content: center;
            background-color: #f8f9fa;
            padding: 10px;
            border-radius: 8px;
            border: 1px solid #dee2e6;
        }
        .scrolling-text {
            width: 100%;
            background-color: #fff3cd;
            color: #856404;
            padding: 10px;
            text-align: center;
            font-weight: bold;
            border-bottom: 1px solid #ffeeba;
            margin-bottom: 10px;
        }
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
cookie_manager = stx.CookieManager(key="yanzu_v27_2_dialog_mgr")

# --- 4. 核心工具函数 ---
@st.cache_data(ttl=3)
def run_query(table_name):
    try:
        response = supabase.table(table_name).select("*").execute()
        df = pd.DataFrame(response.data)
        for col in ['created_at', 'deadline', 'completed_at', 'occurred_at']:
            if col in df.columns:
                df[col] = pd.to_datetime(df[col], errors='coerce').dt.date
        return df
    except:
        return pd.DataFrame()

def get_announcement():
    try:
        res = supabase.table("messages").select("content").eq("username", "__NOTICE__").order("created_at", desc=True).limit(1).execute()
        return res.data[0]['content'] if res.data else "欢迎来到颜祖美学执行中枢！"
    except:
        return "公告加载中..."

def update_announcement(text):
    supabase.table("messages").delete().eq("username", "__NOTICE__").execute()
    supabase.table("messages").insert({"username": "__NOTICE__", "content": text, "created_at": str(datetime.datetime.now())}).execute()

def calculate_net_yvp(username, days_lookback=None):
    users = run_query("users")
    if not users.empty:
        user_row = users[users['username']==username]
        if not user_row.empty and user_row.iloc[0]['role'] == 'admin':
            return 0.0

    tasks = run_query("tasks")
    gross = 0.0
    if not tasks.empty:
        my_done = tasks[(tasks['assignee'] == username) & (tasks['status'] == '完成')].copy()
        if not my_done.empty:
            my_done['val'] = my_done['difficulty'] * my_done['std_time'] * my_done['quality']
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
                w_start = pen['occurred_at'] - pd.Timedelta(days=7)
                if not tasks.empty:
                    base_tasks = tasks[(tasks['assignee'] == username) & (tasks['status'] == '完成')].copy()
                    if not base_tasks.empty:
                        base_tasks['val'] = base_tasks['difficulty'] * base_tasks['std_time'] * base_tasks['quality']
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
    members = users[users['role'] != 'admin']['username'].tolist()
    stats_data = []
    tasks = run_query("tasks"); pens = run_query("penalties"); rews = run_query("rewards")
    ts_start = pd.Timestamp(start_date)
    ts_end = pd.Timestamp(end_date) + pd.Timedelta(days=1) - pd.Timedelta(seconds=1)

    for m in members:
        gross = 0.0
        if not tasks.empty:
            m_tasks = tasks[(tasks['assignee'] == m) & (tasks['status'] == '完成')].copy()
            if not m_tasks.empty:
                m_tasks['completed_at'] = pd.to_datetime(m_tasks['completed_at'])
                in_range = m_tasks[(m_tasks['completed_at'] >= ts_start) & (m_tasks['completed_at'] <= ts_end)]
                gross = (in_range['difficulty'] * in_range['std_time'] * in_range['quality']).sum()
        fine = 0.0
        if not pens.empty:
            m_pens = pens[(pens['username'] == m)].copy()
            if not m_pens.empty:
                m_pens['occurred_at'] = pd.to_datetime(m_pens['occurred_at'])
                in_range_pens = m_pens[(m_pens['occurred_at'] >= ts_start) & (m_pens['occurred_at'] <= ts_end)]
                for _, p in in_range_pens.iterrows():
                    w_start = p['occurred_at'] - pd.Timedelta(days=7)
                    if not tasks.empty:
                        all_m_tasks = tasks[(tasks['assignee'] == m) & (tasks['status'] == '完成')].copy()
                        if not all_m_tasks.empty:
                            all_m_tasks['completed_at'] = pd.to_datetime(all_m_tasks['completed_at'])
                            all_m_tasks['val'] = all_m_tasks['difficulty'] * all_m_tasks['std_time'] * all_m_tasks['quality']
                            w_tasks = all_m_tasks[(all_m_tasks['completed_at'] >= w_start) & (all_m_tasks['completed_at'] <= p['occurred_at'])]
                            fine += w_tasks['val'].sum() * 0.2
        reward_val = 0.0
        if not rews.empty:
            m_rews = rews[rews['username'] == m].copy()
            if not m_rews.empty:
                m_rews['created_at'] = pd.to_datetime(m_rews['created_at'])
                in_range_rews = m_rews[(m_rews['created_at'] >= ts_start) & (m_rews['created_at'] <= ts_end)]
                reward_val = in_range_rews['amount'].sum()
        net = gross - fine + reward_val
        stats_data.append({"成员": m, "任务产出": round(gross, 2), "罚款": round(fine, 2), "奖励": round(reward_val, 2), "💰 应发YVP": round(net, 2)})
    return pd.DataFrame(stats_data).sort_values("💰 应发YVP", ascending=False)

def format_deadline(d_val):
    if pd.isna(d_val) or str(d_val) in ['NaT', 'None', '']: return "♾️ 无期限"
    return str(d_val)

def show_task_history(username, role):
    st.divider()
    st.subheader("📜 任务历史档案")
    df = run_query("tasks")
    if df.empty:
        st.info("暂无数据")
        return
    my_history = df[(df['assignee'] == username) & (df['status'] == '完成')].copy()
    if my_history.empty:
        st.info("暂无已完成的任务记录")
    else:
        my_history['completed_at'] = pd.to_datetime(my_history['completed_at'])
        my_history['Month'] = my_history['completed_at'].dt.strftime('%Y-%m')
        c_search, c_filter = st.columns(2)
        search_kw = c_search.text_input("🔍 搜索任务标题", key=f"hist_search_{username}")
        month_list = ["全部"] + sorted(my_history['Month'].unique().tolist(), reverse=True)
        month_sel = c_filter.selectbox("🗓️ 按月份筛选", month_list, key=f"hist_filter_{username}")
        filtered_df = my_history.copy()
        if month_sel != "全部": filtered_df = filtered_df[filtered_df['Month'] == month_sel]
        if search_kw: filtered_df = filtered_df[filtered_df['title'].str.contains(search_kw, case=False, na=False)]
        if not filtered_df.empty:
            filtered_df['Deadline'] = filtered_df['deadline'].apply(format_deadline)
            filtered_df['Completed'] = filtered_df['completed_at'].dt.date
            filtered_df['Earned YVP'] = filtered_df['difficulty'] * filtered_df['std_time'] * filtered_df['quality']
            cols_show = ['title', 'Completed', 'difficulty', 'std_time', 'quality', 'Earned YVP', 'feedback']
            st.dataframe(filtered_df[cols_show].sort_values("Completed", ascending=False), use_container_width=True, hide_index=True)
            st.caption(f"共找到 {len(filtered_df)} 条记录")
        else: st.info("未找到符合条件的记录")

# --- 新增：成功弹窗函数 ---
@st.dialog("✅ 系统提示")
def show_success_modal(msg="操作成功！"):
    st.write(msg)
    if st.button("关闭", type="primary"):
        st.rerun()

QUOTES = ["管理者的跃升，是从'对任务负责'到'对目标负责'。", "没有执行力，一切战略都是空谈。", "不要假装努力，结果不会陪你演戏。"]
ENCOURAGEMENTS = ["🔥 哪怕是一颗螺丝钉，也要拧得比别人紧！", "🚀 相信你的能力，这个任务非你莫属！", "💪 干就完了！期待你的完美交付。"]

# --- 5. 鉴权与自动登录 ---
if 'user' not in st.session_state:
    st.session_state.user = None
    st.session_state.role = None
if st.session_state.user is None:
    time.sleep(0.5)
    c_user = cookie_manager.get("yanzu_user")
    c_role = cookie_manager.get("yanzu_role")
    if c_user and c_role:
        st.session_state.user = c_user
        st.session_state.role = c_role
        st.rerun()
if st.session_state.user is None:
    st.title("🏛️ 颜祖美学·执行中枢")
    st.info(f"🔥 {random.choice(QUOTES)}")
    c1, c2 = st.columns(2)
    with c1:
        with st.form("login"):
            st.markdown("### 🔑 登录")
            u = st.text_input("用户名")
            p = st.text_input("密码", type="password")
            if st.form_submit_button("🚀 登录", type="primary"):
                res = supabase.table("users").select("*").eq("username", u).eq("password", p).execute()
                if res.data:
                    st.session_state.user = u
                    st.session_state.role = res.data[0]['role']
                    cookie_manager.set("yanzu_user", u, expires_at=datetime.datetime.now() + datetime.timedelta(days=30))
                    cookie_manager.set("yanzu_role", res.data[0]['role'], expires_at=datetime.datetime.now() + datetime.timedelta(days=30))
                    st.rerun()
                else: st.error("账号或密码错误")
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

ann_text = get_announcement()
st.markdown(f"""<div class="scrolling-text"><marquee scrollamount="6">🔔 公告：{ann_text}</marquee></div>""", unsafe_allow_html=True)
st.title(f"🏛️ 帝国中枢 · {user}")
nav = st.radio("NAV", ["📋 任务大厅", "🗣️ 颜祖广场", "🏆 风云榜", "🏰 个人中心"], horizontal=True, label_visibility="collapsed")
st.divider()

with st.sidebar:
    st.header(f"👤 {user}")
    if role != 'admin':
        yvp_7 = calculate_net_yvp(user, 7)
        yvp_30 = calculate_net_yvp(user, 30)
        yvp_all = calculate_net_yvp(user)
        st.metric("7天净收益", yvp_7)
        st.metric("30天净收益", yvp_30)
        st.metric("总净资产", yvp_all)
    st.divider()
    if st.button("注销退出"):
        cookie_manager.set("yanzu_user", "", expires_at=datetime.datetime.now() - datetime.timedelta(days=1))
        cookie_manager.set("yanzu_role", "", expires_at=datetime.datetime.now() - datetime.timedelta(days=1))
        st.session_state.user = None
        st.session_state.role = None
        st.rerun()

if nav == "📋 任务大厅":
    st.header("🛡️ 任务大厅")
    tdf = run_query("tasks")
    st.subheader("🔥 待抢任务池")
    if not tdf.empty:
        pool = tdf[(tdf['status']=='待领取') & (tdf['type']=='公共任务池')]
        if not pool.empty:
            cols = st.columns(3)
            for i, (idx, row) in enumerate(pool.iterrows()):
                with cols[i % 3]:
                    with st.container(border=True):
                        st.markdown(f"**{row['title']}**")
                        # 细节可见
                        st.write(f"⚙️ **难度**: {row['difficulty']} | ⏱️ **工时**: {row['std_time']}")
                        st.write(f"📅 **截止**: {format_deadline(row.get('deadline'))}")
                        
                        with st.expander("👁️ 查看详情"):
                            st.write(row.get('description', '无详情'))
                        if st.button("⚡️ 抢单", key=f"g_{row['id']}", type="primary"):
                            can_grab = True
                            if role != 'admin':
                                my_ongoing = tdf[(tdf['assignee'] == user) & (tdf['status'] == '进行中') & (tdf['type'] == '公共任务池')]
                                if len(my_ongoing) >= 2: can_grab = False
                            if can_grab:
                                supabase.table("tasks").update({"status": "进行中", "assignee": user}).eq("id", int(row['id'])).execute()
                                show_success_modal("任务抢夺成功！请前往我的战场查看。")
                            else: st.warning("✋ 贪多嚼不烂！您已有 2 个公共任务在进行中。")
    st.divider()
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("🔭 实时动态 (最近35条)")
        active = tdf[tdf['status'].isin(['进行中', '返工', '待验收'])].sort_values("created_at", ascending=False).head(35)
        if not active.empty:
            active['Deadline'] = active['deadline'].apply(format_deadline)
            st.dataframe(active[['title', 'assignee', 'status', 'Deadline']], use_container_width=True, hide_index=True)
    with c2:
        st.subheader("📜 荣誉记录 (最近35条)")
        done = tdf[tdf['status']=='完成'].sort_values('completed_at', ascending=False).head(35)
        if not done.empty:
            done['P'] = done.apply(lambda x: f"D{x['difficulty']}/T{x['std_time']}/Q{x['quality']}", axis=1)
            done['💰 获益'] = done['difficulty'] * done['std_time'] * done['quality']
            st.dataframe(done[['title', 'assignee', 'P', '💰 获益']], use_container_width=True, hide_index=True)

elif nav == "🗣️ 颜祖广场":
    st.header("🗣️ 颜祖广场")
    with st.expander("✍️ 发布寄语"):
        txt = st.text_area("输入内容")
        if st.button("发布"):
            supabase.table("messages").insert({"username": user, "content": txt, "created_at": str(datetime.datetime.now())}).execute()
            st.rerun()
    msgs = run_query("messages")
    if not msgs.empty:
        msgs = msgs[msgs['username'] != '__NOTICE__'].sort_values("created_at", ascending=False).head(50)
        for i, m in msgs.iterrows():
            with st.chat_message("user", avatar="💬"):
                st.write(f"**{m['username']}**: {m['content']}")

elif nav == "🏆 风云榜":
    st.header("🏆 荣誉榜单")
    udf = run_query("users")
    if not udf.empty:
        members = udf[udf['role'] != 'admin']['username'].tolist()
        def get_lb(days):
            data = [{"成员": m, "YVP": calculate_net_yvp(m, days)} for m in members]
            return pd.DataFrame(data).sort_values("YVP", ascending=False)
        t1, t2, t3 = st.tabs(["📅 过去7天", "🗓️ 过去30天", "🔥 历史总榜"])
        with t1: st.dataframe(get_lb(7), use_container_width=True, hide_index=True)
        with t2: st.dataframe(get_lb(30), use_container_width=True, hide_index=True)
        with t3: st.dataframe(get_lb(None), use_container_width=True, hide_index=True)
    st.divider()
    c_r1, c_r2 = st.columns(2)
    with c_r1:
        st.subheader("🏆 功勋簿 (最近10条)")
        rews = run_query("rewards")
        if not rews.empty:
            rews_show = rews.sort_values("created_at", ascending=False).head(10)
            st.dataframe(rews_show[['username', 'amount', 'reason', 'created_at']], use_container_width=True, hide_index=True)
        else: st.caption("暂无奖励记录")
    with c_r2:
        st.subheader("🚨 警示录 (最近10条)")
        pens = run_query("penalties")
        if not pens.empty:
            pens_show = pens.sort_values("occurred_at", ascending=False).head(10)
            st.dataframe(pens_show[['username', 'reason', 'occurred_at']], use_container_width=True, hide_index=True)
        else: st.caption("全员全勤，继续保持！")

elif nav == "🏰 个人中心":
    if role == 'admin':
        st.header("👑 统帅后台")
        if datetime.date.today().day % 10 == 0:
            st.warning(f"📅 **今日为备份提醒日，请下载全量备份。**")
        tabs = st.tabs(["⚡️ 我的战场", "💰 分润统计", "🚀 发布任务", "🛠️ 全量管理", "🎁 人员与奖惩", "⚖️ 裁决审核", "📢 公告维护", "💾 备份恢复"])
        
        with tabs[0]: 
            st.subheader("⚡️ 快捷派发")
            qc1, qc2 = st.columns([3, 1])
            quick_t = qc1.text_input("内容", key="adm_q_t")
            quick_d = qc2.date_input("截止", value=None, key="adm_q_d")
            if st.button("派发给我", type="primary", key="adm_q_btn"):
                supabase.table("tasks").insert({"title": quick_t, "difficulty": 0, "std_time": 0, "status": "进行中", "assignee": user, "type": "AdminSelf", "deadline": str(quick_d) if quick_d else None}).execute()
                show_success_modal("已添加到您的战场！")
            st.divider()
            st.subheader("🛡️ 进行中")
            tdf = run_query("tasks")
            my_adm = tdf[(tdf['assignee'] == user) & (tdf['status'] == '进行中')]
            for i, r in my_adm.iterrows():
                with st.container(border=True):
                    ic1, ic2 = st.columns([4, 1])
                    with ic1:
                        st.markdown(f"**{r['title']}**")
                        # 细节可见
                        st.write(f"📅 **截止**: {format_deadline(r.get('deadline'))}")
                    if ic2.button("✅ 完成", key=f"fin_{r['id']}"):
                        supabase.table("tasks").update({"status": "完成", "quality": 1.0, "completed_at": str(datetime.date.today()), "feedback": "统帅自结"}).eq("id", int(r['id'])).execute()
                        show_success_modal("任务已归档！")
            show_task_history(user, role)

        with tabs[1]: # 分润
            st.subheader("💰 周期分润统计")
            st.info("含任务产出、罚款扣除及奖励加成。")
            c_d1, c_d2 = st.columns(2)
            d_start = c_d1.date_input("开始日期", value=datetime.date.today().replace(day=1), key="stats_d1")
            d_end = c_d2.date_input("结束日期", value=datetime.date.today(), key="stats_d2")
            if st.button("📊 开始统计", type="primary"):
                if d_start <= d_end:
                    report = calculate_period_stats(d_start, d_end)
                    st.dataframe(report, use_container_width=True, hide_index=True)
                    csv = report.to_csv(index=False).encode('utf-8')
                    st.download_button("📥 下载报表", csv, f"yvp_report_{d_start}_{d_end}.csv", "text/csv")
                else: st.error("日期错误")

        with tabs[2]: # 发布
            c1, c2 = st.columns(2)
            t_name = c1.text_input("任务标题", key="pub_t")
            t_desc = st.text_area("详情", key="pub_desc")
            col_d, col_c = c1.columns([3,2])
            d_inp = col_d.date_input("截止日期", key="pub_d")
            no_d = col_c.checkbox("无截止日期", key="pub_no_d")
            diff = c2.number_input("难度", value=1.0, key="pub_diff")
            stdt = c2.number_input("工时", value=1.0, key="pub_std")
            ttype = c2.radio("模式", ["公共任务池", "指派成员"], key="pub_type")
            assign = "待定"
            if ttype == "指派成员":
                udf = run_query("users")
                assign = st.selectbox("人员", udf['username'].tolist(), key="pub_ass")
            if st.button("🚀 确认发布", type="primary", key="pub_btn"):
                supabase.table("tasks").insert({"title": t_name, "description": t_desc, "difficulty": diff, "std_time": stdt, "status": "待领取" if ttype=="公共任务池" else "进行中", "assignee": assign, "deadline": None if no_d else str(d_inp), "type": ttype}).execute()
                show_success_modal("任务发布成功！")

        with tabs[3]: # 全量管理
            st.subheader("🛠️ 精准修正")
            tdf = run_query("tasks"); udf = run_query("users")
            cf1, cf2 = st.columns(2)
            fu = cf1.selectbox("筛选人员", ["全部"] + list(udf['username'].unique()), key="mng_u")
            sk = cf2.text_input("搜标题", key="mng_k")
            fil = tdf.copy()
            if fu != "全部": fil = fil[fil['assignee'] == fu]
            if sk: fil = fil[fil['title'].str.contains(sk, case=False, na=False)]
            if not fil.empty:
                tid = st.selectbox("选择任务", fil['id'], format_func=lambda x: f"ID:{x}|{fil[fil['id']==x]['title'].values[0]}", key="mng_sel")
                tar = fil[fil['id']==tid].iloc[0]
                with st.container(border=True):
                    supabase.table("tasks").update({
                        "title": st.text_input("标题", tar['title'], key=f"et_{tid}"),
                        "difficulty": st.number_input("难度", value=float(tar['difficulty']), key=f"ed_{tid}"),
                        "quality": st.number_input("质量", value=float(tar['quality']), key=f"eq_{tid}"),
                        "status": st.selectbox("状态", ["待领取", "进行中", "待验收", "完成", "返工"], index=["待领取", "进行中", "待验收", "完成", "返工"].index(tar['status']), key=f"es_{tid}")
                    }).eq("id", int(tid)).execute()
                    if st.button("💾 保存", key=f"eb_{tid}"): st.rerun()

        with tabs[4]: # 🎁 人员与奖惩
            udf = run_query("users")
            members = udf[udf['role']!='admin']['username'].tolist() if not udf.empty else []
            c_p, c_r = st.columns(2)
            with c_p:
                st.markdown("#### 🚨 考勤管理")
                with st.container(border=True):
                    target_p = st.selectbox("缺勤成员", members, key="pen_u")
                    date_p = st.date_input("缺勤日期", value=datetime.date.today(), key="pen_d")
                    if st.button("🔴 记录缺勤", key="btn_pen"):
                        supabase.table("penalties").insert({"username": target_p, "occurred_at": str(date_p), "reason": "缺勤"}).execute()
                        st.error(f"已记录 {target_p} 于 {date_p} 缺勤")
            with c_r:
                st.markdown("#### 🎁 奖励赏赐")
                with st.container(border=True):
                    target_r = st.selectbox("赏赐成员", members, key="rew_u")
                    amt_r = st.number_input("奖励YVP点数", min_value=1.0, step=10.0, key="rew_a")
                    reason_r = st.text_input("奖励理由", placeholder="例：技术攻坚", key="rew_re")
                    if st.button("🎁 确认赏赐", type="primary", key="btn_rew"):
                        supabase.table("rewards").insert({"username": target_r, "amount": amt_r, "reason": reason_r}).execute()
                        show_success_modal(f"已赏赐 {target_r} {amt_r} YVP")
            st.divider()
            st.markdown("#### 📝 奖励记录管理 (可撤销)")
            rews_all = run_query("rewards")
            if not rews_all.empty:
                for i, r in rews_all.sort_values("created_at", ascending=False).iterrows():
                    with st.container(border=True):
                        cr1, cr2, cr3 = st.columns([3,2,1])
                        cr1.write(f"**{r['username']}** : {r['reason']}")
                        cr2.caption(f"+{r['amount']} | {r['created_at']}")
                        if cr3.button("撤销", key=f"del_rew_{r['id']}"):
                            supabase.table("rewards").delete().eq("id", int(r['id'])).execute()
                            st.rerun()
            else: st.info("暂无奖励记录")
            st.divider()
            st.markdown("#### 👥 成员账号管理")
            for i, m in udf[udf['role']!='admin'].iterrows():
                with st.container(border=True):
                    c_n, c_p, c_d = st.columns([2,2,1])
                    c_n.write(f"**{m['username']}**")
                    n_pass = c_p.text_input("重置密码", key=f"rp_{m['username']}")
                    if c_p.button("重置", key=f"btn_rp_{m['username']}"):
                        supabase.table("users").update({"password": n_pass}).eq("username", m['username']).execute(); st.toast("密码已改")
                    with c_d.popover("驱逐"):
                        if st.button("确认注销该成员", key=f"del_{m['username']}"):
                            supabase.table("users").delete().eq("username", m['username']).execute(); st.rerun()

        with tabs[5]: # 裁决
            pend = run_query("tasks")
            pend = pend[pend['status'] == '待验收']
            if not pend.empty:
                sel_p = st.selectbox("待审任务", pend['id'], format_func=lambda x: pend[pend['id']==x]['title'].values[0])
                with st.container(border=True):
                    qual = st.slider("质量评分", 0.0, 3.0, 1.0, 0.1)
                    res = st.selectbox("裁决结果", ["完成", "返工"])
                    fb = st.text_area("御批反馈")
                    if st.button("提交审核"):
                        cat = str(datetime.date.today()) if res=="完成" else None
                        supabase.table("tasks").update({"quality": qual, "status": res, "feedback": fb, "completed_at": cat}).eq("id", int(sel_p)).execute()
                        show_success_modal("裁决已提交！")
            else: st.info("暂无待审任务")

        with tabs[6]: # 公告
            new_ann = st.text_input("输入新公告内容", placeholder=ann_text)
            if st.button("立即发布公告"):
                update_announcement(new_ann); st.success("公告已更新")

        with tabs[7]: # 备份
            d1=run_query("users"); d2=run_query("tasks"); d3=run_query("penalties"); d4=run_query("messages"); d5=run_query("rewards")
            buf = io.StringIO()
            buf.write("===USERS===\n"); d1.to_csv(buf, index=False)
            buf.write("\n===TASKS===\n"); d2.to_csv(buf, index=False)
            buf.write("\n===PENALTIES===\n"); d3.to_csv(buf, index=False)
            buf.write("\n===MESSAGES===\n"); d4.to_csv(buf, index=False)
            buf.write("\n===REWARDS===\n"); d5.to_csv(buf, index=False)
            st.download_button("📥 下载备份", buf.getvalue(), f"backup_{datetime.date.today()}.txt")
            st.divider()
            upf = st.file_uploader("上传备份进行覆盖恢复", type=['txt'], key="up_f")
            if upf:
                if st.button("🚨 确认执行全量恢复", type="primary", key="up_btn"):
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
                        st.success("恢复完成"); time.sleep(1); st.rerun()
                    except: st.error("失败")

    else: # 成员界面
        st.header("⚔️ 我的战场")
        tdf = run_query("tasks")
        my = tdf[(tdf['assignee']==user) & (tdf['status']=='进行中')]
        for i, r in my.iterrows():
            with st.container(border=True):
                st.markdown(f"**{r['title']}**")
                # 细节可见 (成员端)
                st.write(f"⚙️ **难度**: {r['difficulty']} | ⏱️ **工时**: {r['std_time']}")
                st.write(f"📅 **截止**: {format_deadline(r.get('deadline'))}")
                with st.expander("👁️ 查看详情"):
                    st.write(r.get('description', '无详情'))
                if st.button("✅ 交付验收", key=f"dev_{r['id']}", type="primary"):
                    supabase.table("tasks").update({"status": "待验收"}).eq("id", int(r['id'])).execute()
                    show_success_modal("任务已提交验收！")
        show_task_history(user, role)
        st.divider()
        with st.expander("🔐 修改密码"):
            np = st.text_input("新密码", type="password", key="m_p")
            if st.button("确认更改", key="m_p_btn"):
                supabase.table("users").update({"password": np}).eq("username", user).execute()
                st.success("已更新")
