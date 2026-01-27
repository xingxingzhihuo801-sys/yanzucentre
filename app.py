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
    page_title="颜祖美学·执行中枢 V20.0",
    page_icon="🏛️",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# 样式优化
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
    st.error("🚨 数据库连接失败。")
    st.stop()

# --- 3. Cookie 管理 ---
def get_manager():
    return stx.CookieManager(key="yanzu_cookie_handler_v20_0")
cookie_manager = get_manager()

# --- 4. 核心工具 ---
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
        if res.data: return res.data[0]['content']
        return "欢迎来到颜祖美学执行中枢！"
    except:
        return "公告加载中..."

def update_announcement(text):
    supabase.table("messages").delete().eq("username", "__NOTICE__").execute()
    supabase.table("messages").insert({"username": "__NOTICE__", "content": text, "created_at": str(datetime.datetime.now())}).execute()

def calculate_net_yvp(username, days_lookback=None):
    if check_is_admin(username): return 0.0
    tasks = run_query("tasks")
    if tasks.empty: return 0.0
    my_done = tasks[(tasks['assignee'] == username) & (tasks['status'] == '完成')].copy()
    if my_done.empty: return 0.0
    my_done['val'] = my_done['difficulty'] * my_done['std_time'] * my_done['quality']
    my_done['completed_at'] = pd.to_datetime(my_done['completed_at'])
    view_df = my_done.copy()
    if days_lookback:
        cutoff = pd.Timestamp.now() - pd.Timedelta(days=days_lookback)
        view_df = view_df[view_df['completed_at'] >= cutoff]
    gross = view_df['val'].sum()
    total_fine = 0.0
    if days_lookback is None: 
        penalties = run_query("penalties")
        if not penalties.empty:
            my_pens = penalties[penalties['username'] == username].copy()
            if not my_pens.empty:
                my_pens['occurred_at'] = pd.to_datetime(my_pens['occurred_at'])
                for _, pen in my_pens.iterrows():
                    w_start = pen['occurred_at'] - pd.Timedelta(days=7)
                    w_tasks = my_done[(my_done['completed_at'] >= w_start) & (my_done['completed_at'] <= pen['occurred_at'])]
                    total_fine += w_tasks['val'].sum() * 0.2
    return round(gross, 2) if days_lookback else round(gross - total_fine, 2)

def check_is_admin(username):
    users = run_query("users")
    if not users.empty:
        u = users[users['username']==username]
        if not u.empty and u.iloc[0]['role'] == 'admin': return True
    return False

def format_deadline(d_val):
    if pd.isna(d_val) or str(d_val) == 'NaT' or not d_val:
        return "♾️ 无期限"
    return f"{d_val}"

QUOTES = ["管理者的跃升，是从'对任务负责'到'对目标负责'。", "没有执行力，一切战略都是空谈。", "不要假装努力，结果不会陪你演戏。"]
ENCOURAGEMENTS = ["🔥 哪怕是一颗螺丝钉，也要拧得比别人紧！", "🚀 相信你的能力，这个任务非你莫属！", "💪 干就完了！期待你的完美交付。"]

# --- 5. 鉴权逻辑 ---
if 'user' not in st.session_state:
    st.session_state.user = None
    st.session_state.role = None
if st.session_state.user is None:
    time.sleep(0.1) 
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
            u = st.text_input("用户名")
            p = st.text_input("密码", type="password")
            if st.form_submit_button("🚀 登录", type="primary"):
                res = supabase.table("users").select("*").eq("username", u).eq("password", p).execute()
                if res.data:
                    role = res.data[0]['role']
                    st.session_state.user = u
                    st.session_state.role = role
                    cookie_manager.set("yanzu_user", u, expires_at=datetime.datetime.now() + datetime.timedelta(days=30))
                    cookie_manager.set("yanzu_role", role, expires_at=datetime.datetime.now() + datetime.timedelta(days=30))
                    st.success("欢迎回来")
                    time.sleep(0.5)
                    st.rerun()
                else:
                    st.error("密码错误")
    with c2:
        with st.expander("新兵注册"):
            nu = st.text_input("用户名")
            np = st.text_input("密码", type="password")
            if st.button("注册"):
                try:
                    supabase.table("users").insert({"username": nu, "password": np, "role": "member"}).execute()
                    st.success("注册成功！")
                except:
                    st.warning("用户已存在")
    st.stop()

# --- 6. 登录后界面 ---
user = st.session_state.user
role = st.session_state.role
announcement = get_announcement()
st.markdown(f"""<div class="scrolling-text"><marquee scrollamount="6" direction="left">🔔 公告：{announcement}</marquee></div>""", unsafe_allow_html=True)
st.title(f"🏛️ 颜祖帝国 ({user})")
nav_options = ["📋 任务大厅", "🗣️ 颜祖广场", "🏆 风云榜", "🏰 个人中心"]
nav = st.radio("NAV", nav_options, horizontal=True, label_visibility="collapsed")
st.divider()

# 侧边栏
with st.sidebar:
    st.header(f"👤 {user}")
    st.caption("👑 最高指挥官" if role == 'admin' else "⚔️ 核心成员")
    if role != 'admin':
        yvp_7 = calculate_net_yvp(user, 7)
        yvp_all = calculate_net_yvp(user, None)
        st.metric("本周产出", yvp_7)
        st.metric("总净资产", yvp_all)
    st.divider()
    if st.button("注销退出"):
        cookie_manager.delete("yanzu_user")
        cookie_manager.delete("yanzu_role")
        st.session_state.user = None
        st.session_state.role = None
        time.sleep(0.5)
        st.rerun()

# ================= 📋 任务大厅 =================
if nav == "📋 任务大厅":
    st.header("🛡️ 任务大厅")
    t_df = run_query("tasks")
    st.subheader("🔥 待抢任务")
    if not t_df.empty:
        pool = t_df[(t_df['status']=='待领取') & (t_df['type']=='公共任务池')]
        if not pool.empty:
            cols = st.columns(3)
            for i, (idx, row) in enumerate(pool.iterrows()):
                with cols[i % 3]:
                    with st.container(border=True):
                        st.markdown(f"**{row['title']}**")
                        st.caption(f"📅 截止: **{format_deadline(row.get('deadline'))}**")
                        st.markdown(f"⚙️ 难度: **{row['difficulty']}** | ⏱️ 工时: **{row['std_time']}**")
                        if st.button("⚡️ 抢单", key=f"grab_{row['id']}", type="primary"):
                            supabase.table("tasks").update({"status": "进行中", "assignee": user}).eq("id", int(row['id'])).execute()
                            st.toast(random.choice(ENCOURAGEMENTS), icon="🔥")
                            time.sleep(1)
                            st.rerun()
        else: st.info("公共池空闲中")
    st.divider()
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("🔭 全军动态")
        if not t_df.empty:
            active = t_df[t_df['status'].isin(['进行中', '返工', '待验收'])]
            if not active.empty:
                active_display = active.copy()
                active_display['Deadline'] = active_display['deadline'].apply(format_deadline)
                st.dataframe(active_display[['title', 'assignee', 'status', 'Deadline']], use_container_width=True, hide_index=True)
            else: st.caption("全军休整中")
    with c2:
        st.subheader("📜 荣誉榜 (Top 20)")
        if not t_df.empty:
            done = t_df[t_df['status']=='完成'].sort_values('completed_at', ascending=False).head(20)
            if not done.empty:
                done_display = done.copy()
                done_display['Params'] = done_display.apply(lambda x: f"D{x['difficulty']} / T{x['std_time']} / Q{x['quality']}", axis=1)
                st.dataframe(done_display[['title', 'assignee', 'Params']], use_container_width=True, hide_index=True)

# ================= 🗣️ 颜祖广场 =================
elif nav == "🗣️ 颜祖广场":
    st.header("🗣️ 颜祖广场")
    with st.expander("✍️ 发布新寄语"):
        txt = st.text_area("输入内容...")
        if st.button("发布"):
            if txt:
                supabase.table("messages").insert({"username": user, "content": txt, "created_at": str(datetime.datetime.now())}).execute()
                st.success("已发布"); st.rerun()
    msgs = run_query("messages")
    msgs = msgs[msgs['username'] != '__NOTICE__']
    if not msgs.empty:
        msgs = msgs.sort_values("created_at", ascending=False)
        for i, m in msgs.iterrows():
            with st.chat_message("user", avatar="💬"):
                st.write(f"**{m['username']}**: {m['content']}")
                st.caption(f"{m['created_at']}")

# ================= 🏆 风云榜 =================
elif nav == "🏆 风云榜":
    st.header("🏆 颜祖富豪榜")
    u_df = run_query("users")
    if not u_df.empty:
        mems = u_df[u_df['role'] != 'admin']['username'].tolist()
        def get_rank(lookback):
            d = []
            for m in mems:
                val = calculate_net_yvp(m, lookback)
                d.append({"成员": m, "YVP": val})
            return pd.DataFrame(d).sort_values("YVP", ascending=False)
        t1, t2, t3 = st.tabs(["📅 7天", "🗓️ 30天", "🔥 总榜"])
        with t1: st.dataframe(get_rank(7), use_container_width=True, hide_index=True)
        with t2: st.dataframe(get_rank(30), use_container_width=True, hide_index=True)
        with t3: st.dataframe(get_rank(None), use_container_width=True, hide_index=True)

# ================= 🏰 个人中心 =================
elif nav == "🏰 个人中心":
    if role == 'admin':
        st.header("👑 统帅控制台")
        adm_tabs = st.tabs(["⚡️ 随手记", "🚀 发布", "🛠️ 管理(全权版)", "⚖️ 裁决", "📢 公告", "👥 成员", "💾 备份"])
        
        with adm_tabs[0]: 
            st.info("⚡️ 随手记任务派给自己，不计分，完成后直接归档。")
            q_title = st.text_input("任务内容", key="q_title")
            q_desc = st.text_area("备注", key="q_desc")
            if st.button("⚡️ 立即创建", type="primary"):
                supabase.table("tasks").insert({"title": q_title, "description": q_desc, "difficulty": 0, "std_time": 0, "status": "进行中", "assignee": user, "type": "AdminSelf", "feedback": "统帅自派"}).execute()
                st.success("已创建")
                
        with adm_tabs[1]: # 发布
            c1, c2 = st.columns(2)
            title = c1.text_input("任务名称")
            col_date, col_check = c1.columns([3, 2])
            dead_input = col_date.date_input("截止日期")
            no_deadline = col_check.checkbox("♾️ 无截止时间")
            final_deadline = None if no_deadline else str(dead_input)
            desc = st.text_area("详情")
            diff = c2.number_input("难度", min_value=0.0, max_value=99.0, value=1.0, step=0.1)
            stdt = c2.number_input("工时", min_value=0.0, max_value=99.0, value=1.0, step=0.5)
            ttype = c2.radio("类型", ["公共任务池", "指定指派"], horizontal=True)
            assignee = "待定"
            udf = run_query("users")
            if ttype == "指定指派" and not udf.empty:
                assignee = st.selectbox("指派给", udf['username'].tolist())
            with st.popover("🚀 确认发布"):
                if st.button("确定发布", type="primary"):
                    s = "待领取" if ttype=="公共任务池" else "进行中"
                    a = assignee if ttype=="指定指派" else "待定"
                    supabase.table("tasks").insert({"title": title, "description": desc, "difficulty": diff, "std_time": stdt, "status": s, "assignee": a, "deadline": final_deadline, "type": ttype, "feedback": ""}).execute()
                    st.success("已发布")

        with adm_tabs[2]: # 管理(全权版)
            st.subheader("🛠️ 全局任务修正与精准检索")
            tdf = run_query("tasks")
            udf = run_query("users")
            if not tdf.empty:
                c_filter1, c_filter2 = st.columns(2)
                # 微调点：增加执行人检索
                user_list = ["全部"] + list(udf['username'].unique())
                filter_user = c_filter1.selectbox("🔍 按执行人过滤", user_list)
                search_term = c_filter2.text_input("🔍 搜索标题关键词")
                
                # 执行过滤逻辑
                filtered_tdf = tdf.copy()
                if filter_user != "全部":
                    filtered_tdf = filtered_tdf[filtered_tdf['assignee'] == filter_user]
                if search_term:
                    filtered_tdf = filtered_tdf[filtered_tdf['title'].str.contains(search_term, na=False, case=False)]
                
                if not filtered_tdf.empty:
                    tid = st.selectbox("🎯 选择具体任务", filtered_tdf['id'], format_func=lambda x: f"ID:{x} | {filtered_tdf[filtered_tdf['id']==x]['title'].values[0]} ({filtered_tdf[filtered_tdf['id']==x]['assignee'].values[0]})")
                    curr = filtered_tdf[filtered_tdf['id']==tid].iloc[0]
                    
                    with st.container(border=True):
                        st.markdown(f"#### 正在修改任务 ID: {tid}")
                        # 微调点：开放所有数据编辑
                        e_title = st.text_input("任务标题", curr['title'])
                        e_desc = st.text_area("详细说明", curr.get('description', ''))
                        
                        col_e1, col_e2, col_e3 = st.columns(3)
                        e_diff = col_e1.number_input("难度系数 (D)", value=float(curr['difficulty']), min_value=0.0, max_value=99.0)
                        e_stdt = col_e2.number_input("预计工时 (T)", value=float(curr['std_time']), min_value=0.0, max_value=99.0)
                        e_qual = col_e3.number_input("质量系数 (Q)", value=float(curr['quality']), min_value=0.0, max_value=3.0)
                        
                        col_e4, col_e5, col_e6 = st.columns(3)
                        status_opts = ["待领取", "进行中", "待验收", "完成", "返工"]
                        e_status = col_e4.selectbox("任务状态", status_opts, index=status_opts.index(curr['status']) if curr['status'] in status_opts else 0)
                        e_assignee = col_e5.selectbox("执行人归属", udf['username'].tolist(), index=udf['username'].tolist().index(curr['assignee']) if curr['assignee'] in udf['username'].tolist() else 0)
                        
                        # 截止日期编辑
                        curr_dead = curr.get('deadline')
                        has_dead = not (pd.isna(curr_dead) or str(curr_dead) == 'None')
                        e_no_dead = col_e6.checkbox("无截止日期", value=not has_dead)
                        e_dead = col_e6.date_input("修改截止日期", value=curr_dead if has_dead else datetime.date.today())
                        
                        e_fb = st.text_area("反馈/御批内容", curr.get('feedback', ''))
                        
                        c_save, c_del = st.columns([1,4])
                        if c_save.button("💾 确认全权修改"):
                            final_dead = None if e_no_dead else str(e_dead)
                            supabase.table("tasks").update({
                                "title": e_title, "description": e_desc, "difficulty": e_diff, 
                                "std_time": e_stdt, "quality": e_qual, "status": e_status, 
                                "assignee": e_assignee, "deadline": final_dead, "feedback": e_fb,
                                "completed_at": str(datetime.date.today()) if e_status == "完成" else None
                            }).eq("id", int(tid)).execute()
                            st.success("数据已全量更新！"); st.rerun()
                        with c_del.popover("🗑️ 彻底删除"):
                            if st.button("确认删除该记录", type="primary"):
                                supabase.table("tasks").delete().eq("id", int(tid)).execute(); st.rerun()
                else: st.info("未找到匹配任务")

        with adm_tabs[3]: # 裁决
            pend = run_query("tasks")
            if not pend.empty: pend = pend[pend['status']=='待验收']
            if not pend.empty:
                pid = st.selectbox("待审", pend['id'], format_func=lambda x: f"{pend[pend['id']==x]['title'].values[0]}")
                pinfo = pend[pend['id']==pid].iloc[0]
                st.caption(f"执行: {pinfo['assignee']} | D:{pinfo['difficulty']} | T:{pinfo['std_time']}")
                with st.container(border=True):
                    q = st.slider("质量", 0.0, 3.0, 1.0, 0.1)
                    fb = st.text_area("御批")
                    res = st.selectbox("结果", ["完成", "返工"])
                    if st.button("提交裁决"):
                        cat = str(datetime.date.today()) if res=="完成" else None
                        supabase.table("tasks").update({"quality": q, "feedback": fb, "status": res, "completed_at": cat}).eq("id", int(pid)).execute()
                        st.success("生效"); st.rerun()
            else: st.info("无待审")
        
        with adm_tabs[4]: # 公告
            st.subheader("📢 滚动公告")
            update_n = st.text_input("新内容", placeholder=get_announcement())
            if st.button("更新"): update_announcement(update_n); st.success("OK"); st.rerun()
        with adm_tabs[5]: # 成员
            udf = run_query("users")
            with st.expander("🚨 记过"):
                target = st.selectbox("违规人", udf[udf['role']!='admin']['username'].tolist() if not udf.empty else [])
                if st.button("记缺勤"): supabase.table("penalties").insert({"username": target, "occurred_at": str(datetime.date.today()), "reason": "缺勤"}).execute(); st.success("OK")
            for i, m in udf[udf['role']!='admin'].iterrows():
                with st.container(border=True):
                    c1, c2, c3 = st.columns([2,2,1])
                    c1.write(f"**{m['username']}**")
                    np = c2.text_input(f"改密", key=f"p_{m['username']}")
                    if c2.button("重置", key=f"r{m['username']}"):
                        if np: supabase.table("users").update({"password": np}).eq("username", m['username']).execute(); st.toast("OK")
                    with c3.popover("驱逐"):
                        if st.button("确认", key=f"d{m['username']}", type="primary"):
                            supabase.table("users").delete().eq("username", m['username']).execute(); st.rerun()
        with adm_tabs[6]: # 备份
            d1 = run_query("users"); d2 = run_query("tasks"); d3 = run_query("penalties"); d4 = run_query("messages")
            b = io.StringIO()
            b.write("===USERS===\n"); d1.to_csv(b, index=False)
            b.write("\n===TASKS===\n"); d2.to_csv(b, index=False)
            b.write("\n===PENALTIES===\n"); d3.to_csv(b, index=False)
            b.write("\n===MESSAGES===\n"); d4.to_csv(b, index=False)
            st.download_button("📥 下载备份", b.getvalue(), "backup.txt")

    else: # 普通成员视图
        st.header("⚔️ 我的战场")
        tdf = run_query("tasks")
        if not tdf.empty:
            today_done = tdf[(tdf['assignee']==user) & (tdf['status']=='完成') & (tdf['completed_at'] == datetime.date.today())]
            if not today_done.empty: st.info(f"🔔 您有 {len(today_done)} 个任务今日已被验收评分！")
            my = tdf[(tdf['assignee']==user) & (tdf['status']=='进行中')]
            if not my.empty:
                for i, r in my.iterrows():
                    with st.container(border=True):
                        st.markdown(f"**{r['title']}**")
                        st.caption(f"📅 截止: **{format_deadline(r.get('deadline'))}**")
                        st.caption(f"⚙️ 难度: {r['difficulty']} | ⏱️ 工时: {r['std_time']}")
                        if st.button("✅ 交付验收", key=f"deliv_{r['id']}", type="primary"):
                             supabase.table("tasks").update({"status": "待验收"}).eq("id", int(r['id'])).execute()
                             st.success("已交付"); st.rerun()
            else: st.info("暂无任务")
        st.divider()
        with st.expander("🔐 修改密码"):
            np = st.text_input("新密码", type="password")
            if st.button("修改"): supabase.table("users").update({"password": np}).eq("username", user).execute(); st.success("已更新")
