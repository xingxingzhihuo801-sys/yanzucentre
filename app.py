import streamlit as st
import pandas as pd
import datetime
import time
import io
import random  # <--- 陛下，补上了这个关键的工具包
from supabase import create_client, Client

# --- 系统配置 ---
st.set_page_config(page_title="颜祖美学·执行中枢 V13.1", layout="wide")

# --- 1. 连接 Supabase 云端数据库 ---
try:
    url = st.secrets["supabase"]["url"]
    key = st.secrets["supabase"]["key"]
    supabase: Client = create_client(url, key)
except Exception as e:
    st.error("🚨 数据库连接失败！请检查 Streamlit Secrets 配置。")
    st.stop()

# --- 2. 核心工具函数 ---
def run_query(table_name):
    """获取全量数据并转换为 DataFrame，自动处理日期格式"""
    try:
        response = supabase.table(table_name).select("*").execute()
        df = pd.DataFrame(response.data)
        if not df.empty:
            # 自动识别并转换日期列
            for col in ['created_at', 'deadline', 'completed_at', 'occurred_at']:
                if col in df.columns:
                    df[col] = pd.to_datetime(df[col], errors='coerce').dt.date
        return df
    except Exception as e:
        return pd.DataFrame()

def calculate_yvp(username, days=None):
    """
    计算特定时间段内的 YVP
    逻辑：(总产出) * (1 - 惩罚系数)
    注意：惩罚系数计算该时间段内的惩罚次数
    """
    # 1. 获取任务数据
    tasks = run_query("tasks")
    if tasks.empty:
        return 0.0

    # 筛选：指定人 + 已完成
    mask_user = (tasks['assignee'] == username) & (tasks['status'] == '完成')
    
    # 筛选：时间范围
    if days:
        cutoff = datetime.date.today() - datetime.timedelta(days=days)
        # 确保 completed_at 是日期对象
        # 如果是 NAT (无效时间) 则不参与计算
        if 'completed_at' in tasks.columns:
            mask_time = tasks['completed_at'] >= cutoff
            user_tasks = tasks[mask_user & mask_time]
        else:
            return 0.0
    else:
        user_tasks = tasks[mask_user]

    # 计算毛收入
    gross = 0.0
    if not user_tasks.empty:
        gross = (user_tasks['difficulty'] * user_tasks['std_time'] * user_tasks['quality']).sum()

    # 2. 获取惩罚数据
    pens = run_query("penalties")
    pen_cnt = 0
    if not pens.empty:
        mask_pen_user = pens['username'] == username
        if days:
            cutoff = datetime.date.today() - datetime.timedelta(days=days)
            if 'occurred_at' in pens.columns:
                mask_pen_time = pens['occurred_at'] >= cutoff
                pen_cnt = len(pens[mask_pen_user & mask_pen_time])
        else:
            pen_cnt = len(pens[mask_pen_user])

    # 3. 计算净值 (每次惩罚扣 20%)
    net = gross * (1 - min(pen_cnt * 0.2, 1.0))
    return round(net, 2)

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
    st.caption("Data Secured by Supabase™ | V13.1")
    
    # 这里现在肯定不会报错了，因为 random 已经导入
    st.info(f"🔥 {random.choice(QUOTES)}")
    
    col1, col2 = st.columns(2)
    with col1:
        with st.form("login"):
            u = st.text_input("用户名")
            p = st.text_input("密码", type="password")
            if st.form_submit_button("🚀 进入系统"):
                try:
                    response = supabase.table("users").select("*").eq("username", u).eq("password", p).execute()
                    if response.data:
                        st.session_state.user = u
                        st.session_state.role = response.data[0]['role']
                        st.toast("身份确认，正在载入...", icon="✅")
                        time.sleep(1)
                        st.rerun()
                    else:
                        st.error("身份验证失败")
                except:
                    st.error("网络连接异常")

    with col2:
        with st.expander("📝 新兵注册通道"):
            nu = st.text_input("用户名")
            np = st.text_input("密码", type="password")
            if st.button("提交注册"):
                try:
                    supabase.table("users").insert({"username": nu, "password": np, "role": "member"}).execute()
                    st.success("注册成功！请登录。")
                except:
                    st.warning("用户已存在")
    st.stop()

# --- 5. 主程序结构 ---
user = st.session_state.user
role = st.session_state.role

# === 侧边栏：个人战绩 (新增功能4) ===
st.sidebar.title(f"👤 {user}")
if role == 'admin':
    st.sidebar.caption("👑 最高指挥官")
else:
    st.sidebar.caption("⚔️ 核心成员")
    
    # 获取三个维度的数据
    yvp_7 = calculate_yvp(user, 7)
    yvp_30 = calculate_yvp(user, 30)
    yvp_all = calculate_yvp(user, None)
    
    st.sidebar.markdown("### 📊 个人战绩")
    st.sidebar.metric("📅 过去 7 天", f"💰 {yvp_7}")
    st.sidebar.metric("🗓️ 过去 30 天", f"💰 {yvp_30}")
    st.sidebar.metric("🏆 历史总计", f"💰 {yvp_all}")

st.sidebar.divider()
if st.sidebar.button("注销"):
    del st.session_state.user
    st.rerun()

# 导航
if role == 'admin':
    menu = ["👑 核心控制台", "📋 任务大厅", "🏆 颜祖风云榜"]
else:
    menu = ["📋 任务大厅", "👤 我的任务", "🏆 颜祖风云榜"]
choice = st.sidebar.radio("导航", menu)

# ================= 👑 管理员控制台 =================
if choice == "👑 核心控制台" and role == 'admin':
    st.header("👑 最高统帅部")
    t1, t2, t3, t4, t5 = st.tabs(["🚀 发布", "📝 任务管理(增删改)", "⚖️ 裁决", "🚨 惩罚", "💾 备份与人员"])
    
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
        
        if st.button("🚀 下达指令"):
            status = "待领取" if ttype == "公共任务池" else "进行中"
            final_a = assignee if ttype == "指定指派" else "待定"
            supabase.table("tasks").insert({
                "title": title, "description": desc, "difficulty": d, "std_time": t,
                "status": status, "assignee": final_a, "deadline": str(deadline),
                "type": ttype, "feedback": ""
            }).execute()
            st.success("发布成功！")

    with t2: # 任务管理 (新增功能1：编辑和删除)
        st.subheader("🛠️ 全局任务修正")
        st.info("此处可编辑或删除系统内任何任务（包括已完成的）。")
        
        tasks_df = run_query("tasks")
        if not tasks_df.empty:
            # 筛选器
            status_list = list(tasks_df['status'].unique()) if 'status' in tasks_df.columns else []
            if status_list:
                filter_status = st.multiselect("筛选状态", status_list, default=status_list)
                filtered_df = tasks_df[tasks_df['status'].isin(filter_status)]
            else:
                filtered_df = tasks_df
            
            if not filtered_df.empty:
                task_id = st.selectbox("选择要操作的任务", filtered_df['id'], format_func=lambda x: f"ID {x} - {filtered_df[filtered_df['id']==x]['title'].values[0]}")
                
                # 获取当前任务详情
                curr_task = filtered_df[filtered_df['id']==task_id].iloc[0]
                
                with st.expander("📝 编辑任务详情", expanded=True):
                    with st.form("edit_form"):
                        e_title = st.text_input("标题", curr_task['title'])
                        e_desc = st.text_area("描述", curr_task.get('description', ''))
                        c_e1, c_e2 = st.columns(2)
                        e_d = c_e1.number_input("难度", value=float(curr_task['difficulty']))
                        e_t = c_e2.number_input("工时", value=float(curr_task['std_time']))
                        
                        all_status = ["待领取", "进行中", "待验收", "完成", "返工"]
                        current_status_idx = 0
                        if curr_task['status'] in all_status:
                            current_status_idx = all_status.index(curr_task['status'])
                        e_status = st.selectbox("状态", all_status, index=current_status_idx)
                        
                        e_assignee = st.text_input("执行人", curr_task['assignee'])
                        
                        col_save, col_del = st.columns([1,5])
                        if col_save.form_submit_button("💾 保存修改"):
                            supabase.table("tasks").update({
                                "title": e_title, "description": e_desc, "difficulty": e_d,
                                "std_time": e_t, "status": e_status, "assignee": e_assignee
                            }).eq("id", int(task_id)).execute()
                            st.success("修改已保存！")
                            time.sleep(1)
                            st.rerun()
                            
                        if col_del.form_submit_button("🗑️ 永久删除", type="primary"):
                            supabase.table("tasks").delete().eq("id", int(task_id)).execute()
                            st.warning("任务已删除！")
                            time.sleep(1)
                            st.rerun()
            else:
                st.info("筛选条件下无任务")
        else:
            st.info("系统暂无任务")

    with t3: # 裁决
        pend = run_query("tasks")
        if not pend.empty:
            pend = pend[pend['status'] == '待验收']
        
        if not pend.empty:
            tid = st.selectbox("待审任务", pend['id'], format_func=lambda x: f"ID {x} - {pend[pend['id']==x]['title'].values[0]}")
            curr = pend[pend['id']==tid].iloc[0]
            st.info(f"执行人: {curr['assignee']} | 预估: {round(curr['difficulty']*curr['std_time'], 2)}")
            
            q = st.slider("质量系数", 0.0, 3.0, 1.0, 0.1)
            fb = st.text_area("御批 (理由)", placeholder="必填...")
            res = st.selectbox("结果", ["完成", "返工"])
            
            if st.button("提交裁决"):
                comp_at = str(datetime.date.today()) if res == "完成" else None
                supabase.table("tasks").update({
                    "quality": q, "status": res, "feedback": fb, "completed_at": comp_at
                }).eq("id", int(tid)).execute()
                st.success("裁决生效")
                time.sleep(1)
                st.rerun()
        else:
            st.info("无待验收任务")

    with t4: # 惩罚
        udf = run_query("users")
        if not udf.empty:
            mems = udf[udf['role']!='admin']['username'].tolist()
            target = st.selectbox("违规人员", mems)
            if st.button("🚨 记录缺勤"):
                supabase.table("penalties").insert({
                    "username": target, "occurred_at": str(datetime.date.today()), "reason": "缺勤"
                }).execute()
                st.success(f"{target} 已受罚")
        st.dataframe(run_query("penalties"))

    with t5: # 备份与人员 (新增功能2)
        st.subheader("💾 数据备份")
        st.info("点击下方按钮下载所有数据，以防更新时丢失。")
        
        # 获取所有数据
        df_u = run_query("users")
        df_t = run_query("tasks")
        df_p = run_query("penalties")
        
        # 转换为 CSV
        csv_buffer = io.StringIO()
        csv_buffer.write("===USERS===\n")
        df_u.to_csv(csv_buffer, index=False)
        csv_buffer.write("\n===TASKS===\n")
        df_t.to_csv(csv_buffer, index=False)
        csv_buffer.write("\n===PENALTIES===\n")
        df_p.to_csv(csv_buffer, index=False)
        
        st.download_button(
            label="📥 下载全量数据备份 (.txt)",
            data=csv_buffer.getvalue(),
            file_name=f"yanzu_backup_{datetime.date.today()}.txt",
            mime="text/plain"
        )
        
        st.divider()
        st.subheader("👥 人员列表")
        for i, r in df_u.iterrows():
            if r['role'] != 'admin':
                c1, c2 = st.columns([3, 1])
                c1.write(f"{r['username']}")
                if c2.button("驱逐", key=r['username']):
                    supabase.table("users").delete().eq("username", r['username']).execute()
                    st.rerun()

# ================= 📋 任务大厅 (全员可见) =================
elif choice == "📋 任务大厅":
    st.header("🛡️ 任务大厅")
    
    # 1. 公共池
    st.subheader("🔥 公共任务池 (待抢)")
    tasks = run_query("tasks")
    if not tasks.empty:
        pool = tasks[(tasks['status'] == '待领取') & (tasks['type'] == '公共任务池')]
        if not pool.empty:
            for i, r in pool.iterrows():
                val = round(r['difficulty'] * r['std_time'], 2)
                with st.expander(f"💰 {val} | {r['title']}"):
                    st.write(f"详情: {r.get('description', '')}")
                    st.write(f"截止: {r.get('deadline', '')}")
                    if role != 'admin':
                        if st.button(f"⚡️ 抢单", key=f"take_{r['id']}"):
                            supabase.table("tasks").update({"status": "进行中", "assignee": user}).eq("id", int(r['id'])).execute()
                            st.rerun()
        else:
            st.info("暂无公共任务")
    
    st.divider()
    
    # 2. 全员正在进行的任务 (新增功能3：所有人可见)
    st.subheader("🔭 全军执行动态")
    if not tasks.empty:
        # 显示所有正在进行或待验收的任务，无论指派给谁
        active_tasks = tasks[tasks['status'].isin(['进行中', '返工', '待验收', '待领取'])]
        # 过滤掉公共任务池的待领取，只保留指派的和正在做的
        active_display = active_tasks[~((active_tasks['status'] == '待领取') & (active_tasks['type'] == '公共任务池'))]
        
        if not active_display.empty:
            # 简化显示列
            cols_to_show = ['title', 'assignee', 'status', 'deadline', 'difficulty']
            # 确保列存在
            final_cols = [c for c in cols_to_show if c in active_display.columns]
            
            st.dataframe(
                active_display[final_cols], 
                use_container_width=True,
                hide_index=True
            )
        else:
            st.caption("全军休整中...")

    st.divider()
    
    # 3. 完工记录
    st.subheader("📜 历史荣誉榜")
    if not tasks.empty:
        done = tasks[tasks['status'] == '完成']
        if not done.empty:
            # 计算实际获得
            done['YVP'] = done['difficulty'] * done['std_time'] * done['quality']
            
            cols_to_show = ['title', 'assignee', 'completed_at', 'YVP', 'feedback']
            final_cols = [c for c in cols_to_show if c in done.columns]
            
            st.dataframe(done[final_cols], use_container_width=True)

# ================= 👤 我的任务 =================
elif choice == "👤 我的任务":
    st.header("⚔️ 我的战场")
    tasks = run_query("tasks")
    if not tasks.empty:
        my = tasks[(tasks['assignee'] == user) & (tasks['status'] == '进行中')]
        if not my.empty:
            for i, r in my.iterrows():
                with st.container(border=True):
                    c1, c2 = st.columns([3, 1])
                    c1.write(f"**{r['title']}**")
                    c1.caption(f"截止: {r.get('deadline', '')}")
                    if c2.button("✅ 提交验收", key=r['id']):
                        supabase.table("tasks").update({"status": "待验收"}).eq("id", int(r['id'])).execute()
                        st.success("已提交！")
                        time.sleep(1)
                        st.rerun()
        else:
            st.info("暂无进行中任务")

# ================= 🏆 风云榜 (新增功能5：多维榜单) =================
elif choice == "🏆 颜祖风云榜":
    st.header("🏆 颜祖富豪榜")
    
    users = run_query("users")
    if not users.empty:
        mems = users[users['role'] != 'admin']['username'].tolist()
        
        # 定义生成榜单数据的函数
        def get_leaderboard_data(days):
            data = []
            for m in mems:
                yvp = calculate_yvp(m, days)
                data.append({"成员": m, "YVP": yvp})
            return pd.DataFrame(data).sort_values("YVP", ascending=False)

        # 选项卡
        tab_7, tab_30, tab_all = st.tabs(["📅 过去 7 天", "🗓️ 过去 30 天", "🔥 历史总榜"])
        
        with tab_7:
            st.caption("最近一周表现最强战力")
            st.dataframe(get_leaderboard_data(7), use_container_width=True, hide_index=True)
            
        with tab_30:
            st.caption("月度考核参考")
            st.dataframe(get_leaderboard_data(30), use_container_width=True, hide_index=True)
            
        with tab_all:
            st.caption("颜祖帝国开国至今总排行")
            st.dataframe(get_leaderboard_data(None), use_container_width=True, hide_index=True)
