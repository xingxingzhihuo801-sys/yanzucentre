import streamlit as st
import pandas as pd
import datetime
import time
import io
import random
import extra_streamlit_components as stx
from supabase import create_client, Client

# --- 1. 系统配置与视觉隐身 ---
st.set_page_config(
    page_title="颜祖美学·执行中枢 V22.0",
    page_icon="🏛️",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# 强力 CSS 优化：保留核心 UI，隐藏开发调试工具
st.markdown("""
    <style>
        #MainMenu {visibility: hidden;}
        header {visibility: hidden;}
        footer {visibility: hidden;}
        .stDeployButton {display:none;}
        div[data-testid="stToolbar"] {visibility: hidden;}
        div[data-testid="stDecoration"] {visibility: hidden;}
        div[data-testid="stStatusWidget"] {visibility: hidden;}
        
        /* 顶部导航菜单横向排列 */
        div[data-testid="stRadio"] > div {
            flex-direction: row;
            justify-content: center;
            background-color: #f8f9fa;
            padding: 10px;
            border-radius: 8px;
            border: 1px solid #dee2e6;
        }
        
        /* 滚动公告样式 */
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

# --- 3. 初始化 Cookie 管理器 (修复警告的关键：不使用缓存装饰器) ---
cookie_manager = stx.CookieManager(key="yanzu_v22_cookie_unique")

# --- 4. 核心工具函数 ---
@st.cache_data(ttl=3)
def run_query(table_name):
    """仅对纯数据查询使用缓存"""
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

def calculate_net_yvp(username, days_lookback=None):
    # 管理员不计分
    users = run_query("users")
    if not users.empty:
        user_row = users[users['username']==username]
        if not user_row.empty and user_row.iloc[0]['role'] == 'admin':
            return 0.0

    tasks = run_query("tasks")
    if tasks.empty: return 0.0
    my_done = tasks[(tasks['assignee'] == username) & (tasks['status'] == '完成')].copy()
    if my_done.empty: return 0.0
    
    my_done['val'] = my_done['difficulty'] * my_done['std_time'] * my_done['quality']
    my_done['completed_at'] = pd.to_datetime(my_done['completed_at'])
    
    if days_lookback:
        cutoff = pd.Timestamp.now() - pd.Timedelta(days=days_lookback)
        my_done = my_done[my_done['completed_at'] >= cutoff]
    
    gross = my_done['val'].sum()

    # 罚款逻辑
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
    return round(gross - total_fine, 2)

def format_deadline(d_val):
    if pd.isna(d_val) or str(d_val) in ['NaT', 'None', '']: return "♾️ 无期限"
    return str(d_val)

# --- 5. 鉴权与自动登录 ---
if 'user' not in st.session_state:
    st.session_state.user = None
    st.session_state.role = None

# 尝试通过 Cookie 自动登录
if st.session_state.user is None:
    # 稍微等待组件加载
    time.sleep(0.5)
    c_user = cookie_manager.get("yanzu_user")
    c_role = cookie_manager.get("yanzu_role")
    if c_user and c_role:
        st.session_state.user = c_user
        st.session_state.role = c_role
        st.rerun()

# 登录界面
if st.session_state.user is None:
    st.title("🏛️ 颜祖美学·执行中枢")
    c1, c2 = st.columns(2)
    with c1:
        with st.form("login"):
            st.markdown("### 🔑 登录")
            u = st.text_input("用户名")
            p = st.text_input("密码", type="password")
            if st.form_submit_button("进入系统", type="primary"):
                res = supabase.table("users").select("*").eq("username", u).eq("password", p).execute()
                if res.data:
                    st.session_state.user = u
                    st.session_state.role = res.data[0]['role']
                    cookie_manager.set("yanzu_user", u, expires_at=datetime.datetime.now() + datetime.timedelta(days=30))
                    cookie_manager.set("yanzu_role", st.session_state.role, expires_at=datetime.datetime.now() + datetime.timedelta(days=30))
                    st.success("验证成功")
                    time.sleep(0.5)
                    st.rerun()
                else: st.error("账号或密码错误")
    with c2:
        with st.expander("📝 注册新成员"):
            nu = st.text_input("用户名", key="reg_u")
            np = st.text_input("密码", type="password", key="reg_p")
            if st.button("提交注册"):
                try:
                    supabase.table("users").insert({"username": nu, "password": np, "role": "member"}).execute()
                    st.success("注册成功！请直接登录。")
                except: st.warning("用户名已存在")
    st.stop()

# --- 6. 核心业务界面 ---
user = st.session_state.user
role = st.session_state.role

# 滚动公告
ann_text = get_announcement()
st.markdown(f"""<div class="scrolling-text"><marquee scrollamount="6">🔔 公告：{ann_text}</marquee></div>""", unsafe_allow_html=True)

st.title(f"🏛️ 帝国中枢 · {user}")
nav = st.radio("NAV", ["📋 任务大厅", "🗣️ 颜祖广场", "🏆 风云榜", "🏰 个人中心"], horizontal=True, label_visibility="collapsed")
st.divider()

# 侧边栏
with st.sidebar:
    st.header(f"👤 {user}")
    st.caption("👑 管理员" if role == 'admin' else "⚔️ 成员")
    if role != 'admin':
        yvp_7 = calculate_net_yvp(user, 7)
        yvp_all = calculate_net_yvp(user)
        st.metric("本周产出", yvp_7)
        st.metric("总净资产", yvp_all)
    st.divider()
    if st.button("注销并退出"):
        cookie_manager.set("yanzu_user", "", expires_at=datetime.datetime.now() - datetime.timedelta(days=1))
        cookie_manager.set("yanzu_role", "", expires_at=datetime.datetime.now() - datetime.timedelta(days=1))
        st.session_state.user = None
        st.session_state.role = None
        time.sleep(0.5)
        st.rerun()

# ================= 业务路由 =================

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
                        st.caption(f"📅 截止: {format_deadline(row.get('deadline'))}")
                        st.markdown(f"D:{row['difficulty']} | T:{row['std_time']}")
                        if st.button("⚡️ 抢单", key=f"g_{row['id']}", type="primary"):
                            supabase.table("tasks").update({"status": "进行中", "assignee": user}).eq("id", int(row['id'])).execute()
                            st.toast("任务已领取，加油！", icon="🚀")
                            time.sleep(0.5); st.rerun()
        else: st.info("目前池中无任务")

    st.divider()
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("🔭 实时动态")
        active = tdf[tdf['status'].isin(['进行中', '返工', '待验收'])]
        if not active.empty:
            st.dataframe(active[['title', 'assignee', 'status']], use_container_width=True, hide_index=True)
    with c2:
        st.subheader("📜 荣誉记录")
        done = tdf[tdf['status']=='完成'].sort_values('completed_at', ascending=False).head(10)
        if not done.empty:
            done['P'] = done.apply(lambda x: f"D{x['difficulty']}/T{x['std_time']}/Q{x['quality']}", axis=1)
            st.dataframe(done[['title', 'assignee', 'P']], use_container_width=True, hide_index=True)

elif nav == "🗣️ 颜祖广场":
    st.header("🗣️ 颜祖广场")
    with st.expander("✍️ 发布寄语/感想"):
        txt = st.text_area("输入内容")
        if st.button("确认发布"):
            supabase.table("messages").insert({"username": user, "content": txt, "created_at": str(datetime.datetime.now())}).execute()
            st.rerun()
    msgs = run_query("messages")
    if not msgs.empty:
        msgs = msgs[msgs['username'] != '__NOTICE__'].sort_values("created_at", ascending=False)
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
        t1, t2 = st.tabs(["📅 7天榜", "🔥 总资产榜"])
        with t1: st.dataframe(get_lb(7), use_container_width=True, hide_index=True)
        with t2: st.dataframe(get_lb(None), use_container_width=True, hide_index=True)

elif nav == "🏰 个人中心":
    if role == 'admin':
        st.header("👑 统帅后台")
        # 10天备份提醒
        if datetime.date.today().day % 10 == 0:
            st.warning(f"📅 **今日为备份提醒日 ({datetime.date.today().day}号)，请下载全量备份。**")
            
        tabs = st.tabs(["⚡️ 随手记", "🚀 发布任务", "🛠️ 全量管理", "⚖️ 裁决审核", "📢 公告维护", "👥 成员管理", "💾 备份恢复"])
        
        with tabs[0]:
            st.info("直接派发给自己的任务，不计分，完成后点击‘归档’。")
            quick_t = st.text_input("任务标题")
            if st.button("⚡️ 派发给我", type="primary"):
                supabase.table("tasks").insert({"title": quick_t, "difficulty": 0, "std_time": 0, "status": "进行中", "assignee": user, "type": "AdminSelf"}).execute()
                st.success("已添加")
        
        with tabs[1]:
            c1, c2 = st.columns(2)
            t_name = c1.text_input("任务名称")
            col_d, col_c = c1.columns([3,2])
            d_input = col_d.date_input("截止日期")
            no_d = col_c.checkbox("无截止日期")
            diff = c2.number_input("难度 (0-99)", value=1.0, step=0.1)
            stdt = c2.number_input("工时 (0-99)", value=1.0, step=0.5)
            ttype = c2.radio("派发模式", ["公共任务池", "指派成员"], horizontal=True)
            assign = "待定"
            udf = run_query("users")
            if ttype == "指派成员": assign = st.selectbox("指派给", udf['username'].tolist())
            if st.button("🚀 确认发布", type="primary"):
                final_d = None if no_d else str(d_input)
                supabase.table("tasks").insert({"title": t_name, "difficulty": diff, "std_time": stdt, "status": "待领取" if ttype=="公共任务池" else "进行中", "assignee": assign if ttype=="指派成员" else "待定", "deadline": final_d, "type": ttype}).execute()
                st.success("已发布")

        with tabs[2]:
            st.subheader("🛠️ 全量数据修正")
            tdf = run_query("tasks"); udf = run_query("users")
            if not tdf.empty:
                c_f1, c_f2 = st.columns(2)
                f_u = c_f1.selectbox("筛选人员", ["全部"] + list(udf['username'].unique()))
                s_k = c_f2.text_input("搜标题")
                filtered = tdf.copy()
                if f_u != "全部": filtered = filtered[filtered['assignee'] == f_u]
                if s_k: filtered = filtered[filtered['title'].str.contains(s_k, case=False, na=False)]
                if not filtered.empty:
                    sel_id = st.selectbox("选择要修改的任务", filtered['id'], format_func=lambda x: f"ID:{x}|{filtered[filtered['id']==x]['title'].values[0]}")
                    target = filtered[filtered['id']==sel_id].iloc[0]
                    with st.container(border=True):
                        new_title = st.text_input("修改标题", target['title'])
                        new_diff = st.number_input("修改难度", value=float(target['difficulty']))
                        new_status = st.selectbox("修改状态", ["待领取", "进行中", "待验收", "完成", "返工"], index=["待领取", "进行中", "待验收", "完成", "返工"].index(target['status']))
                        if st.button("💾 确认保存修改"):
                            supabase.table("tasks").update({"title": new_title, "difficulty": new_diff, "status": new_status}).eq("id", int(sel_id)).execute()
                            st.rerun()
                        with st.popover("🗑️ 删除任务"):
                            if st.button("确认删除"):
                                supabase.table("tasks").delete().eq("id", int(sel_id)).execute(); st.rerun()

        with tabs[3]:
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
                        st.success("已完成裁决"); st.rerun()
            else: st.info("暂无待审任务")

        with tabs[4]:
            st.subheader("📢 公告维护")
            new_ann = st.text_input("输入新公告内容", placeholder=ann_text)
            if st.button("立即发布公告"):
                supabase.table("messages").delete().eq("username", "__NOTICE__").execute()
                supabase.table("messages").insert({"username": "__NOTICE__", "content": new_ann, "created_at": str(datetime.datetime.now())}).execute()
                st.success("公告已更新")

        with tabs[5]:
            udf = run_query("users")
            st.subheader("👥 成员名录")
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

        with tabs[6]:
            st.subheader("💾 备份与恢复")
            d1=run_query("users"); d2=run_query("tasks"); d3=run_query("penalties"); d4=run_query("messages")
            buf = io.StringIO()
            buf.write("===USERS===\n"); d1.to_csv(buf, index=False)
            buf.write("\n===TASKS===\n"); d2.to_csv(buf, index=False)
            buf.write("\n===PENALTIES===\n"); d3.to_csv(buf, index=False)
            buf.write("\n===MESSAGES===\n"); d4.to_csv(buf, index=False)
            st.download_button("📥 下载备份", buf.getvalue(), f"backup_{datetime.date.today()}.txt")
            
            st.divider()
            up_f = st.file_uploader("上传备份文件 (.txt)", type=['txt'])
            if up_f:
                with st.popover("🚨 确认全量覆盖恢复"):
                    if st.button("确认恢复"):
                        try:
                            content = up_f.getvalue().decode("utf-8")
                            s_u = content.split("===USERS===\n")[1].split("===TASKS===")[0].strip()
                            s_t = content.split("===TASKS===\n")[1].split("===PENALTIES===")[0].strip()
                            s_p = content.split("===PENALTIES===\n")[1].split("===MESSAGES===")[0].strip()
                            s_m = content.split("===MESSAGES===\n")[1].strip()
                            supabase.table("users").delete().neq("username", "_").execute()
                            supabase.table("tasks").delete().neq("id", -1).execute()
                            supabase.table("penalties").delete().neq("id", -1).execute()
                            supabase.table("messages").delete().neq("id", -1).execute()
                            if s_u: supabase.table("users").insert(pd.read_csv(io.StringIO(s_u)).to_dict('records')).execute()
                            if s_t: supabase.table("tasks").insert(pd.read_csv(io.StringIO(s_t)).to_dict('records')).execute()
                            if s_p: supabase.table("penalties").insert(pd.read_csv(io.StringIO(s_p)).to_dict('records')).execute()
                            if s_m: supabase.table("messages").insert(pd.read_csv(io.StringIO(s_m)).to_dict('records')).execute()
                            st.success("恢复完成"); st.rerun()
                        except: st.error("恢复失败，格式不符")

    else: # 成员界面
        st.header("⚔️ 我的战场")
        tdf = run_query("tasks")
        # 评分提醒
        td_done = tdf[(tdf['assignee']==user) & (tdf['status']=='完成') & (tdf['completed_at'] == datetime.date.today())]
        if not td_done.empty: st.info(f"🔔 喜报！您有 {len(td_done)} 个任务今日已评分！")
        
        my = tdf[(tdf['assignee']==user) & (tdf['status']=='进行中')]
        if not my.empty:
            for i, r in my.iterrows():
                with st.container(border=True):
                    st.markdown(f"**{r['title']}**")
                    st.caption(f"📅 截止：{format_deadline(r.get('deadline'))}")
                    st.caption(f"⚙️ 难度: {r['difficulty']} | ⏱️ 工时: {r['std_time']}")
                    if st.button("✅ 交付验收", key=f"dev_{r['id']}", type="primary"):
                        supabase.table("tasks").update({"status": "待验收"}).eq("id", int(r['id'])).execute()
                        st.success("已提交交付"); st.rerun()
        else: st.info("暂无任务，前往大厅看看吧。")
        st.divider()
        with st.expander("🔐 修改密码"):
            new_p = st.text_input("新密码", type="password")
            if st.button("确认更改"):
                supabase.table("users").update({"password": new_p}).eq("username", user).execute()
                st.success("密码已更新")
