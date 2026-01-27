import streamlit as st
import pandas as pd
import datetime
import time
import io
import random
from supabase import create_client, Client

# --- 1. 系统美学配置 ---
st.set_page_config(
    page_title="颜祖美学·执行中枢 V14.0",
    page_icon="🏛️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 隐藏默认的 Streamlit 菜单，让界面更像 App
hide_st_style = """
            <style>
            #MainMenu {visibility: hidden;}
            footer {visibility: hidden;}
            header {visibility: hidden;}
            </style>
            """
st.markdown(hide_st_style, unsafe_allow_html=True)

# --- 2. 连接 Supabase ---
try:
    url = st.secrets["supabase"]["url"]
    key = st.secrets["supabase"]["key"]
    supabase: Client = create_client(url, key)
except Exception:
    st.error("🚨 数据库连接失败，请检查 Secrets。")
    st.stop()

# --- 3. 核心算法与工具 ---

def run_query(table_name):
    """通用查表函数，带缓存优化"""
    try:
        response = supabase.table(table_name).select("*").execute()
        df = pd.DataFrame(response.data)
        # 自动日期转换
        for col in ['created_at', 'deadline', 'completed_at', 'occurred_at']:
            if col in df.columns:
                df[col] = pd.to_datetime(df[col], errors='coerce').dt.date
        return df
    except:
        return pd.DataFrame()

def calculate_net_yvp(username, days_lookback=None):
    """
    V14.0 核心算法：滑动窗口惩罚机制
    规则：每发生一次缺勤，扣除该缺勤发生日期前 7 天内完工任务总值的 20%。
    """
    # 1. 获取该用户所有已完成任务
    tasks = run_query("tasks")
    if tasks.empty: return 0.0
    
    # 基础筛选：只看这个人的完成任务
    my_done = tasks[(tasks['assignee'] == username) & (tasks['status'] == '完成')].copy()
    if my_done.empty: return 0.0
    
    # 确保 completed_at 是日期类型
    my_done['completed_at'] = pd.to_datetime(my_done['completed_at'])
    my_done['val'] = my_done['difficulty'] * my_done['std_time'] * my_done['quality']

    # 2. 计算【总毛收入】 (Gross Income)
    # 如果指定了 days_lookback (比如只看过去7天赚了多少)，先过滤时间
    view_df = my_done.copy()
    if days_lookback:
        cutoff = pd.Timestamp.now() - pd.Timedelta(days=days_lookback)
        view_df = view_df[view_df['completed_at'] >= cutoff]
    
    gross_income = view_df['val'].sum()

    # 3. 计算【总罚款】 (Total Fine)
    # 注意：罚款是累计的，不随查看窗口变化而消失（除非惩罚本身太久远，但一般惩罚是永久记录）
    # 逻辑：遍历每一条惩罚记录，计算该次惩罚对应的“罚款额”
    penalties = run_query("penalties")
    total_fine = 0.0
    
    if not penalties.empty:
        my_pens = penalties[penalties['username'] == username].copy()
        if not my_pens.empty:
            my_pens['occurred_at'] = pd.to_datetime(my_pens['occurred_at'])
            
            for _, pen in my_pens.iterrows():
                # 惩罚日
                pen_date = pen['occurred_at']
                # 回溯7天窗口
                window_start = pen_date - pd.Timedelta(days=7)
                
                # 找到在这个窗口期内完成的任务
                # 逻辑：完成时间 >= 窗口开始 AND 完成时间 <= 惩罚日
                # (这意味着如果你在惩罚日之前拼命干活，这些活也会被抽成)
                window_tasks = my_done[
                    (my_done['completed_at'] >= window_start) & 
                    (my_done['completed_at'] <= pen_date)
                ]
                
                # 计算该窗口期的总产出 * 20%
                window_sum = window_tasks['val'].sum()
                fine = window_sum * 0.2
                total_fine += fine

    # 4. 净值
    net = gross_income - total_fine
    
    # 如果是查看特定时间段（如过去7天），我们要显示的通常是“那7天的产出”，
    # 但罚款怎么算？通常罚款是由于“行为”产生的。
    # 为了简化且逻辑自洽：
    # 个人面板显示的“过去7天/30天”仅显示【毛收入】(Gross)，
    # 而【总资产】显示的是扣除所有历史罚款后的【净资产】。
    
    if days_lookback:
        return round(gross_income, 2) # 短期榜单看爆发力（毛收入）
    else:
        return round(net, 2) # 总榜看积累（净收入）

# --- 4. 语录库 ---
QUOTES = [
    "痛苦是成长的属性。不要因为痛苦而逃避，要因为痛苦而兴奋。",
    "管理者的跃升，是从'对任务负责'到'对目标负责'。",
    "不要假装努力，结果不会陪你演戏。",
    "用系统工作的效率，对抗个体努力的瓶颈。",
    "没有执行力，一切战略都是空谈。",
    "将个体的能力固化为组织的系统，才是真正的熵减。"
]

ENCOURAGEMENTS = [
    "🔥 哪怕是一颗螺丝钉，也要拧得比别人紧！",
    "🚀 相信你的能力，这个任务非你莫属！",
    "💪 干就完了！期待你的完美交付。",
    "🌟 你的每一次交付，都在为颜祖帝国添砖加瓦。",
    "⚔️ 勇士，去征服这个挑战吧！"
]

# --- 5. 登录逻辑 (优化版) ---
if 'user' not in st.session_state:
    st.title("🏛️ 颜祖美学·云端执行中枢")
    st.caption("V14.0 Enterprise Edition")
    
    # 随机寄语
    st.markdown(f"> *{random.choice(QUOTES)}*")
    
    col1, col2 = st.columns(2)
    with col1:
        with st.form("login"):
            st.markdown("### 🔑 登录")
            u = st.text_input("用户名")
            p = st.text_input("密码", type="password")
            if st.form_submit_button("进入系统", type="primary"):
                # 优化报错逻辑：直接查，不乱抛异常
                res = supabase.table("users").select("*").eq("username", u).eq("password", p).execute()
                if res.data:
                    st.session_state.user = u
                    st.session_state.role = res.data[0]['role']
                    st.toast("欢迎回来，指挥官！", icon="🫡")
                    time.sleep(0.5)
                    st.rerun()
                else:
                    st.error("账号或密码错误")

    with col2:
        with st.expander("📝 新兵注册 / 加入"):
            nu = st.text_input("设置用户名")
            np = st.text_input("设置密码", type="password")
            if st.button("提交申请"):
                try:
                    supabase.table("users").insert({"username": nu, "password": np, "role": "member"}).execute()
                    st.success("注册成功！请登录。")
                except:
                    st.warning("该用户已存在")
    st.stop()

# --- 6. 主程序 ---
user = st.session_state.user
role = st.session_state.role

# === 侧边栏：个人中心 ===
with st.sidebar:
    st.title(f"👤 {user}")
    
    # 身份标牌
    if role == 'admin':
        st.info("👑 最高指挥官")
    else:
        st.success("⚔️ 核心成员")
    
    # 个人战绩 (区分逻辑)
    # 总榜：净收入（扣罚款）
    net_all = calculate_net_yvp(user, None)
    # 短期：毛收入（看近期产出能力）
    gross_7 = calculate_net_yvp(user, 7)
    gross_30 = calculate_net_yvp(user, 30)
    
    st.markdown("### 📊 个人战绩")
    col_a, col_b = st.columns(2)
    col_a.metric("过去7天", f"{gross_7}")
    col_b.metric("过去30天", f"{gross_30}")
    st.metric("🏆 净资产 (含罚款扣除)", f"💰 {net_all}")
    
    st.divider()
    
    # 修改密码功能 (新增功能4)
    with st.expander("🔐 修改密码"):
        new_pwd = st.text_input("新密码", type="password", key="sidebar_pwd")
        if st.button("确认修改"):
            supabase.table("users").update({"password": new_pwd}).eq("username", user).execute()
            st.success("密码已更新！")
            
    st.divider()
    if st.button("注销退出", type="secondary"):
        del st.session_state.user
        st.rerun()

# === 顶部导航 ===
# 使用 emoji 增强美观度
if role == 'admin':
    menu = ["👑 统帅控制台", "📋 任务大厅", "🗣️ 颜祖广场", "🏆 风云榜"]
else:
    menu = ["📋 任务大厅", "👤 我的战场", "🗣️ 颜祖广场", "🏆 风云榜"]
    
choice = st.sidebar.radio(" ", menu, label_visibility="collapsed")

# ================= 👑 管理员控制台 =================
if choice == "👑 统帅控制台" and role == 'admin':
    st.header("👑 最高统帅部")
    
    t1, t2, t3, t4, t5 = st.tabs(["🚀 发布", "📝 全局管理", "⚖️ 裁决", "👥 人员/密码", "💾 备份"])
    
    with t1:
        with st.container(border=True):
            st.subheader("下达新指令")
            c1, c2 = st.columns(2)
            title = c1.text_input("任务名称")
            deadline = c1.date_input("截止日期")
            desc = st.text_area("详细说明 (DoD标准)")
            
            d = c2.number_input("难度系数 (D)", 1.0, step=0.1)
            t = c2.number_input("标准工时 (T)", 1.0, step=0.5)
            ttype = c2.radio("类型", ["公共任务池", "指定指派"], horizontal=True)
            
            assignee = "待定"
            if ttype == "指定指派":
                udf = run_query("users")
                if not udf.empty:
                    mems = udf[udf['role']!='admin']['username'].tolist()
                    assignee = st.selectbox("指派给", mems)
            
            if st.button("🚀 发布指令", type="primary"):
                status = "待领取" if ttype == "公共任务池" else "进行中"
                final_a = assignee if ttype == "指定指派" else "待定"
                supabase.table("tasks").insert({
                    "title": title, "description": desc, "difficulty": d, "std_time": t,
                    "status": status, "assignee": final_a, "deadline": str(deadline),
                    "type": ttype, "feedback": ""
                }).execute()
                st.success("指令已下达！")

    with t2: # 全局管理 (含修改已完成任务)
        st.subheader("🛠️ 任务修正 (含已完成)")
        tasks_df = run_query("tasks")
        
        if not tasks_df.empty:
            # 搜索与筛选
            search = st.text_input("🔍 搜索任务标题/人员")
            if search:
                tasks_df = tasks_df[tasks_df['title'].str.contains(search) | tasks_df['assignee'].str.contains(search)]
                
            task_id = st.selectbox("选择要操作的任务", tasks_df['id'], format_func=lambda x: f"ID {x} - {tasks_df[tasks_df['id']==x]['title'].values[0]}")
            curr = tasks_df[tasks_df['id']==task_id].iloc[0]
            
            with st.container(border=True):
                c_edit1, c_edit2 = st.columns(2)
                e_title = c_edit1.text_input("标题", curr['title'])
                e_diff = c_edit1.number_input("难度", value=float(curr['difficulty']))
                e_qual = c_edit1.number_input("质量系数 (可修正已完成)", value=float(curr['quality']), step=0.1)
                
                e_status = c_edit2.selectbox("状态", ["待领取", "进行中", "待验收", "完成", "返工"], index=["待领取", "进行中", "待验收", "完成", "返工"].index(curr['status']) if curr['status'] in ["待领取", "进行中", "待验收", "完成", "返工"] else 0)
                e_assignee = c_edit2.text_input("执行人", curr['assignee'])
                e_fb = st.text_area("反馈/御批", curr.get('feedback', ''))
                
                col_save, col_del = st.columns([1, 4])
                if col_save.button("💾 保存修正"):
                    supabase.table("tasks").update({
                        "title": e_title, "difficulty": e_diff, "quality": e_qual,
                        "status": e_status, "assignee": e_assignee, "feedback": e_fb
                    }).eq("id", int(task_id)).execute()
                    st.success("已修正！")
                    time.sleep(1)
                    st.rerun()
                    
                if col_del.button("🗑️ 删除任务"):
                    supabase.table("tasks").delete().eq("id", int(task_id)).execute()
                    st.rerun()

    with t3: # 裁决
        pend = run_query("tasks")
        if not pend.empty: pend = pend[pend['status'] == '待验收']
        
        if not pend.empty:
            tid = st.selectbox("待审任务", pend['id'], format_func=lambda x: f"ID {x} - {pend[pend['id']==x]['title'].values[0]}")
            curr = pend[pend['id']==tid].iloc[0]
            
            with st.container(border=True):
                st.markdown(f"**{curr['title']}**")
                st.caption(f"执行人: {curr['assignee']} | 截止: {curr['deadline']}")
                
                c_q, c_r = st.columns([1, 2])
                q = c_q.slider("质量系数", 0.0, 3.0, 1.0, 0.1)
                fb = c_r.text_area("御批 (理由)", placeholder="必填...")
                res = c_r.selectbox("结果", ["完成", "返工"])
                
                if st.button("⚖️ 提交裁决", type="primary"):
                    if not fb:
                        st.error("请填写理由")
                    else:
                        comp_at = str(datetime.date.today()) if res == "完成" else None
                        supabase.table("tasks").update({
                            "quality": q, "status": res, "feedback": fb, "completed_at": comp_at
                        }).eq("id", int(tid)).execute()
                        st.success("裁决生效")
                        time.sleep(1)
                        st.rerun()
        else:
            st.info("暂无待验收任务")

    with t4: # 人员与密码管理 (新增功能4)
        st.subheader("👥 成员管理")
        udf = run_query("users")
        
        # 惩罚区
        with st.expander("🚨 军法处置 (缺勤记录)", expanded=True):
            if not udf.empty:
                mems = udf[udf['role']!='admin']['username'].tolist()
                target = st.selectbox("违规人员", mems)
                if st.button("🚨 记录缺勤 (触发滑动扣款)"):
                    supabase.table("penalties").insert({
                        "username": target, "occurred_at": str(datetime.date.today()), "reason": "缺勤"
                    }).execute()
                    st.success(f"已记录。系统将自动扣除 {target} 过去7天产出的20%。")

        st.divider()
        
        # 密码重置区
        st.subheader("🔑 密码重置")
        c_u, c_p = st.columns([2, 2])
        target_u = c_u.selectbox("选择成员", udf['username'].tolist())
        new_pass_admin = c_p.text_input("设置新密码", key="admin_reset_pwd")
        if st.button("强制重置密码"):
            supabase.table("users").update({"password": new_pass_admin}).eq("username", target_u).execute()
            st.success(f"{target_u} 的密码已重置。")

    with t5: # 备份
        st.subheader("💾 数据方舟")
        df_u = run_query("users")
        df_t = run_query("tasks")
        df_p = run_query("penalties")
        df_m = run_query("messages")
        
        csv_buffer = io.StringIO()
        csv_buffer.write("===USERS===\n")
        df_u.to_csv(csv_buffer, index=False)
        csv_buffer.write("\n===TASKS===\n")
        df_t.to_csv(csv_buffer, index=False)
        csv_buffer.write("\n===PENALTIES===\n")
        df_p.to_csv(csv_buffer, index=False)
        csv_buffer.write("\n===MESSAGES===\n")
        df_m.to_csv(csv_buffer, index=False)
        
        st.download_button("📥 下载全量备份", csv_buffer.getvalue(), f"backup_{datetime.date.today()}.txt")

# ================= 📋 任务大厅 (美化版) =================
elif choice == "📋 任务大厅":
    st.header("🛡️ 任务大厅")
    
    tasks = run_query("tasks")
    
    # 1. 公共池
    st.subheader("🔥 待抢任务")
    if not tasks.empty:
        pool = tasks[(tasks['status'] == '待领取') & (tasks['type'] == '公共任务池')]
        if not pool.empty:
            cols = st.columns(3) # 卡片式布局
            for i, (idx, r) in enumerate(pool.iterrows()):
                with cols[i % 3]:
                    with st.container(border=True):
                        st.markdown(f"**{r['title']}**")
                        st.markdown(f"💰 **{round(r['difficulty'] * r['std_time'], 2)}** | 难度 {r['difficulty']}")
                        st.caption(f"截止: {r.get('deadline', '无')}")
                        st.text(r.get('description', '')[:50] + "...")
                        
                        if role != 'admin':
                            if st.button("⚡️ 抢单", key=f"take_{r['id']}", type="primary"):
                                supabase.table("tasks").update({"status": "进行中", "assignee": user}).eq("id", int(r['id'])).execute()
                                # 随机鼓励 (新增功能7)
                                st.toast(random.choice(ENCOURAGEMENTS), icon="🔥")
                                time.sleep(1)
                                st.rerun()
        else:
            st.info("暂无公共任务")
    
    st.divider()
    
    # 2. 全军动态
    st.subheader("🔭 实时看板")
    if not tasks.empty:
        active = tasks[tasks['status'].isin(['进行中', '返工', '待验收'])]
        if not active.empty:
            st.dataframe(
                active[['title', 'assignee', 'status', 'deadline']], 
                use_container_width=True,
                hide_index=True
            )
        else:
            st.caption("全军休整中")

    st.divider()
    
    # 3. 荣誉榜
    st.subheader("📜 完工御批")
    if not tasks.empty:
        done = tasks[tasks['status'] == '完成']
        if not done.empty:
            done['YVP'] = done['difficulty'] * done['std_time'] * done['quality']
            st.dataframe(
                done[['title', 'assignee', 'YVP', 'feedback', 'completed_at']], 
                use_container_width=True,
                hide_index=True
            )

# ================= 👤 我的战场 =================
elif choice == "👤 我的战场":
    st.header("⚔️ 我的战场")
    tasks = run_query("tasks")
    
    if not tasks.empty:
        my = tasks[(tasks['assignee'] == user) & (tasks['status'] == '进行中')]
        if not my.empty:
            for i, r in my.iterrows():
                with st.container(border=True):
                    c1, c2 = st.columns([4, 1])
                    with c1:
                        st.subheader(r['title'])
                        st.markdown(f"**详情**: {r.get('description', '')}")
                        st.caption(f"截止: {r.get('deadline', '无')} | 难度: {r['difficulty']}")
                    with c2:
                        st.write("") # Spacer
                        if st.button("✅ 提交验收", key=r['id'], type="primary"):
                            supabase.table("tasks").update({"status": "待验收"}).eq("id", int(r['id'])).execute()
                            st.balloons()
                            st.success("已提交！")
                            time.sleep(1)
                            st.rerun()
        else:
            st.info("暂无任务，去大厅抢单吧！")

# ================= 🗣️ 颜祖广场 (新增功能5) =================
elif choice == "🗣️ 颜祖广场":
    st.header("🗣️ 颜祖广场")
    st.caption("分享认知，发布感想，互相鼓励。")
    
    # 发布区
    with st.expander("✍️ 发布新寄语", expanded=False):
        msg_content = st.text_area("写下你的想法...", height=100)
        if st.button("发布寄语"):
            if msg_content:
                supabase.table("messages").insert({
                    "username": user, 
                    "content": msg_content,
                    "created_at": str(datetime.datetime.now())
                }).execute()
                st.success("发布成功！")
                st.rerun()
    
    # 展示区
    msgs = run_query("messages")
    if not msgs.empty:
        # 按时间倒序
        msgs = msgs.sort_values("created_at", ascending=False)
        for i, m in msgs.iterrows():
            with st.chat_message("user", avatar="👤"):
                st.markdown(f"**{m['username']}** 说：")
                st.write(m['content'])
                st.caption(f"发表于 {m['created_at']}")
    else:
        st.write("还没有人发言，做第一个吧！")

# ================= 🏆 风云榜 =================
elif choice == "🏆 风云榜":
    st.header("🏆 颜祖富豪榜")
    
    users = run_query("users")
    if not users.empty:
        mems = users[users['role'] != 'admin']['username'].tolist()
        
        def get_data(lookback):
            data = []
            for m in mems:
                # 短期榜单看产出(Gross)，总榜看净值(Net)
                # 但 V14.0 逻辑中，calculate_net_yvp 已经处理了这个区分
                val = calculate_net_yvp(m, lookback)
                data.append({"成员": m, "YVP": val})
            return pd.DataFrame(data).sort_values("YVP", ascending=False)

        t1, t2, t3 = st.tabs(["📅 7天冲刺榜", "🗓️ 月度考核榜", "🔥 历史总榜"])
        
        with t1: st.dataframe(get_data(7), use_container_width=True, hide_index=True)
        with t2: st.dataframe(get_data(30), use_container_width=True, hide_index=True)
        with t3: st.dataframe(get_data(None), use_container_width=True, hide_index=True)
