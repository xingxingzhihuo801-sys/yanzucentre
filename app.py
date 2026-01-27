import streamlit as st
import pandas as pd
import sqlite3
import datetime
import random
import time
import io

# --- 1. 系统配置 ---
st.set_page_config(page_title="颜祖美学·执行中枢 V11.0", layout="wide")

# --- 2. 数据库连接与自动修复 ---
# 使用新文件名以避免旧缓存干扰，或者沿用旧名但加强修复逻辑
DB_NAME = "yanzu_core_v11.db"
conn = sqlite3.connect(DB_NAME, check_same_thread=False)

def init_and_repair_db():
    c = conn.cursor()
    
    # A. 建基础表 (如果完全是新的)
    c.execute('''CREATE TABLE IF NOT EXISTS users 
                 (username TEXT PRIMARY KEY, password TEXT, role TEXT)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS tasks 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                  title TEXT, 
                  description TEXT, 
                  difficulty REAL, 
                  std_time REAL, 
                  quality REAL DEFAULT 1.0, 
                  status TEXT, 
                  assignee TEXT, 
                  deadline DATE, 
                  completed_at DATE, 
                  feedback TEXT,
                  type TEXT)''')
                  
    c.execute('''CREATE TABLE IF NOT EXISTS penalties 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                  username TEXT, 
                  occurred_at DATE, 
                  reason TEXT)''')
    
    # B. 自动修复机制 (关键：补全旧表缺失的列)
    # 针对每一个可能缺失的列，尝试执行 ALTER TABLE
    columns_to_check = [
        ("tasks", "description", "TEXT"),
        ("tasks", "deadline", "DATE"),
        ("tasks", "type", "TEXT"),
        ("tasks", "feedback", "TEXT"),
        ("tasks", "completed_at", "DATE")
    ]
    
    for table, col, dtype in columns_to_check:
        try:
            c.execute(f"ALTER TABLE {table} ADD COLUMN {col} {dtype}")
            # print(f"修复成功：已添加 {col} 列") 
        except sqlite3.OperationalError:
            pass # 列已存在，忽略错误

    # C. 预设管理员 (防止被锁在门外)
    c.execute("INSERT OR IGNORE INTO users VALUES ('liujingting', 'admin888', 'admin')")
    c.execute("INSERT OR IGNORE INTO users VALUES ('jiangjing', 'strategy999', 'admin')")
    conn.commit()

# 执行初始化
init_and_repair_db()

# --- 3. 励志语录库 ---
QUOTES = [
    "痛苦是成长的属性。不要因为痛苦而逃避，要因为痛苦而兴奋。",
    "管理者的跃升，是从'对任务负责'到'对目标负责'。",
    "不要假装努力，结果不会陪你演戏。",
    "你的对手在看书，你的仇人在磨刀，隔壁老王在练腰。",
    "悲观者正确，乐观者成功。",
    "用系统工作的效率，对抗个体努力的瓶颈。",
    "不做烂好人，要做'手起刀落'的管理者。"
]

# --- 4. 核心逻辑函数 ---

def get_gold_stats(username, days=None):
    """计算净金币 (YVP) = 总收入 * (1 - 惩罚系数)"""
    date_filter = ""
    if days:
        start_date = datetime.date.today() - datetime.timedelta(days=days)
        date_filter = f" AND completed_at >= '{start_date}'"
    
    # 1. 查任务收入
    sql = f"SELECT difficulty, std_time, quality FROM tasks WHERE assignee='{username}' AND status='完成' {date_filter}"
    df = pd.read_sql(sql, conn)
    gross = 0.0
    if not df.empty:
        gross = (df['difficulty'] * df['std_time'] * df['quality']).sum()
    
    # 2. 查惩罚次数 (累计)
    pen_sql = f"SELECT COUNT(*) as cnt FROM penalties WHERE username='{username}'"
    pen_cnt = pd.read_sql(pen_sql, conn).iloc[0]['cnt']
    
    # 3. 计算净值 (每次惩罚扣20%)
    net = gross * (1 - min(pen_cnt * 0.2, 1.0))
    return round(net, 2), pen_cnt

# --- 5. 登录与注册界面 ---
if 'user' not in st.session_state:
    st.title("🏛️ 颜祖美学·数字化军营")
    st.info(f"🔥 {random.choice(QUOTES)}")
    
    tab_login, tab_reg = st.tabs(["🔑 登录", "📝 新兵注册"])
    
    with tab_login:
        with st.form("login_form"):
            u = st.text_input("用户名")
            p = st.text_input("密码", type="password")
            if st.form_submit_button("进入中枢"):
                ud = pd.read_sql(f"SELECT * FROM users WHERE username='{u}' AND password='{p}'", conn)
                if not ud.empty:
                    st.session_state.user = u
                    st.session_state.role = ud.iloc[0]['role']
                    st.rerun()
                else:
                    st.error("鉴权失败：账号或密码错误")
    
    with tab_reg:
        with st.form("reg_form"):
            nu = st.text_input("设置用户名")
            np = st.text_input("设置密码", type="password")
            if st.form_submit_button("注册账号"):
                if nu and np:
                    try:
                        conn.execute("INSERT INTO users VALUES (?, ?, 'member')", (nu, np))
                        conn.commit()
                        st.success("注册成功！请切换到登录页登录。")
                    except sqlite3.IntegrityError:
                        st.warning("该用户名已被占用。")
                else:
                    st.warning("用户名和密码不能为空。")
    st.stop()

# --- 6. 主程序 ---
user = st.session_state.user
role = st.session_state.role

# 侧边栏：个人中心
st.sidebar.title(f"👤 {user}")
if role == 'admin':
    st.sidebar.info("👑 最高指挥官")
    st.sidebar.caption("不参与金币结算")
else:
    st.sidebar.info("⚔️ 核心成员")
    net, pen = get_gold_stats(user)
    st.sidebar.metric("💰 净金币 (YVP)", net, delta=f"被罚 {pen} 次 (-{int(pen*20)}%)", delta_color="inverse")
    
    # 历史战绩微缩图
    g7, _ = get_gold_stats(user, 7)
    g30, _ = get_gold_stats(user, 30)
    st.sidebar.text(f"7天收益: {g7}")
    st.sidebar.text(f"30天收益: {g30}")

st.sidebar.divider()
if st.sidebar.button("安全注销"):
    del st.session_state.user
    st.rerun()

# 导航菜单 (阶级隔离)
if role == 'admin':
    menu = ["👑 核心控制台", "📋 任务大厅", "🏆 颜祖风云榜"]
else:
    menu = ["📋 任务大厅", "👤 我的任务", "🏆 颜祖风云榜"]

choice = st.sidebar.radio("导航", menu)

# ================= 👑 管理员控制台 =================
if choice == "👑 核心控制台" and role == 'admin':
    st.header("👑 最高统帅部")
    tabs = st.tabs(["🚀 发布指令", "⚖️ 裁决评分", "🚨 军法考勤", "👥 人员管理", "💾 备份恢复"])
    
    # 1. 发布
    with tabs[0]:
        c1, c2 = st.columns(2)
        with c1:
            title = st.text_input("任务名称")
            desc = st.text_area("详细说明 (DoD标准)")
            deadline = st.date_input("截止日期")
        with c2:
            d = st.number_input("难度系数 (D_factor)", 1.0, step=0.1)
            t = st.number_input("标准工时 (T_std)", 1.0, step=0.5)
            ttype = st.radio("任务类型", ["公共任务池", "指定指派"])
            
            assignee = "待定"
            if ttype == "指定指派":
                usrs = pd.read_sql("SELECT username FROM users WHERE role='member'", conn)
                if not usrs.empty:
                    assignee = st.selectbox("指派给", usrs['username'].tolist())
        
        if st.button("立即发布"):
            # 完整字段插入
            status = "待领取" if ttype == "公共任务池" else "进行中"
            final_a = assignee if ttype == "指定指派" else "待定"
            
            try:
                conn.execute('''INSERT INTO tasks (title, description, difficulty, std_time, status, assignee, deadline, type, feedback) 
                                VALUES (?, ?, ?, ?, ?, ?, ?, ?, '')''', 
                             (title, desc, d, t, status, final_a, deadline, ttype))
                conn.commit()
                st.success("指令已下达！")
            except Exception as e:
                st.error(f"发布失败: {e}")

    # 2. 裁决
    with tabs[1]:
        # 只看待验收
        pend = pd.read_sql("SELECT * FROM tasks WHERE status='待验收'", conn)
        if not pend.empty:
            tid = st.selectbox("选择待审任务", pend['id'], format_func=lambda x: f"ID {x}")
            tinfo = pend[pend['id']==tid].iloc[0]
            
            st.warning(f"正在裁决: {tinfo['title']}")
            st.write(f"执行人: {tinfo['assignee']} | 预估金币: {round(tinfo['difficulty']*tinfo['std_time'], 2)}")
            
            col_q, col_fb = st.columns([1, 2])
            with col_q:
                q = st.slider("质量系数 (Q)", 0.0, 3.0, 1.0, 0.1)
                res = st.selectbox("裁决结果", ["完成", "返工"])
            with col_fb:
                fb = st.text_area("御批 (评分理由)", placeholder="必须填写理由...")
            
            if st.button("提交裁决"):
                if not fb:
                    st.error("陛下，请填写御批理由！")
                else:
                    cat = datetime.date.today() if res == '完成' else None
                    conn.execute("UPDATE tasks SET quality=?, status=?, feedback=?, completed_at=? WHERE id=?", 
                                 (q, res, fb, cat, tid))
                    conn.commit()
                    st.success("裁决已生效！")
                    time.sleep(1)
                    st.rerun()
        else:
            st.info("暂无待验收任务")

    # 3. 考勤
    with tabs[2]:
        st.error("⚠️ 热炉法则：每次缺勤扣除 20% 总收益")
        usrs = pd.read_sql("SELECT username FROM users WHERE role='member'", conn)
        target = st.selectbox("违规人员", usrs['username'].tolist() if not usrs.empty else [])
        
        if st.button("🚨 记录缺勤"):
            conn.execute("INSERT INTO penalties (username, occurred_at, reason) VALUES (?, ?, '缺勤')", 
                         (target, datetime.date.today()))
            conn.commit()
            st.success(f"已对 {target} 执行惩罚")
            
        st.write("---")
        st.caption("惩罚日志")
        st.dataframe(pd.read_sql("SELECT * FROM penalties ORDER BY id DESC", conn))

    # 4. 人员
    with tabs[3]:
        all_u = pd.read_sql("SELECT * FROM users", conn)
        for i, r in all_u.iterrows():
            c1, c2, c3 = st.columns([2, 1, 1])
            c1.write(f"**{r['username']}**")
            c2.write(f"角色: {r['role']}")
            if r['role'] != 'admin':
                if c3.button("驱逐", key=f"del_{r['username']}"):
                    conn.execute("DELETE FROM users WHERE username=?", (r['username'],))
                    conn.commit()
                    st.rerun()

    # 5. 备份与恢复
    with tabs[4]:
        st.info("数据冷备份：防止云端重置丢失数据。")
        
        # 导出
        users_csv = pd.read_sql("SELECT * FROM users", conn).to_csv(index=False)
        tasks_csv = pd.read_sql("SELECT * FROM tasks", conn).to_csv(index=False)
        pens_csv = pd.read_sql("SELECT * FROM penalties", conn).to_csv(index=False)
        
        # 简单打包成文本
        full_backup = f"===USERS===\n{users_csv}\n===TASKS===\n{tasks_csv}\n===PENALTIES===\n{pens_csv}"
        
        st.download_button("📥 下载全量备份.txt", full_backup, f"backup_{datetime.date.today()}.txt")
        
        st.write("---")
        st.write("♻️ 恢复数据 (请上传上面下载的txt)")
        uf = st.file_uploader("上传备份文件", type=['txt'])
        if uf:
            if st.button("⚠️ 确认覆盖并恢复"):
                try:
                    content = uf.getvalue().decode("utf-8")
                    parts = content.split("===")
                    # parts[0] is empty, parts[1] is USERS tag... wait split results:
                    # "", "USERS", "\ncsv...", "TASKS", "\ncsv...", "PENALTIES", "\ncsv..."
                    # split by sections manually safer
                    
                    sec_users = content.split("===USERS===\n")[1].split("===TASKS===")[0].strip()
                    sec_tasks = content.split("===TASKS===\n")[1].split("===PENALTIES===")[0].strip()
                    sec_pens = content.split("===PENALTIES===\n")[1].strip()
                    
                    c = conn.cursor()
                    c.execute("DELETE FROM users")
                    c.execute("DELETE FROM tasks")
                    c.execute("DELETE FROM penalties")
                    
                    pd.read_csv(io.StringIO(sec_users)).to_sql('users', conn, if_exists='append', index=False)
                    pd.read_csv(io.StringIO(sec_tasks)).to_sql('tasks', conn, if_exists='append', index=False)
                    pd.read_csv(io.StringIO(sec_pens)).to_sql('penalties', conn, if_exists='append', index=False)
                    
                    conn.commit()
                    st.success("数据已成功恢复！")
                    time.sleep(1)
                    st.rerun()
                except Exception as e:
                    st.error(f"恢复失败: {e}")

# ================= 📋 任务大厅 (全员可见) =================
elif choice == "📋 任务大厅":
    st.header("🛡️ 任务大厅")
    
    # 1. 待领取任务
    st.subheader("🔥 待领取任务 (公共池)")
    pool = pd.read_sql("SELECT * FROM tasks WHERE status='待领取' AND type='公共任务池'", conn)
    
    if not pool.empty:
        for i, r in pool.iterrows():
            gold = round(r['difficulty'] * r['std_time'], 2)
            with st.expander(f"💰 {gold}金币 | {r['title']} (难度{r['difficulty']})"):
                st.write(f"**详情**: {r['description']}")
                st.write(f"**截止**: {r['deadline']}")
                # 管理员只能看，不能抢
                if role != 'admin':
                    if st.button("⚡️ 抢单", key=f"take_{r['id']}"):
                        conn.execute("UPDATE tasks SET status='进行中', assignee=? WHERE id=?", (user, r['id']))
                        conn.commit()
                        st.success("抢单成功！")
                        time.sleep(0.5)
                        st.rerun()
                else:
                    st.caption("🔒 管理员仅查看")
    else:
        st.caption("暂无待领取任务")
        
    st.divider()
    
    # 2. 全员看板
    st.subheader("🔭 实时看板")
    active = pd.read_sql("SELECT title, assignee, status, deadline FROM tasks WHERE status IN ('进行中','返工','待验收')", conn)
    st.dataframe(active, use_container_width=True)
    
    st.divider()
    
    # 3. 完工记录
    st.subheader("📜 完工御批")
    done = pd.read_sql("SELECT title, assignee, quality, feedback, difficulty*std_time*quality as earned FROM tasks WHERE status='完成' ORDER BY completed_at DESC", conn)
    st.dataframe(done, use_container_width=True)

# ================= 👤 我的任务 (仅成员) =================
elif choice == "👤 我的任务":
    st.header("⚔️ 我的战场")
    my = pd.read_sql(f"SELECT * FROM tasks WHERE assignee='{user}' AND status='进行中'", conn)
    
    if not my.empty:
        for i, r in my.iterrows():
            with st.container(border=True):
                c1, c2 = st.columns([3, 1])
                c1.write(f"**{r['title']}**")
                c1.caption(f"截止: {r['deadline']} | 详情: {r['description']}")
                if c2.button("✅ 提交验收", key=f"sub_{r['id']}"):
                    conn.execute("UPDATE tasks SET status='待验收' WHERE id=?", (r['id'],))
                    conn.commit()
                    st.success("已提交！")
                    time.sleep(0.5)
                    st.rerun()
    else:
        st.info("暂无进行中任务，请去大厅抢单。")

# ================= 🏆 颜祖风云榜 (全员可见) =================
elif choice == "🏆 颜祖风云榜":
    st.header("🏆 颜祖富豪榜")
    # 只显示 member
    mems = pd.read_sql("SELECT username FROM users WHERE role='member'", conn)
    
    if not mems.empty:
        data = []
        for m in mems['username']:
            g, p = get_gold_stats(m)
            data.append({"成员": m, "净金币": g, "缺勤次数": p})
        
        df = pd.DataFrame(data).sort_values("净金币", ascending=False)
        st.dataframe(df, use_container_width=True)
    else:
        st.info("暂无数据")
