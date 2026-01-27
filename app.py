import streamlit as st
import pandas as pd
import datetime
import time
import io
import random
import extra_streamlit_components as stx # 引入Cookie管理器
from supabase import create_client, Client

# --- 1. 系统基础配置 ---
st.set_page_config(
    page_title="颜祖美学·执行中枢 V16.0",
    page_icon="🏛️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# CSS 美化：隐藏多余菜单，优化按钮
st.markdown("""
    <style>
        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}
        header {visibility: hidden;}
        /* 使得 tab 字体更大 */
        button[data-baseweb="tab"] > div {font-size: 1.1rem; font-weight: bold;} 
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

@st.cache_data(ttl=5) # 短缓存，防止频繁请求
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
    """核心军规：缺勤滑动扣款"""
    tasks = run_query("tasks")
    if tasks.empty: return 0.0
    
    my_done = tasks[(tasks['assignee'] == username) & (tasks['status'] == '完成')].copy()
    if my_done.empty: return 0.0
    
    my_done['val'] = my_done['difficulty'] * my_done['std_time'] * my_done['quality']
    my_done['completed_at'] = pd.to_datetime(my_done['completed_at'])

    # 1. 计算产出
    view_df = my_done.copy()
    if days_lookback:
        cutoff = pd.Timestamp.now() - pd.Timedelta(days=days_lookback)
        view_df = view_df[view_df['completed_at'] >= cutoff]
    
    gross = view_df['val'].sum()

    # 2. 计算罚款 (仅在计算总资产时扣除)
    total_fine = 0.0
    if days_lookback is None: 
        penalties = run_query("penalties")
        if not penalties.empty:
            my_pens = penalties[penalties['username'] == username].copy()
            if not my_pens.empty:
                my_pens['occurred_at'] = pd.to_datetime(my_pens['occurred_at'])
                for _, pen in my_pens.iterrows():
                    # 规则：扣除惩罚日之前7天内产出的20%
                    w_start = pen['occurred_at'] - pd.Timedelta(days=7)
                    w_tasks = my_done[(my_done['completed_at'] >= w_start) & (my_done['completed_at'] <= pen['occurred_at'])]
                    total_fine += w_tasks['val'].sum() * 0.2

    if days_lookback:
        return round(gross, 2)
    else:
        return round(gross - total_fine, 2)

# --- 4. 语录库 ---
QUOTES = ["管理者的跃升，是从'对任务负责'到'对目标负责'。", "没有执行力，一切战略都是空谈。", "不要假装努力，结果不会陪你演戏。"]
ENCOURAGEMENTS = ["🔥 哪怕是一颗螺丝钉，也要拧得比别人紧！", "🚀 相信你的能力，这个任务非你莫属！", "💪 干就完了！期待你的完美交付。"]

# --- 5. 鉴权与 Cookie 管理 (新增) ---
def get_manager():
    return stx.CookieManager()

cookie_manager = get_manager()

# 尝试从 Session 或 Cookie 获取用户
if 'user' not in st.session_state:
    # 1. 检查 Cookie
    cookie_user = cookie_manager.get(cookie="yanzu_user")
    cookie_role = cookie_manager.get(cookie="yanzu_role")
    
    if cookie_user and cookie_role:
        st.session_state.user = cookie_user
        st.session_state.role = cookie_role
        st.rerun()
    
    # 2. 显示登录页
    st.title("🏛️ 颜祖美学·执行中枢")
    st.caption("V16.0 Auto-Login Enabled")
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
                    # 设置 Session
                    st.session_state.user = u
                    st.session_state.role = role
                    # 设置 Cookie (有效期 30 天)
                    cookie_manager.set("yanzu_user", u, expires_at=datetime.datetime.now() + datetime.timedelta(days=30))
                    cookie_manager.set("yanzu_role", role, expires_at=datetime.datetime.now() + datetime.timedelta(days=30))
                    st.success("登录成功！")
                    time.sleep(1)
                    st.rerun()
                else:
                    st.error("账号或密码错误")
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

# --- 6. 主程序结构 ---
user = st.session_state.user
role = st.session_state.role

# === 侧边栏：个人概览 ===
with st.sidebar:
    st.title(f"👤 {user}")
    st.caption("👑 最高指挥官" if role == 'admin' else "⚔️ 核心成员")
    
    # 战绩
    yvp_7 = calculate_net_yvp(user, 7)
    yvp_all = calculate_net_yvp(user, None)
    c_a, c_b = st.columns(2)
    c_a.metric("7天产出", yvp_7)
    c_b.metric("净资产", yvp_all)
    
    st.divider()
    
    # 导航栏 (统一入口，解决“看不到界面”的问题)
    nav_options = ["📋 任务大厅", "🗣️ 颜祖广场", "🏆 风云榜", "🏰 个人中心"]
    nav = st.radio("导航", nav_options)
    
    st.divider()
    # 注销功能
    if st.button("注销退出"):
        cookie_manager.delete("yanzu_user")
        cookie_manager.delete("yanzu_role")
        for key in st.session_state.keys():
            del st.session_state[key]
        st.rerun()

# ================= 📋 任务大厅 (全员可见) =================
if nav == "📋 任务大厅":
    st.header("🛡️ 任务大厅")
    
    t_df = run_query("tasks")
    
    # 1. 抢单区
    st.subheader("🔥 待抢任务")
    if not t_df.empty:
        pool = t_df[(t_df['status']=='待领取') & (t_df['type']=='公共任务池')]
        if not pool.empty:
            cols = st.columns(3)
            for i, (idx, row) in enumerate(pool.iterrows()):
                with cols[i % 3]:
                    with st.container(border=True):
                        st.markdown(f"**{row['title']}**")
                        st.caption(f"💰 {round(row['difficulty']*row['std_time'], 2)} | 难度 {row['difficulty']}")
                        st.text(row.get('description', '')[:40]+"...")
                        
                        # 只有非管理员能抢，管理员看个热闹
                        if role != 'admin':
                            if st.button("⚡️ 抢单", key=f"grab_{row['id']}", type="primary"):
                                supabase.table("tasks").update({"status": "进行中", "assignee": user}).eq("id", int(row['id'])).execute()
                                st.toast(random.choice(ENCOURAGEMENTS), icon="🔥")
                                time.sleep(1)
                                st.rerun()
                        else:
                            st.button("🔒 管理员仅监视", key=f"lk_{row['id']}", disabled=True)
        else:
            st.info("公共池空闲中")
    
    st.divider()
    
    # 2. 全军看板
    st.subheader("🔭 全军动态")
    if not t_df.empty:
        active = t_df[t_df['status'].isin(['进行中', '返工', '待验收'])]
        if not active.empty:
            st.dataframe(active[['title', 'assignee', 'status', 'deadline']], use_container_width=True, hide_index=True)
            
    st.divider()
    
    # 3. 历史
    st.subheader("📜 荣誉榜")
    if not t_df.empty:
        done = t_df[t_df['status']=='完成']
        if not done.empty:
            done['YVP'] = done['difficulty'] * done['std_time'] * done['quality']
            st.dataframe(done[['title', 'assignee', 'YVP', 'feedback', 'completed_at']], use_container_width=True, hide_index=True)

# ================= 🗣️ 颜祖广场 (全员可见) =================
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

# ================= 🏆 风云榜 (全员可见) =================
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

# ================= 🏰 个人中心 (根据身份自动分流) =================
elif nav == "🏰 个人中心":
    
    # ------------------ 管理员视图 ------------------
    if role == 'admin':
        st.header("👑 统帅控制台")
        st.info("在这里行使您的最高指挥权。")
        
        adm_tabs = st.tabs(["🚀 发布指令", "🛠️ 全局管理", "⚖️ 任务裁决", "👥 成员与生杀", "💾 数据备份"])
        
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
                    assignee = st.selectbox("给谁", ms)
            if st.button("发布", type="primary"):
                s = "待领取" if ttype=="公共任务池" else "进行中"
                a = assignee if ttype=="指定指派" else "待定"
                supabase.table("tasks").insert({"title": title, "description": desc, "difficulty": diff, "std_time": stdt, "status": s, "assignee": a, "deadline": str(dead), "type": ttype, "feedback": ""}).execute()
                st.success("已发布")
        
        with adm_tabs[1]: # 修改/删除任务
            st.subheader("全局任务修正")
            tdf = run_query("tasks")
            if not tdf.empty:
                search = st.text_input("搜任务", placeholder="标题...")
                if search: tdf = tdf[tdf['title'].str.contains(search)]
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
                        time.sleep(1)
                        st.rerun()
                    if c_b2.button("删除", type="primary"):
                        supabase.table("tasks").delete().eq("id", int(tid)).execute()
                        st.rerun()
                        
        with adm_tabs[2]: # 裁决
            pend = run_query("tasks")
            if not pend.empty: pend = pend[pend['status']=='待验收']
            if not pend.empty:
                pid = st.selectbox("待审", pend['id'], format_func=lambda x: f"{pend[pend['id']==x]['title'].values[0]}")
                pc = pend[pend['id']==pid].iloc[0]
                with st.container(border=True):
                    st.write(f"执行人: {pc['assignee']}")
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
                
        with adm_tabs[3]: # 人员管理
            st.subheader("👥 成员管理")
            udf = run_query("users")
            
            # 军法
            with st.expander("🚨 军法处置 (缺勤记录)", expanded=True):
                if not udf.empty:
                    mems = udf[udf['role']!='admin']['username'].tolist()
                    target = st.selectbox("违规人", mems)
                    if st.button("记录缺勤"):
                        supabase.table("penalties").insert({"username": target, "occurred_at": str(datetime.date.today()), "reason": "缺勤"}).execute()
                        st.success(f"{target} 已记过")
            
            # 列表与删除
            st.markdown("#### 成员名单")
            if not udf.empty:
                for i, m in udf[udf['role']!='admin'].iterrows():
                    with st.container(border=True):
                        c_n, c_p, c_d = st.columns([2, 2, 1])
                        c_n.write(f"**{m['username']}**")
                        
                        new_p = c_p.text_input(f"重置密码", key=f"p_{m['username']}", label_visibility="collapsed", placeholder="新密码")
                        if c_p.button("重置", key=f"r_{m['username']}"):
                            if new_p:
                                supabase.table("users").update({"password": new_p}).eq("username", m['username']).execute()
                                st.toast("密码已重置")
                        
                        if c_d.button("驱逐", key=f"d_{m['username']}", type="primary"):
                            supabase.table("users").delete().eq("username", m['username']).execute()
                            st.warning("已驱逐")
                            time.sleep(1)
                            st.rerun()

        with adm_tabs[4]: # 备份
            if st.button("下载全量备份"):
                d1 = run_query("users")
                d2 = run_query("tasks")
                d3 = run_query("penalties")
                d4 = run_query("messages")
                b = io.StringIO()
                b.write("===USERS===\n"); d1.to_csv(b, index=False)
                b.write("\n===TASKS===\n"); d2.to_csv(b, index=False)
                b.write("\n===PENALTIES===\n"); d3.to_csv(b, index=False)
                b.write("\n===MESSAGES===\n"); d4.to_csv(b, index=False)
                st.download_button("📥 下载", b.getvalue(), "backup.txt")

    # ------------------ 普通成员视图 ------------------
    else:
        st.header("👤 我的战场")
        
        # 我的进行中任务
        st.subheader("⚔️ 进行中")
        tdf = run_query("tasks")
        if not tdf.empty:
            my = tdf[(tdf['assignee']==user) & (tdf['status']=='进行中')]
            if not my.empty:
                for i, r in my.iterrows():
                    with st.container(border=True):
                        c1, c2 = st.columns([4, 1])
                        c1.markdown(f"**{r['title']}**")
                        c1.caption(f"截止: {r.get('deadline', '无')}")
                        if c2.button("✅ 交付", key=f"deliv_{r['id']}", type="primary"):
                             supabase.table("tasks").update({"status": "待验收"}).eq("id", int(r['id'])).execute()
                             st.success("已交付")
                             st.rerun()
            else:
                st.info("暂无任务，请去大厅抢单")
        
        st.divider()
        st.subheader("🔐 账户设置")
        with st.expander("修改密码"):
            np = st.text_input("新密码", type="password", key="self_pwd")
            if st.button("确认修改", key="self_btn"):
                supabase.table("users").update({"password": np}).eq("username", user).execute()
                st.success("密码已更新")
