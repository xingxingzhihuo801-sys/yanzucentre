import streamlit as st
import pandas as pd
import datetime
import time
import io
import random
from supabase import create_client, Client

# --- 1. 系统基础配置 ---
st.set_page_config(
    page_title="颜祖美学·执行中枢 V15.0",
    page_icon="🏛️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 隐藏多余菜单，沉浸式体验
st.markdown("""
    <style>
        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}
        header {visibility: hidden;}
        /* 优化卡片显示 */
        div[data-testid="stMetricValue"] {font-size: 1.2rem;}
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

# --- 3. 核心算法区 ---

def run_query(table_name):
    """通用查表，带防崩处理"""
    try:
        response = supabase.table(table_name).select("*").execute()
        df = pd.DataFrame(response.data)
        # 自动转换日期列
        for col in ['created_at', 'deadline', 'completed_at', 'occurred_at']:
            if col in df.columns:
                df[col] = pd.to_datetime(df[col], errors='coerce').dt.date
        return df
    except:
        return pd.DataFrame() # 返回空表防止报错

def calculate_net_yvp(username, days_lookback=None):
    """
    V15.0 核心军规：缺勤滑动扣款
    """
    tasks = run_query("tasks")
    if tasks.empty: return 0.0
    
    # 筛选该用户已完成的任务
    my_done = tasks[(tasks['assignee'] == username) & (tasks['status'] == '完成')].copy()
    if my_done.empty: return 0.0
    
    # 预计算单任务价值
    my_done['val'] = my_done['difficulty'] * my_done['std_time'] * my_done['quality']
    # 确保时间格式为 datetime 以便比较
    my_done['completed_at'] = pd.to_datetime(my_done['completed_at'])

    # --- 1. 计算显示用的“产出” (Gross) ---
    view_df = my_done.copy()
    if days_lookback:
        cutoff = pd.Timestamp.now() - pd.Timedelta(days=days_lookback)
        view_df = view_df[view_df['completed_at'] >= cutoff]
    
    gross_income = view_df['val'].sum()

    # --- 2. 计算罚款 (Fine) ---
    # 仅当计算“总资产”时才扣除罚款，短期榜单只看产出爆发力
    total_fine = 0.0
    if days_lookback is None: 
        penalties = run_query("penalties")
        if not penalties.empty:
            my_pens = penalties[penalties['username'] == username].copy()
            if not my_pens.empty:
                my_pens['occurred_at'] = pd.to_datetime(my_pens['occurred_at'])
                for _, pen in my_pens.iterrows():
                    # 规则：每次缺勤，扣除【惩罚日之前7天内】产出的20%
                    p_date = pen['occurred_at']
                    w_start = p_date - pd.Timedelta(days=7)
                    
                    # 找到该窗口期的任务
                    w_tasks = my_done[(my_done['completed_at'] >= w_start) & (my_done['completed_at'] <= p_date)]
                    total_fine += w_tasks['val'].sum() * 0.2

    # --- 3. 返回结果 ---
    if days_lookback:
        return round(gross_income, 2) # 短期看产出
    else:
        return round(gross_income - total_fine, 2) # 总账看净值

# --- 4. 语录与鼓励库 ---
QUOTES = [
    "管理者的跃升，是从'对任务负责'到'对目标负责'。",
    "用系统工作的效率，对抗个体努力的瓶颈。",
    "不要假装努力，结果不会陪你演戏。",
    "痛苦是成长的属性，要因为痛苦而兴奋。",
    "没有执行力，一切战略都是空谈。"
]
ENCOURAGEMENTS = [
    "🔥 哪怕是一颗螺丝钉，也要拧得比别人紧！",
    "🚀 相信你的能力，这个任务非你莫属！",
    "💪 干就完了！期待你的完美交付。",
    "🌟 你的每一次交付，都在为颜祖帝国添砖加瓦。"
]

# --- 5. 登录模块 ---
if 'user' not in st.session_state:
    st.title("🏛️ 颜祖美学·执行中枢")
    st.caption("V15.0 Stable | Data Secured by Supabase")
    st.markdown(f"> *{random.choice(QUOTES)}*")
    
    c1, c2 = st.columns(2)
    with c1:
        with st.form("login"):
            st.markdown("#### 🔑 登录")
            u = st.text_input("用户名")
            p = st.text_input("密码", type="password")
            if st.form_submit_button("进入系统", type="primary"):
                res = supabase.table("users").select("*").eq("username", u).eq("password", p).execute()
                if res.data:
                    st.session_state.user = u
                    st.session_state.role = res.data[0]['role']
                    st.toast("鉴权通过！", icon="🫡")
                    time.sleep(0.5)
                    st.rerun()
                else:
                    st.error("账号或密码错误")
    with c2:
        with st.expander("📝 注册新账号"):
            nu = st.text_input("用户名")
            np = st.text_input("密码", type="password")
            if st.button("提交注册"):
                try:
                    supabase.table("users").insert({"username": nu, "password": np, "role": "member"}).execute()
                    st.success("注册成功！请登录。")
                except:
                    st.warning("用户已存在")
    st.stop()

# --- 6. 全局侧边栏 (始终显示) ---
user = st.session_state.user
role = st.session_state.role

with st.sidebar:
    st.title(f"👤 {user}")
    if role == 'admin':
        st.info("👑 最高指挥官")
    else:
        st.success("⚔️ 核心成员")
        
    # 战绩看板
    yvp_7 = calculate_net_yvp(user, 7)
    yvp_30 = calculate_net_yvp(user, 30)
    yvp_total = calculate_net_yvp(user, None)
    
    st.markdown("### 📊 个人战绩")
    c_a, c_b = st.columns(2)
    c_a.metric("7天产出", yvp_7)
    c_b.metric("30天产出", yvp_30)
    st.metric("🏆 净资产 (含罚款扣除)", f"💰 {yvp_total}")
    
    st.divider()
    
    # 密码修改
    with st.expander("🔐 修改我的密码"):
        new_pwd = st.text_input("新密码", type="password")
        if st.button("确认修改"):
            supabase.table("users").update({"password": new_pwd}).eq("username", user).execute()
            st.success("密码已更新")
    
    st.divider()
    if st.button("退出登录"):
        del st.session_state.user
        st.rerun()

    # --- 导航逻辑 (修复版：彻底分离) ---
    st.markdown("### 🧭 导航")
    if role == 'admin':
        # 管理员菜单
        nav = st.radio("前往", ["👑 统帅后台", "📋 任务大厅", "🗣️ 颜祖广场", "🏆 风云榜"])
    else:
        # 成员菜单
        nav = st.radio("前往", ["📋 任务大厅", "👤 我的战场", "🗣️ 颜祖广场", "🏆 风云榜"])

# --- 7. 页面路由 (Page Routing) ---

# ================= 👑 管理员：统帅后台 =================
if role == 'admin' and nav == "👑 统帅后台":
    st.header("👑 最高统帅部")
    
    # 管理员功能分栏
    tab1, tab2, tab3, tab4, tab5 = st.tabs(["🚀 发布", "🛠️ 任务管理", "⚖️ 裁决", "👥 人员与军法", "💾 备份"])
    
    with tab1: # 发布
        st.subheader("下达新指令")
        c1, c2 = st.columns(2)
        title = c1.text_input("任务名称")
        dead = c1.date_input("截止日期")
        desc = st.text_area("任务详情")
        
        diff = c2.number_input("难度系数", 1.0, step=0.1)
        std_t = c2.number_input("标准工时", 1.0, step=0.5)
        t_type = c2.radio("类型", ["公共任务池", "指定指派"], horizontal=True)
        
        assignee = "待定"
        if t_type == "指定指派":
            u_df = run_query("users")
            if not u_df.empty:
                mems = u_df[u_df['role']!='admin']['username'].tolist()
                assignee = st.selectbox("指派给", mems)
        
        if st.button("🚀 发布任务", type="primary"):
            status = "待领取" if t_type == "公共任务池" else "进行中"
            final_a = assignee if t_type == "指定指派" else "待定"
            supabase.table("tasks").insert({
                "title": title, "description": desc, "difficulty": diff, "std_time": std_t,
                "status": status, "assignee": final_a, "deadline": str(dead),
                "type": t_type, "feedback": ""
            }).execute()
            st.success("发布成功！")

    with tab2: # 全局编辑/删除
        st.subheader("🛠️ 全局任务修正")
        t_df = run_query("tasks")
        if not t_df.empty:
            search = st.text_input("搜索任务", placeholder="输入标题或人名...")
            if search:
                t_df = t_df[t_df['title'].str.contains(search) | t_df['assignee'].str.contains(search)]
            
            tid = st.selectbox("选择任务", t_df['id'], format_func=lambda x: f"ID {x} : {t_df[t_df['id']==x]['title'].values[0]}")
            curr = t_df[t_df['id']==tid].iloc[0]
            
            with st.container(border=True):
                c_e1, c_e2 = st.columns(2)
                e_tit = c_e1.text_input("标题", curr['title'])
                e_dif = c_e1.number_input("难度", value=float(curr['difficulty']))
                e_qua = c_e1.number_input("质量 (修正已完成)", value=float(curr['quality']), step=0.1)
                e_sta = c_e2.selectbox("状态", ["待领取", "进行中", "待验收", "完成", "返工"], index=["待领取", "进行中", "待验收", "完成", "返工"].index(curr['status']) if curr['status'] in ["待领取", "进行中", "待验收", "完成", "返工"] else 0)
                e_ass = c_e2.text_input("执行人", curr['assignee'])
                
                c_btn1, c_btn2 = st.columns([1, 5])
                if c_btn1.button("💾 保存"):
                    supabase.table("tasks").update({
                        "title": e_tit, "difficulty": e_dif, "quality": e_qua, "status": e_sta, "assignee": e_ass
                    }).eq("id", int(tid)).execute()
                    st.success("保存成功")
                    time.sleep(1)
                    st.rerun()
                if c_btn2.button("🗑️ 删除", type="primary"):
                    supabase.table("tasks").delete().eq("id", int(tid)).execute()
                    st.warning("已删除")
                    time.sleep(1)
                    st.rerun()

    with tab3: # 裁决
        st.subheader("⚖️ 待审任务")
        pend = run_query("tasks")
        if not pend.empty: pend = pend[pend['status']=='待验收']
        
        if not pend.empty:
            pid = st.selectbox("选择待审", pend['id'], format_func=lambda x: f"{pend[pend['id']==x]['title'].values[0]} ({pend[pend['id']==x]['assignee'].values[0]})")
            p_curr = pend[pend['id']==pid].iloc[0]
            
            with st.container(border=True):
                st.write(f"**{p_curr['title']}**")
                c_q, c_r = st.columns([1, 2])
                q_val = c_q.slider("质量评分", 0.0, 3.0, 1.0, 0.1)
                fb_val = c_r.text_area("御批 (必填)")
                res_val = c_r.selectbox("结果", ["完成", "返工"])
                
                if st.button("提交裁决"):
                    if not fb_val: st.error("请写理由")
                    else:
                        c_at = str(datetime.date.today()) if res_val=="完成" else None
                        supabase.table("tasks").update({
                            "quality": q_val, "status": res_val, "feedback": fb_val, "completed_at": c_at
                        }).eq("id", int(pid)).execute()
                        st.success("裁决完成")
                        time.sleep(1)
                        st.rerun()
        else:
            st.info("暂无待审任务")

    with tab4: # 人员与军法 (修复重点：独立的删人界面)
        st.subheader("👥 人员管理与军法")
        
        u_df = run_query("users")
        
        # 1. 军法记录
        with st.expander("🚨 记录缺勤 (扣除7天产出的20%)", expanded=True):
            if not u_df.empty:
                mems = u_df[u_df['role']!='admin']['username'].tolist()
                target = st.selectbox("违规人员", mems)
                if st.button("🚨 确认违规"):
                    supabase.table("penalties").insert({
                        "username": target, "occurred_at": str(datetime.date.today()), "reason": "缺勤"
                    }).execute()
                    st.success(f"已记录 {target} 缺勤。")
        
        st.divider()
        
        # 2. 人员列表与删除 (修复删人功能)
        st.markdown("### 📋 成员名册 (含删除功能)")
        if not u_df.empty:
            # 只显示普通成员，防止删掉管理员自己
            members = u_df[u_df['role'] != 'admin']
            for i, m in members.iterrows():
                with st.container(border=True):
                    c_name, c_reset, c_del = st.columns([2, 2, 1])
                    c_name.write(f"👤 **{m['username']}**")
                    
                    # 重置密码
                    new_p_admin = c_reset.text_input(f"重置密码-{m['username']}", placeholder="输入新密码", label_visibility="collapsed")
                    if c_reset.button("重置", key=f"rst_{m['username']}"):
                        if new_p_admin:
                            supabase.table("users").update({"password": new_p_admin}).eq("username", m['username']).execute()
                            st.toast("密码已重置")
                    
                    # 删除用户
                    if c_del.button("驱逐", key=f"del_{m['username']}", type="primary"):
                        supabase.table("users").delete().eq("username", m['username']).execute()
                        st.warning(f"已驱逐 {m['username']}")
                        time.sleep(1)
                        st.rerun()

    with tab5: # 备份
        st.subheader("💾 数据备份")
        if st.button("生成备份文件"):
            df_u = run_query("users")
            df_t = run_query("tasks")
            df_p = run_query("penalties")
            df_m = run_query("messages")
            
            buf = io.StringIO()
            buf.write("===USERS===\n")
            df_u.to_csv(buf, index=False)
            buf.write("\n===TASKS===\n")
            df_t.to_csv(buf, index=False)
            buf.write("\n===PENALTIES===\n")
            df_p.to_csv(buf, index=False)
            buf.write("\n===MESSAGES===\n")
            df_m.to_csv(buf, index=False)
            
            st.download_button("📥 点击下载", buf.getvalue(), f"backup_{datetime.date.today()}.txt")

# ================= 📋 任务大厅 (公用) =================
elif nav == "📋 任务大厅":
    st.header("🛡️ 任务大厅")
    t_df = run_query("tasks")
    
    # 待抢区域
    st.subheader("🔥 待抢任务")
    if not t_df.empty:
        pool = t_df[(t_df['status']=='待领取') & (t_df['type']=='公共任务池')]
        if not pool.empty:
            cols = st.columns(3)
            for i, (idx, row) in enumerate(pool.iterrows()):
                with cols[i % 3]:
                    with st.container(border=True):
                        st.markdown(f"**{row['title']}**")
                        st.write(f"💰 **{round(row['difficulty']*row['std_time'], 2)}**")
                        st.caption(f"截止: {row.get('deadline', '无')}")
                        st.text(row.get('description', '')[:40]+"...")
                        
                        # 仅非管理员可抢
                        if role != 'admin':
                            if st.button("⚡️ 抢单", key=f"grab_{row['id']}", type="primary"):
                                supabase.table("tasks").update({"status": "进行中", "assignee": user}).eq("id", int(row['id'])).execute()
                                st.toast(random.choice(ENCOURAGEMENTS), icon="🔥")
                                time.sleep(1)
                                st.rerun()
                        else:
                            st.caption("🔒 管理员仅查看")
        else:
            st.info("公共池空闲中")
            
    st.divider()
    
    # 全局看板
    st.subheader("🔭 全军动态")
    if not t_df.empty:
        active = t_df[t_df['status'].isin(['进行中', '返工', '待验收'])]
        if not active.empty:
            st.dataframe(active[['title', 'assignee', 'status', 'deadline']], use_container_width=True, hide_index=True)
        else:
            st.caption("暂无进行中任务")

    st.divider()
    
    # 历史
    st.subheader("📜 完工记录")
    if not t_df.empty:
        done = t_df[t_df['status']=='完成']
        if not done.empty:
            done['YVP'] = done['difficulty'] * done['std_time'] * done['quality']
            st.dataframe(done[['title', 'assignee', 'YVP', 'feedback', 'completed_at']], use_container_width=True, hide_index=True)

# ================= 👤 我的战场 (仅成员) =================
elif nav == "👤 我的战场" and role != 'admin':
    st.header("⚔️ 我的战场")
    t_df = run_query("tasks")
    
    if not t_df.empty:
        my = t_df[(t_df['assignee']==user) & (t_df['status']=='进行中')]
        if not my.empty:
            for i, r in my.iterrows():
                with st.container(border=True):
                    c1, c2 = st.columns([4, 1])
                    with c1:
                        st.markdown(f"### {r['title']}")
                        st.write(r.get('description', ''))
                        st.caption(f"截止: {r.get('deadline', '无')} | 难度: {r['difficulty']}")
                    with c2:
                        st.write("")
                        if st.button("✅ 交付", key=f"sub_{r['id']}", type="primary"):
                            supabase.table("tasks").update({"status": "待验收"}).eq("id", int(r['id'])).execute()
                            st.balloons()
                            st.success("已交付！")
                            time.sleep(1)
                            st.rerun()
        else:
            st.info("暂无任务，请前往大厅抢单")

# ================= 🗣️ 颜祖广场 (公用) =================
elif nav == "🗣️ 颜祖广场":
    st.header("🗣️ 颜祖广场")
    st.caption("分享认知，传递能量")
    
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

# ================= 🏆 风云榜 (公用) =================
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
