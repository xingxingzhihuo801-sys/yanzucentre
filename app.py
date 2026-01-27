import streamlit as st
import pandas as pd
import datetime
import time
import io
import random
import extra_streamlit_components as stx
from supabase import create_client, Client

# --- 1. 系统基础配置 ---
st.set_page_config(
    page_title="颜祖美学·执行中枢 V17.0",
    page_icon="🏛️",
    layout="wide",
    initial_sidebar_state="collapsed" # 默认收起侧边栏，因为我们现在用顶部导航
)

# CSS 修复：不再隐藏 Header，防止菜单按钮消失
# 改为仅隐藏右上角的汉堡菜单和页脚，保留核心功能区
st.markdown("""
    <style>
        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}
        /* 优化顶部导航栏样式 */
        div[data-testid="stRadio"] > div {
            flex-direction: row; /* 强制横向排列 */
            justify-content: center; /* 居中 */
            gap: 20px;
            background-color: #f0f2f6;
            padding: 10px;
            border-radius: 10px;
        }
        /* 手机端适配 */
        @media (max-width: 640px) {
            div[data-testid="stRadio"] > div {
                flex-direction: column; /* 手机上竖向防止挤压，或者保持横向但允许滚动 */
                gap: 5px;
            }
        }
    </style>
""", unsafe_allow_html=True)

# --- 2. 数据库连接 ---
try:
    url = st.secrets["supabase"]["url"]
    key = st.secrets["supabase"]["key"]
    supabase: Client = create_client(url, key)
except Exception:
    st.error("🚨 致命错误：数据库连接失败，请检查配置文件。")
    st.stop()

# --- 3. 核心工具函数 ---
@st.cache_data(ttl=5)
def run_query(table_name):
    """通用查表"""
    try:
        response = supabase.table(table_name).select("*").execute()
        df = pd.DataFrame(response.data)
        for col in ['created_at', 'deadline', 'completed_at', 'occurred_at']:
            if col in df.columns:
                df[col] = pd.to_datetime(df[col], errors='coerce').dt.date
        return df
    except:
        return pd.DataFrame()

def calculate_net_yvp(username, days_lookback=None):
    """军规算法"""
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

QUOTES = ["管理者的跃升，是从'对任务负责'到'对目标负责'。", "没有执行力，一切战略都是空谈。", "不要假装努力，结果不会陪你演戏。"]
ENCOURAGEMENTS = ["🔥 哪怕是一颗螺丝钉，也要拧得比别人紧！", "🚀 相信你的能力，这个任务非你莫属！", "💪 干就完了！期待你的完美交付。"]

# --- 4. 登录与状态管理 ---
def get_manager(): return stx.CookieManager()
cookie_manager = get_manager()

if 'user' not in st.session_state:
    time.sleep(0.1) # 等待 Cookie 加载
    cookie_user = cookie_manager.get(cookie="yanzu_user")
    cookie_role = cookie_manager.get(cookie="yanzu_role")
    
    if cookie_user and cookie_role:
        st.session_state.user = cookie_user
        st.session_state.role = cookie_role
        st.rerun()
    
    st.title("🏛️ 颜祖美学·执行中枢")
    st.info(f"🔥 {random.choice(QUOTES)}")
    
    c1, c2 = st.columns(2)
    with c1:
        with st.form("login"):
            u = st.text_input("用户名")
            p = st.text_input("密码", type="password")
            if st.form_submit_button("🚀 登录"):
                res = supabase.table("users").select("*").eq("username", u).eq("password", p).execute()
                if res.data:
                    role = res.data[0]['role']
                    st.session_state.user = u
                    st.session_state.role = role
                    cookie_manager.set("yanzu_user", u, expires_at=datetime.datetime.now() + datetime.timedelta(days=30))
                    cookie_manager.set("yanzu_role", role, expires_at=datetime.datetime.now() + datetime.timedelta(days=30))
                    st.success("登录成功")
                    time.sleep(0.5)
                    st.rerun()
                else:
                    st.error("验证失败")
    with c2:
        with st.expander("新兵注册"):
            nu = st.text_input("用户名")
            np = st.text_input("密码", type="password")
            if st.button("注册"):
                try:
                    supabase.table("users").insert({"username": nu, "password": np, "role": "member"}).execute()
                    st.success("注册成功！请登录。")
                except:
                    st.warning("用户已存在")
    st.stop()

user = st.session_state.user
role = st.session_state.role

# --- 5. 顶部核心导航栏 (关键修复：不再依赖侧边栏) ---
st.title(f"🏛️ 颜祖帝国 ({user})")

# 顶部菜单：所有核心入口直接展示
nav_options = ["📋 任务大厅", "🗣️ 颜祖广场", "🏆 风云榜", "🏰 个人中心"]
# 使用 horizontal=True 让单选按钮变成横向导航条
nav = st.radio("系统导航", nav_options, horizontal=True, label_visibility="collapsed")

st.divider()

# --- 6. 侧边栏：仅作为辅助信息区 ---
with st.sidebar:
    st.header(f"👤 {user}")
    st.caption("👑 最高指挥官" if role == 'admin' else "⚔️ 核心成员")
    
    # 简报
    yvp_7 = calculate_net_yvp(user, 7)
    yvp_all = calculate_net_yvp(user, None)
    st.metric("本周产出", yvp_7)
    st.metric("总净资产", yvp_all)
    
    st.divider()
    if st.button("注销退出"):
        cookie_manager.delete("yanzu_user")
        cookie_manager.delete("yanzu_role")
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.rerun()

# --- 7. 页面路由 ---

# ================= 📋 任务大厅 =================
if nav == "📋 任务大厅":
    st.header("🛡️ 任务大厅")
    t_df = run_query("tasks")
    
    # 抢单区
    st.subheader("🔥 待抢任务")
    if not t_df.empty:
        pool = t_df[(t_df['status']=='待领取') & (t_df['type']=='公共任务池')]
        if not pool.empty:
            # 响应式布局：每行显示几个卡片
            cols = st.columns(3)
            for i, (idx, row) in enumerate(pool.iterrows()):
                with cols[i % 3]:
                    with st.container(border=True):
                        st.markdown(f"**{row['title']}**")
                        st.caption(f"💰 {round(row['difficulty']*row['std_time'], 2)} | 难度 {row['difficulty']}")
                        st.text(row.get('description', '')[:40]+"...")
                        
                        if role != 'admin':
                            if st.button("⚡️ 抢单", key=f"grab_{row['id']}", type="primary"):
                                supabase.table("tasks").update({"status": "进行中", "assignee": user}).eq("id", int(row['id'])).execute()
                                st.toast(random.choice(ENCOURAGEMENTS), icon="🔥")
                                time.sleep(1)
                                st.rerun()
                        else:
                            st.button("🔒 监视中", key=f"lk_{row['id']}", disabled=True)
        else:
            st.info("公共池空闲中")
    
    st.divider()
    # 全军看板
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("🔭 全军动态")
        if not t_df.empty:
            active = t_df[t_df['status'].isin(['进行中', '返工', '待验收'])]
            if not active.empty:
                st.dataframe(active[['title', 'assignee', 'status']], use_container_width=True, hide_index=True)
            else:
                st.caption("全军休整中")
    with c2:
        st.subheader("📜 荣誉榜")
        if not t_df.empty:
            done = t_df[t_df['status']=='完成'].sort_values('completed_at', ascending=False).head(10)
            if not done.empty:
                done['YVP'] = done['difficulty'] * done['std_time'] * done['quality']
                st.dataframe(done[['title', 'assignee', 'YVP']], use_container_width=True, hide_index=True)

# ================= 🗣️ 颜祖广场 =================
elif nav == "🗣️ 颜祖广场":
    st.header("🗣️ 颜祖广场")
    with st.expander("✍️ 发布新寄语"):
        txt = st.text_area("输入内容...")
        if st.button("发布"):
            if txt:
                supabase.table("messages").insert({"username": user, "content": txt, "created_at": str(datetime.datetime.now())}).execute()
                st.success("已发布")
                st.rerun()
    
    msgs = run_query("messages")
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
        mems = u_df[u_df['role']!='admin']['username'].tolist()
        def get_rank(lookback):
            d = []
            for m in mems:
                val = calculate_net_yvp(m, lookback)
                d.append({"成员": m, "YVP": val})
            return pd.DataFrame(d).sort_values("YVP", ascending=False)
            
        t1, t2, t3 = st.tabs(["📅 7天榜", "🗓️ 30天榜", "🔥 总榜"])
        with t1: st.dataframe(get_rank(7), use_container_width=True, hide_index=True)
        with t2: st.dataframe(get_rank(30), use_container_width=True, hide_index=True)
        with t3: st.dataframe(get_rank(None), use_container_width=True, hide_index=True)

# ================= 🏰 个人中心 =================
elif nav == "🏰 个人中心":
    # --- 管理员视图 ---
    if role == 'admin':
        st.header("👑 统帅控制台")
        adm_tabs = st.tabs(["🚀 发布", "🛠️ 管理", "⚖️ 裁决", "👥 成员", "💾 备份"])
        
        with adm_tabs[0]: # 发布
            c1, c2 = st.columns(2)
            title = c1.text_input("任务名称")
            dead = c1.date_input("截止")
            desc = st.text_area("详情")
            diff = c2.number_input("难度", 1.0, step=0.1)
            stdt = c2.number_input("工时", 1.0, step=0.5)
            ttype = c2.radio("类型", ["公共任务池", "指定指派"], horizontal=True)
            assignee = "待定"
            if ttype == "指定指派":
                udf = run_query("users")
                if not udf.empty:
                    ms = udf[udf['role']!='admin']['username'].tolist()
                    assignee = st.selectbox("指派给", ms)
            if st.button("发布", type="primary"):
                s = "待领取" if ttype=="公共任务池" else "进行中"
                a = assignee if ttype=="指定指派" else "待定"
                supabase.table("tasks").insert({"title": title, "description": desc, "difficulty": diff, "std_time": stdt, "status": s, "assignee": a, "deadline": str(dead), "type": ttype, "feedback": ""}).execute()
                st.success("已发布")

        with adm_tabs[1]: # 管理
            st.subheader("全局修正")
            tdf = run_query("tasks")
            if not tdf.empty:
                search = st.text_input("搜任务", placeholder="标题...")
                if search: tdf = tdf[tdf['title'].str.contains(search, na=False)]
                if not tdf.empty:
                    tid = st.selectbox("选择", tdf['id'], format_func=lambda x: f"{tdf[tdf['id']==x]['title'].values[0]}")
                    curr = tdf[tdf['id']==tid].iloc[0]
                    with st.container(border=True):
                        e_t = st.text_input("标题", curr['title'])
                        e_s = st.selectbox("状态", ["待领取", "进行中", "待验收", "完成", "返工"], index=["待领取", "进行中", "待验收", "完成", "返工"].index(curr['status']) if curr['status'] in ["待领取", "进行中", "待验收", "完成", "返工"] else 0)
                        e_q = st.number_input("质量", value=float(curr['quality']), step=0.1)
                        c_b1, c_b2 = st.columns([1,4])
                        if c_b1.button("保存"):
                            supabase.table("tasks").update({"title": e_t, "status": e_s, "quality": e_q}).eq("id", int(tid)).execute()
                            st.success("OK")
                            st.rerun()
                        if c_b2.button("删除", type="primary"):
                            supabase.table("tasks").delete().eq("id", int(tid)).execute()
                            st.rerun()

        with adm_tabs[2]: # 裁决
            pend = run_query("tasks")
            if not pend.empty: pend = pend[pend['status']=='待验收']
            if not pend.empty:
                pid = st.selectbox("待审", pend['id'], format_func=lambda x: f"{pend[pend['id']==x]['title'].values[0]}")
                with st.container(border=True):
                    q = st.slider("质量", 0.0, 3.0, 1.0, 0.1)
                    fb = st.text_area("御批")
                    res = st.selectbox("结果", ["完成", "返工"])
                    if st.button("提交裁决"):
                        cat = str(datetime.date.today()) if res=="完成" else None
                        supabase.table("tasks").update({"quality": q, "feedback": fb, "status": res, "completed_at": cat}).eq("id", int(pid)).execute()
                        st.success("生效")
                        st.rerun()
            else:
                st.info("无待审")

        with adm_tabs[3]: # 成员
            st.subheader("成员管理")
            udf = run_query("users")
            with st.expander("🚨 记过 (缺勤)"):
                if not udf.empty:
                    target = st.selectbox("违规人", udf[udf['role']!='admin']['username'].tolist())
                    if st.button("记录缺勤"):
                        supabase.table("penalties").insert({"username": target, "occurred_at": str(datetime.date.today()), "reason": "缺勤"}).execute()
                        st.success("已记录")
            
            st.write("名单:")
            if not udf.empty:
                for i, m in udf[udf['role']!='admin'].iterrows():
                    with st.container(border=True):
                        c1, c2, c3 = st.columns([2,2,1])
                        c1.write(f"**{m['username']}**")
                        np = c2.text_input(f"改密-{m['username']}", label_visibility="collapsed", placeholder="新密码")
                        if c2.button("重置", key=f"r{m['username']}"):
                            if np: supabase.table("users").update({"password": np}).eq("username", m['username']).execute(); st.toast("OK")
                        if c3.button("驱逐", key=f"d{m['username']}", type="primary"):
                            supabase.table("users").delete().eq("username", m['username']).execute(); st.rerun()

        with adm_tabs[4]: # 备份
            if st.button("下载全量备份"):
                d1 = run_query("users"); d2 = run_query("tasks"); d3 = run_query("penalties"); d4 = run_query("messages")
                b = io.StringIO()
                b.write("===USERS===\n"); d1.to_csv(b, index=False)
                b.write("\n===TASKS===\n"); d2.to_csv(b, index=False)
                b.write("\n===PENALTIES===\n"); d3.to_csv(b, index=False)
                b.write("\n===MESSAGES===\n"); d4.to_csv(b, index=False)
                st.download_button("📥 下载", b.getvalue(), "backup.txt")

    # --- 普通成员视图 ---
    else:
        st.header("⚔️ 我的战场")
        tdf = run_query("tasks")
        if not tdf.empty:
            my = tdf[(tdf['assignee']==user) & (tdf['status']=='进行中')]
            if not my.empty:
                for i, r in my.iterrows():
                    with st.container(border=True):
                        st.markdown(f"**{r['title']}**")
                        st.caption(f"截止: {r.get('deadline', '无')}")
                        if st.button("✅ 交付", key=f"deliv_{r['id']}", type="primary"):
                             supabase.table("tasks").update({"status": "待验收"}).eq("id", int(r['id'])).execute()
                             st.success("已交付")
                             st.rerun()
            else:
                st.info("暂无进行中任务")
        
        st.divider()
        with st.expander("🔐 修改密码"):
            np = st.text_input("新密码", type="password", key="s_p")
            if st.button("修改"):
                supabase.table("users").update({"password": np}).eq("username", user).execute()
                st.success("已更新")
