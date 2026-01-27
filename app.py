import streamlit as st
import pandas as pd
import datetime
import random
import time
from supabase import create_client, Client

# --- 系统配置 ---
st.set_page_config(page_title="颜祖美学·执行中枢 V12.0 (云端永恒版)", layout="wide")

# --- 1. 连接 Supabase 云端数据库 ---
try:
    url = st.secrets["supabase"]["url"]
    key = st.secrets["supabase"]["key"]
    supabase: Client = create_client(url, key)
except Exception as e:
    st.error("🚨 数据库连接失败！请检查 Streamlit 的 Secrets 配置是否正确。")
    st.info(f"错误信息: {e}")
    st.stop()

# --- 2. 核心工具函数 (针对 Supabase 优化) ---
def run_query(table_name):
    """获取整张表的数据，返回 DataFrame"""
    try:
        response = supabase.table(table_name).select("*").execute()
        return pd.DataFrame(response.data)
    except Exception as e:
        st.error(f"读取 {table_name} 失败: {e}")
        return pd.DataFrame()

def get_gold_stats(username, days=None):
    """计算净金币 (YVP)"""
    # 1. 获取所有完成的任务
    tasks = run_query("tasks")
    if tasks.empty:
        return 0.0, 0

    # 筛选：当前用户 + 已完成
    user_tasks = tasks[ (tasks['assignee'] == username) & (tasks['status'] == '完成') ]
    
    # 筛选：时间范围 (如果有)
    if days and not user_tasks.empty:
        # 将字符串转为日期进行比较
        cutoff = datetime.date.today() - datetime.timedelta(days=days)
        # 确保 completed_at 是日期类型
        user_tasks['completed_at'] = pd.to_datetime(user_tasks['completed_at']).dt.date
        user_tasks = user_tasks[user_tasks['completed_at'] >= cutoff]

    gross = 0.0
    if not user_tasks.empty:
        gross = (user_tasks['difficulty'] * user_tasks['std_time'] * user_tasks['quality']).sum()
    
    # 2. 获取惩罚
    pens = run_query("penalties")
    pen_cnt = 0
    if not pens.empty:
        pen_cnt = len(pens[pens['username'] == username])
        # 注意：这里简化逻辑，惩罚是累计的，一旦背了惩罚，所有时期的收益都受影响（作为严厉的威慑）
    
    net = gross * (1 - min(pen_cnt * 0.2, 1.0))
    return round(net, 2), pen_cnt

# --- 3. 励志语录 ---
QUOTES = [
    "痛苦是成长的属性。不要因为痛苦而逃避，要因为痛苦而兴奋。",
    "管理者的跃升，是从'对任务负责'到'对目标负责'。",
    "不要假装努力，结果不会陪你演戏。",
    "用系统工作的效率，对抗个体努力的瓶颈。"
]

# --- 4. 登录界面 ---
if 'user' not in st.session_state:
    st.title("🏛️ 颜祖美学·云端执行中枢")
    st.caption("Data Secured by Supabase™")
    st.info(f"🔥 {random.choice(QUOTES)}")
    
    col1, col2 = st.columns(2)
    with col1:
        with st.form("login"):
            u = st.text_input("用户名")
            p = st.text_input("密码", type="password")
            if st.form_submit_button("🚀 进入系统"):
                # Supabase 查询
                try:
                    response = supabase.table("users").select("*").eq("username", u).eq("password", p).execute()
                    if response.data:
                        st.session_state.user = u
                        st.session_state.role = response.data[0]['role']
                        st.toast("鉴权通过，正在进入...", icon="✅")
                        time.sleep(1)
                        st.rerun()
                    else:
                        st.error("鉴权失败")
                except Exception as e:
                    st.error(f"登录连接错误: {e}")

    with col2:
        with st.expander("📝 新兵注册通道"):
            nu = st.text_input("设置用户名")
            np = st.text_input("设置密码", type="password")
            if st.button("提交注册申请"):
                try:
                    supabase.table("users").insert({"username": nu, "password": np, "role": "member"}).execute()
                    st.success("注册成功！请左侧登录。")
                except:
                    st.warning("该用户名已被注册。")
    st.stop()

# --- 5. 主程序 ---
user = st.session_state.user
role = st.session_state.role

# 侧边栏
st.sidebar.title(f"👤 {user}")
if role == 'admin':
    st.sidebar.caption("👑 最高指挥官")
else:
    st.sidebar.caption("⚔️ 核心成员")
    net, pen = get_gold_stats(user)
    st.sidebar.metric("💰 净金币 (YVP)", net, delta=f"被罚 {pen} 次", delta_color="inverse")

if st.sidebar.button("注销"):
    del st.session_state.user
    st.rerun()

# 导航
if role == 'admin':
    menu = ["👑 核心控制台", "📋 任务大厅", "🏆 风云榜"]
else:
    menu = ["📋 任务大厅", "👤 我的任务", "🏆 风云榜"]
choice = st.sidebar.radio("导航", menu)

# ================= 👑 管理员控制台 =================
if choice == "👑 核心控制台" and role == 'admin':
    st.header("👑 最高统帅部 (云端版)")
    t1, t2, t3, t4 = st.tabs(["发布指令", "裁决评分", "军法考勤", "人员管理"])
    
    with t1: # 发布
        c1, c2 = st.columns(2)
        with c1:
            title = st.text_input("任务名称")
            desc = st.text_area("详细说明")
            deadline = st.date_input("截止日期")
        with c2:
            d = st.number_input("难度系数 (D)", 1.0, step=0.1)
            t = st.number_input("标准工时 (T)", 1.0, step=0.5)
            ttype = st.radio("类型", ["公共任务池", "指定指派"])
            assignee = "待定"
            if ttype == "指定指派":
                udf = run_query("users")
                if not udf.empty:
                    mems = udf[udf['role']!='admin']['username'].tolist()
                    assignee = st.selectbox("指派给", mems)
        
        if st.button("🚀 写入云端数据库"):
            status = "待领取" if ttype == "公共任务池" else "进行中"
            final_a = assignee if ttype == "指定指派" else "待定"
            # 写入 Supabase
            data = {
                "title": title, "description": desc, "difficulty": d, "std_time": t,
                "status": status, "assignee": final_a, "deadline": str(deadline),
                "type": ttype, "feedback": ""
            }
            supabase.table("tasks").insert(data).execute()
            st.success("指令已下达！")

    with t2: # 裁决
        # 只能查到 status='待验收'
        response = supabase.table("tasks").select("*").eq("status", "待验收").execute()
        pend = pd.DataFrame(response.data)
        
        if not pend.empty:
            tid = st.selectbox("待审任务", pend['id'], format_func=lambda x: f"ID {x}")
            curr = pend[pend['id']==tid].iloc[0]
            st.info(f"{curr['title']} | 执行人: {curr['assignee']}")
            
            q = st.slider("质量系数", 0.0, 3.0, 1.0, 0.1)
            fb = st.text_area("御批 (理由)", placeholder="必填...")
            res = st.selectbox("结果", ["完成", "返工"])
            
            if st.button("提交裁决"):
                if not fb:
                    st.error("请填写理由")
                else:
                    comp_at = str(datetime.date.today()) if res == "完成" else None
                    supabase.table("tasks").update({
                        "quality": q, "status": res, "feedback": fb, "completed_at": comp_at
                    }).eq("id", int(tid)).execute()
                    st.success("裁决已同步至云端")
                    time.sleep(1)
                    st.rerun()
        else:
            st.info("无待验收任务")

    with t3: # 惩罚
        udf = run_query("users")
        if not udf.empty:
            mems = udf[udf['role']!='admin']['username'].tolist()
            target = st.selectbox("违规人员", mems)
            if st.button("🚨 记录缺勤"):
                supabase.table("penalties").insert({
                    "username": target, "occurred_at": str(datetime.date.today()), "reason": "缺勤"
                }).execute()
                st.success(f"{target} 已受罚")
        
        st.caption("最近惩罚记录")
        st.dataframe(run_query("penalties"))

    with t4: # 人员
        udf = run_query("users")
        for i, r in udf.iterrows():
            if r['role'] != 'admin':
                c1, c2 = st.columns([3, 1])
                c1.write(f"**{r['username']}**")
                if c2.button("驱逐", key=r['username']):
                    supabase.table("users").delete().eq("username", r['username']).execute()
                    st.rerun()

# ================= 📋 任务大厅 =================
elif choice == "📋 任务大厅":
    st.header("🛡️ 任务大厅")
    
    # 1. 抢单区
    response = supabase.table("tasks").select("*").eq("status", "待领取").eq("type", "公共任务池").execute()
    pool = pd.DataFrame(response.data)
    
    if not pool.empty:
        st.subheader("🔥 待领取任务")
        for i, r in pool.iterrows():
            gold = round(r['difficulty'] * r['std_time'], 2)
            with st.expander(f"💰 {gold} | {r['title']}"):
                st.write(f"**详情**: {r['description']}")
                st.write(f"**截止**: {r['deadline']}")
                if role != 'admin':
                    if st.button("⚡️ 抢单", key=f"take_{r['id']}"):
                        supabase.table("tasks").update({
                            "status": "进行中", "assignee": user
                        }).eq("id", int(r['id'])).execute()
                        st.success("抢单成功！")
                        time.sleep(1)
                        st.rerun()
                else:
                    st.caption("🔒 管理员仅查看")
    else:
        st.info("公共池暂无任务")
    
    st.divider()
    
    # 2. 实时看板
    st.subheader("🔭 实时进度")
    # 获取进行中、待验收、返工
    tasks = run_query("tasks")
    if not tasks.empty:
        active = tasks[tasks['status'].isin(['进行中', '返工', '待验收'])]
        st.dataframe(active[['title', 'assignee', 'status', 'deadline']], use_container_width=True)
    
    st.divider()
    
    # 3. 完工记录
    st.subheader("📜 完工御批")
    if not tasks.empty:
        done = tasks[tasks['status']=='完成']
        if not done.empty:
            done['earned'] = done['difficulty'] * done['std_time'] * done['quality']
            st.dataframe(done[['title', 'assignee', 'earned', 'feedback', 'completed_at']], use_container_width=True)

# ================= 👤 我的任务 =================
elif choice == "👤 我的任务":
    st.header("⚔️ 我的战场")
    # 查询我的进行中任务
    response = supabase.table("tasks").select("*").eq("assignee", user).eq("status", "进行中").execute()
    my = pd.DataFrame(response.data)
    
    if not my.empty:
        for i, r in my.iterrows():
            with st.container(border=True):
                c1, c2 = st.columns([3, 1])
                c1.write(f"**{r['title']}**")
                c1.caption(f"截止: {r['deadline']}")
                if c2.button("✅ 提交验收", key=r['id']):
                    supabase.table("tasks").update({"status": "待验收"}).eq("id", int(r['id'])).execute()
                    st.success("已提交！")
                    time.sleep(1)
                    st.rerun()
    else:
        st.info("暂无任务，请去大厅抢单")

# ================= 🏆 风云榜 =================
elif choice == "🏆 风云榜":
    st.header("🏆 颜祖富豪榜")
    udf = run_query("users")
    if not udf.empty:
        mems = udf[udf['role']!='admin']['username'].tolist()
        data = []
        for m in mems:
            g, p = get_gold_stats(m)
            data.append({"成员": m, "净金币": g, "缺勤次数": p})
        
        if data:
            df = pd.DataFrame(data).sort_values("净金币", ascending=False)
            st.dataframe(df, use_container_width=True)
