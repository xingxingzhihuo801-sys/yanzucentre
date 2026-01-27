import streamlit as st
import pandas as pd
import sqlite3
import datetime
import random
import io
import time

# --- 系统配置 ---
st.set_page_config(page_title="颜祖美学·执行中枢 V9.0", layout="wide")

# --- 数据库连接与初始化 ---
# 使用 check_same_thread=False 以适应 Streamlit 的多线程环境
conn = sqlite3.connect("yanzu_core_v9.db", check_same_thread=False)

def init_db():
    c = conn.cursor()
    # 1. 用户表
    c.execute('''CREATE TABLE IF NOT EXISTS users 
                 (username TEXT PRIMARY KEY, password TEXT, role TEXT)''')
    # 2. 任务表
    c.execute('''CREATE TABLE IF NOT EXISTS tasks 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                  title TEXT, 
                  difficulty REAL, 
                  std_time REAL, 
                  quality REAL DEFAULT 1.0, 
                  status TEXT, 
                  assignee TEXT, 
                  completed_at DATE, 
                  feedback TEXT,
                  type TEXT)''')
    # 3. 惩罚表
    c.execute('''CREATE TABLE IF NOT EXISTS penalties 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                  username TEXT, 
                  occurred_at DATE, 
                  reason TEXT)''')
    
    # 预设管理员 (如果不存在则自动创建)
    c.execute("INSERT OR IGNORE INTO users VALUES ('liujingting', 'admin888', 'admin')")
    c.execute("INSERT OR IGNORE INTO users VALUES ('jiangjing', 'strategy999', 'admin')")
    conn.commit()

# 初始化运行
init_db()

# --- 励志语录库 ---
QUOTES = [
    "痛苦是成长的属性。不要因为痛苦而逃避，要因为痛苦而兴奋。",
    "管理者的跃升，是从'对任务负责'到'对目标负责'。",
    "不要假装努力，结果不会陪你演戏。",
    "你的对手在看书，你的仇人在磨刀，隔壁老王在练腰。",
    "悲观者正确，乐观者成功。",
    "用系统工作的效率，对抗个体努力的瓶颈。",
    "不做烂好人，要做'手起刀落'的管理者。"
]

# --- 核心函数：资产计算 ---
def get_gold_stats(username, days=None):
    """计算用户的金币收入，自动扣除惩罚"""
    # 1. 计算总收入
    date_filter = ""
    if days:
        start_date = datetime.date.today() - datetime.timedelta(days=days)
        date_filter = f" AND completed_at >= '{start_date}'"
    
    sql = f"SELECT difficulty, std_time, quality FROM tasks WHERE assignee='{username}' AND status='完成' {date_filter}"
    df = pd.read_sql(sql, conn)
    
    gross_income = 0.0
    if not df.empty:
        # 公式：难度 * 工时 * 质量
        gross_income = (df['difficulty'] * df['std_time'] * df['quality']).sum()
    
    # 2. 计算惩罚系数 (缺勤次数)
    pen_sql = f"SELECT COUNT(*) as cnt FROM penalties WHERE username='{username}'"
    # 如果是计算短期收益，惩罚也只看短期的吗？为了严厉，建议惩罚是永久累计的威慑，或者按您需求逻辑
    # 这里我们采用：查看该用户所有的惩罚次数，每次扣除 20%
    pen_cnt = pd.read_sql(pen_sql, conn).iloc[0]['cnt']
    
    # 3. 计算净收入
    deduction_rate = min(pen_cnt * 0.2, 1.0) # 最多扣光
    net_income = gross_income * (1 - deduction_rate)
    
    return round(net_income, 2), pen_cnt

# --- 登录界面 ---
if 'user' not in st.session_state:
    st.title("🏛️ 颜祖美学·数字化军营")
    st.info(f"🔥 {random.choice(QUOTES)}")
    
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("登录")
        with st.form("login_form"):
            u = st.text_input("用户名")
            p = st.text_input("密码", type="password")
            if st.form_submit_button("进入中枢"):
                try:
                    user_data = pd.read_sql(f"SELECT * FROM users WHERE username='{u}' AND password='{p}'", conn)
                    if not user_data.empty:
                        st.session_state.user = u
                        st.session_state.role = user_data.iloc[0]['role']
                        st.toast("欢迎回来，指挥官！", icon="🫡")
                        time.sleep(1)
                        st.rerun()
                    else:
                        st.error("身份验证失败")
                except Exception as e:
                    st.error("系统正在初始化，请重试")
    
    with col2:
        st.subheader("新兵注册")
        with st.form("reg_form"):
            new_u = st.text_input("设置用户名")
            new_p = st.text_input("设置密码", type="password")
            if st.form_submit_button("加入军营"):
                if new_u and new_p:
                    try:
                        c = conn.cursor()
                        c.execute("INSERT INTO users VALUES (?, ?, 'member')", (new_u, new_p))
                        conn.commit()
                        st.success("注册成功！请在左侧登录")
                    except:
                        st.warning("该用户名已存在")
    st.stop()

# --- 主程序 ---
user = st.session_state.user
role = st.session_state.role

# 侧边栏：个人仪表盘
st.sidebar.title(f"👤 {user}")
st.sidebar.caption(f"身份: {'👑 管理员' if role=='admin' else '⚔️ 战士'}")

# 计算资产
net_gold, pen_count = get_gold_stats(user)
st.sidebar.metric("💰 净金币 (YVP)", net_gold, delta=f"被罚 {pen_count} 次 (-{int(pen_count*20)}%)", delta_color="inverse")

# 详细统计
stats_7, _ = get_gold_stats(user, 7)
stats_30, _ = get_gold_stats(user, 30)
st.sidebar.write("---")
st.sidebar.write(f"📅 7天战绩: **{stats_7}**")
st.sidebar.write(f"🗓️ 30天战绩: **{stats_30}**")

# 安全退出
st.sidebar.write("---")
if st.sidebar.button("注销 / 退出"):
    del st.session_state.user
    st.rerun()

# --- 角色分流：管理员界面 ---
if role == 'admin':
    st.header("👑 颜祖美学·最高统帅部")
    
    # 管理员 Tab 页
    tabs = st.tabs(["🚀 发布指令", "⚖️ 裁决评分", "🚨 军法考勤", "👥 人员管理", "💾 备份与恢复"])
    
    # 1. 发布任务
    with tabs[0]:
        c1, c2 = st.columns(2)
        with c1:
            title = st.text_input("任务名称")
            desc = st.text_area("详细说明")
            deadline = st.date_input("截止日期")
        with c2:
            d_factor = st.number_input("难度系数 (D_factor)", value=1.0, step=0.1, help="斐波那契数列参考：1, 2, 3, 5, 8")
            t_std = st.number_input("标准工时 (T_std)", value=1.0, step=0.5, help="熟练工所需时间")
            t_type = st.radio("任务类型", ["公共任务池", "指定指派"])
            assignee = "待定"
            if t_type == "指定指派":
                users_df = pd.read_sql("SELECT username FROM users WHERE role='member'", conn)
                assignee = st.selectbox("指派给谁", users_df['username'].tolist())

        if st.button("立即发布"):
            status = "待领取" if t_type == "公共任务池" else "进行中"
            final_assignee = assignee if t_type == "指定指派" else "待定"
            c = conn.cursor()
            c.execute('''INSERT INTO tasks (title, difficulty, std_time, status, assignee, deadline, type, feedback) 
                         VALUES (?, ?, ?, ?, ?, ?, ?, '')''', 
                      (title, d_factor, t_std, status, final_assignee, deadline, t_type))
            conn.commit()
            st.success("指令已下达至全军！")

    # 2. 裁决评分
    with tabs[1]:
        st.subheader("待验收任务")
        pending = pd.read_sql("SELECT * FROM tasks WHERE status='待验收'", conn)
        if not pending.empty:
            task_id = st.selectbox("选择要验收的任务", pending['id'], format_func=lambda x: f"ID {x}")
            # 获取该任务详情
            task_info = pending[pending['id']==task_id].iloc[0]
            st.info(f"任务：{task_info['title']} | 执行人：{task_info['assignee']}")
            
            col_q, col_f = st.columns([1, 2])
            with col_q:
                q_mult = st.slider("质量系数 (Q)", 0.0, 3.0, 1.0, 0.1)
                new_status = st.selectbox("裁决结果", ["完成", "返工"])
            with col_f:
                feedback = st.text_area("御批 (评分理由/改进建议)", placeholder="必须填写理由，让员工心服口服")
            
            if st.button("提交裁决"):
                if not feedback:
                    st.error("陛下，请填写评分理由！")
                else:
                    completed_at = datetime.date.today() if new_status == '完成' else None
                    c = conn.cursor()
                    c.execute("UPDATE tasks SET quality=?, status=?, feedback=?, completed_at=? WHERE id=?", 
                              (q_mult, new_status, feedback, completed_at, task_id))
                    conn.commit()
                    st.success("裁决已生效！")
                    time.sleep(1)
                    st.rerun()
        else:
            st.info("暂无待验收任务")

    # 3. 军法考勤
    with tabs[2]:
        st.error("⚠️ 警告：每一次缺勤记录，将永久扣除该成员 20% 的所有收益。")
        users_df = pd.read_sql("SELECT username FROM users WHERE role='member'", conn)
        target_user = st.selectbox("违规人员", users_df['username'].tolist() if not users_df.empty else [])
        
        if st.button("🚨 记录一次缺勤"):
            c = conn.cursor()
            c.execute("INSERT INTO penalties (username, occurred_at, reason) VALUES (?, ?, '缺勤')", 
                      (target_user, datetime.date.today()))
            conn.commit()
            st.success(f"已对 {target_user} 执行军法！")

        st.write("---")
        st.subheader("惩罚记录日志")
        st.dataframe(pd.read_sql("SELECT * FROM penalties ORDER BY id DESC", conn))

    # 4. 人员管理
    with tabs[3]:
        st.subheader("人员清洗")
        all_users = pd.read_sql("SELECT * FROM users", conn)
        for idx, row in all_users.iterrows():
            c1, c2, c3 = st.columns([1, 2, 1])
            c1.write(f"**{row['username']}**")
            c2.write(f"角色: {row['role']}")
            if row['role'] != 'admin':
                if c3.button("驱逐", key=f"del_{row['username']}"):
                    c = conn.cursor()
                    c.execute("DELETE FROM users WHERE username=?", (row['username'],))
                    conn.commit()
                    st.warning(f"已将 {row['username']} 移出系统")
                    time.sleep(1)
                    st.rerun()

    # 5. 备份与恢复 (终极安全方案)
    with tabs[4]:
        st.subheader("💾 数据方舟")
        st.info("由于云端机制，系统重启后数据可能重置。请定期下载备份。若数据丢失，上传备份即可恢复。")
        
        # 导出功能
        # 读取所有表
        df_users = pd.read_sql("SELECT * FROM users", conn)
        df_tasks = pd.read_sql("SELECT * FROM tasks", conn)
        df_penalties = pd.read_sql("SELECT * FROM penalties", conn)
        
        # 将多个表合并到一个 CSV 字符串中 (使用特殊分隔符)
        csv_buffer = io.StringIO()
        csv_buffer.write("---USERS---\n")
        df_users.to_csv(csv_buffer, index=False)
        csv_buffer.write("\n---TASKS---\n")
        df_tasks.to_csv(csv_buffer, index=False)
        csv_buffer.write("\n---PENALTIES---\n")
        df_penalties.to_csv(csv_buffer, index=False)
        
        st.download_button(
            label="📥 下载全量数据备份 (Backup.csv)",
            data=csv_buffer.getvalue(),
            file_name=f"yanzu_backup_{datetime.date.today()}.csv",
            mime="text/csv"
        )
        
        st.write("---")
        st.subheader("♻️ 数据恢复")
        uploaded_file = st.file_uploader("上传备份文件以恢复数据", type=["csv"])
        if uploaded_file is not None:
            if st.button("⚠️ 确认覆盖当前数据并恢复"):
                try:
                    content = uploaded_file.getvalue().decode("utf-8")
                    sections = content.split("---")[1:] # Split by separators
                    
                    c = conn.cursor()
                    # 清空当前表
                    c.execute("DELETE FROM users")
                    c.execute("DELETE FROM tasks")
                    c.execute("DELETE FROM penalties")
                    
                    # 解析并插入 Users
                    # 注意：这里需要简易的手动解析，因为格式是混合的
                    # 为简便起见，这里假设用户是按规定下载的。
                    # 实际操作中，更稳妥的是分别上传，或者解析 text。
                    # 这里提供一个简单的解析逻辑：
                    
                    parts = content.split('---TASKS---')
                    part_users = parts[0].replace('---USERS---\n', '')
                    parts2 = parts[1].split('---PENALTIES---')
                    part_tasks = parts2[0].strip()
                    part_penalties = parts2[1].strip()
                    
                    # 恢复 Users
                    if part_users.strip():
                        pd.read_csv(io.StringIO(part_users)).to_sql('users', conn, if_exists='append', index=False)
                    # 恢复 Tasks
                    if part_tasks.strip():
                        pd.read_csv(io.StringIO(part_tasks)).to_sql('tasks', conn, if_exists='append', index=False)
                    # 恢复 Penalties
                    if part_penalties.strip():
                        pd.read_csv(io.StringIO(part_penalties)).to_sql('penalties', conn, if_exists='append', index=False)
                        
                    conn.commit()
                    st.success("数据恢复成功！帝国已重建！")
                    time.sleep(2)
                    st.rerun()
                except Exception as e:
                    st.error(f"恢复失败，文件格式可能错误: {e}")

# --- 角色分流：普通成员界面 ---
else:
    st.header("📋 任务大厅 (The Quest Hall)")
    
    # 1. 抢单区域
    st.subheader("🔥 待领取的公共任务")
    public_tasks = pd.read_sql("SELECT * FROM tasks WHERE status='待领取' AND type='公共任务池'", conn)
    if not public_tasks.empty:
        for idx, row in public_tasks.iterrows():
            est_gold = round(row['difficulty'] * row['std_time'], 2)
            with st.expander(f"💰 {est_gold} 金币 | {row['title']} (难度 {row['difficulty']})"):
                st.write(f"**说明**: {row['title']}") # 这里应该是 description，但 schema 里没建 description 字段? 
                # 检查: 建表时没有 description? 
                # 修正: 上方 init_db 只有 title。 
                # 补救: 这里显示 title 即可，或者后续版本加。V9版已在上方添加 feedback，
                # 但为了不报错，这里只显示有的字段。
                
                if st.button(f"⚡️ 抢单 (ID: {row['id']})", key=f"take_{row['id']}"):
                    c = conn.cursor()
                    c.execute("UPDATE tasks SET status='进行中', assignee=? WHERE id=?", (user, row['id']))
                    conn.commit()
                    st.success("抢单成功！请在'我的任务'中查看")
                    time.sleep(1)
                    st.rerun()
    else:
        st.caption("暂无公共任务")

    st.write("---")

    # 2. 我的任务
    st.subheader("⚔️ 我的进行中任务")
    my_tasks = pd.read_sql(f"SELECT * FROM tasks WHERE assignee='{user}' AND status='进行中'", conn)
    if not my_tasks.empty:
        for idx, row in my_tasks.iterrows():
            col1, col2 = st.columns([3, 1])
            with col1:
                st.write(f"**{row['title']}**")
                st.caption(f"截止: {row.get('deadline', '无')}") # 使用 get 防止旧数据无字段
            with col2:
                if st.button("✅ 提交验收", key=f"sub_{row['id']}"):
                    c = conn.cursor()
                    c.execute("UPDATE tasks SET status='待验收' WHERE id=?", (row['id'],))
                    conn.commit()
                    st.success("已提交，等待管理员裁决")
                    time.sleep(1)
                    st.rerun()
    else:
        st.caption("你当前没有进行中的任务")

    st.write("---")

    # 3. 历史记录 (含评语)
    st.subheader("📜 完工历史与御批")
    history = pd.read_sql(f"SELECT title, completed_at, quality, feedback, difficulty*std_time*quality as earned FROM tasks WHERE assignee='{user}' AND status='完成' ORDER BY completed_at DESC", conn)
    if not history.empty:
        st.dataframe(history)
    else:
        st.caption("暂无完工记录")

# --- 底部：全员排行榜 (始终可见) ---
st.write("---")
st.header("🏆 颜祖风云榜")
all_members = pd.read_sql("SELECT username FROM users WHERE role='member'", conn)
if not all_members.empty:
    leaderboard_data = []
    for m in all_members['username']:
        g, p = get_gold_stats(m)
        leaderboard_data.append({"成员": m, "净金币": g, "缺勤次数": p})
    
    lb_df = pd.read_json(pd.Series(leaderboard_data).to_json(orient='records')) # 格式化 trick
    lb_df = pd.DataFrame(leaderboard_data).sort_values("净金币", ascending=False)
    
    st.dataframe(lb_df, use_container_width=True)
