cat << 'EOF' > yanzu_system.py
import streamlit as st
import pandas as pd
import sqlite3
import datetime
from datetime import timedelta
import random
import io

# --- V7.0 完美独裁版配置 ---
st.set_page_config(page_title="颜祖美学·执行中枢 V7.0", layout="wide")
DB_FILE = "yanzu_core.db"

# --- 励志语录库 ---
MOTIVATIONS = [
    "痛苦是成长的属性。不要因为痛苦而逃避，要因为痛苦而兴奋。",
    "管理者的跃升，是从'对任务负责'到'对目标负责'。",
    "将个体的能力固化为组织的系统，才是真正的熵减。",
    "不要假装努力，结果不会陪你演戏。",
    "你的对手在看书，你的仇人在磨刀，隔壁老王在练腰。",
    "悲观者正确，乐观者成功。",
    "成年人的世界，没有'容易'二字，只有'因果'二字。",
    "要么出众，要么出局。",
    "用系统工作的效率，对抗个体努力的瓶颈。",
    "不做烂好人，要做'手起刀落'的管理者。"
]

# 初始化数据库 (含自动迁移)
def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    # 表结构定义
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
                  type TEXT,
                  feedback TEXT)''') # 新增 feedback
    c.execute('''CREATE TABLE IF NOT EXISTS penalties 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                  username TEXT, 
                  occurred_at DATE, 
                  reason TEXT)''')
    
    # 尝试添加 feedback 列 (兼容旧库)
    try:
        c.execute("ALTER TABLE tasks ADD COLUMN feedback TEXT")
    except:
        pass # 列已存在

    # 预设管理员
    c.execute("INSERT OR IGNORE INTO users VALUES ('liujingting', 'admin888', 'admin')")
    c.execute("INSERT OR IGNORE INTO users VALUES ('jiangjing', 'strategy999', 'admin')")
    conn.commit()
    conn.close()

init_db()

# --- 核心工具 ---
def run_query(query, params=(), fetch=False):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute(query, params)
    if fetch:
        data = c.fetchall()
        cols = [description[0] for description in c.description]
        conn.close()
        return pd.DataFrame(data, columns=cols)
    conn.commit()
    conn.close()

def calculate_stats(username):
    """计算 7天/30天/总 YVP (扣除惩罚后)"""
    # 1. 查惩罚总数 (用于扣除比例，暂简化为全局扣除，也可按周扣除)
    # V7逻辑：简单起见，惩罚扣除应用于“当周”显示，总榜暂显示原始积累或加权
    # 这里为了仪表盘直观，我们计算纯收益
    
    def get_period_gold(days):
        date_sql = ""
        params = [username]
        if days:
            start = datetime.date.today() - timedelta(days=days)
            date_sql = "AND completed_at >= ?"
            params.append(start)
        
        sql = f"SELECT difficulty, std_time, quality FROM tasks WHERE assignee=? AND status='完成' {date_sql}"
        df = run_query(sql, tuple(params), fetch=True)
        if df.empty: return 0.0
        return (df['difficulty'] * df['std_time'] * df['quality']).sum()

    g7 = get_period_gold(7)
    g30 = get_period_gold(30)
    gtot = get_period_gold(None)
    
    return round(gtot, 2), round(g7, 2), round(g30, 2)

# --- 侧边栏 ---
def login_sidebar():
    st.sidebar.title("💰 颜祖金库 V7.0")
    if 'user' not in st.session_state:
        username = st.sidebar.text_input("用户名")
        password = st.sidebar.text_input("密码", type="password")
        c1, c2 = st.sidebar.columns(2)
        if c1.button("登录"):
            df = run_query("SELECT * FROM users WHERE username=? AND password=?", (username, password), fetch=True)
            if not df.empty:
                st.session_state['user'] = username
                st.session_state['role'] = df.iloc[0]['role']
                # 随机口号
                quote = random.choice(MOTIVATIONS)
                st.toast(f"🔥 {quote}", icon="💪")
                st.rerun()
            else:
                st.sidebar.error("密码错误")
        if c2.button("注册"):
            if username and password:
                try:
                    run_query("INSERT INTO users VALUES (?, ?, 'member')", (username, password))
                    st.sidebar.success("注册成功")
                except:
                    st.sidebar.warning("用户已存在")
    else:
        user = st.session_state['user']
        role = st.session_state['role']
        
        # 仪表盘
        tot, d7, d30 = calculate_stats(user)
        st.sidebar.markdown(f"### 👤 {user}")
        st.sidebar.metric("🏆 历史总金币", f"{tot}")
        c1, c2 = st.sidebar.columns(2)
        c1.metric("近7天", f"{d7}")
        c2.metric("近30天", f"{d30}")
        
        with st.sidebar.expander("🔑 账户/安全"):
            new_pwd = st.text_input("新密码", type="password")
            if st.button("更新密码"):
                run_query("UPDATE users SET password=? WHERE username=?", (new_pwd, user))
                st.sidebar.success("已更新")
        if st.sidebar.button("注销"):
            del st.session_state['user']
            st.rerun()

# --- 主程序 ---
def main():
    login_sidebar()
    if 'user' not in st.session_state:
        st.info("🚫 请先登录系统")
        return

    user = st.session_state['user']
    role = st.session_state['role']

    # 1. 动态菜单 (阶级隔离)
    if role == 'admin':
        menu = ["👑 管理员控制台", "📋 任务大厅", "🏆 金币排行榜"]
    else:
        menu = ["📋 任务大厅", "👤 我的任务", "🏆 金币排行榜"]
    
    choice = st.sidebar.radio("导航", menu)

    # ================= 👑 管理员控制台 =================
    if choice == "👑 管理员控制台" and role == 'admin':
        st.header("👑 核心权力控制台")
        tabs = st.tabs(["发布任务", "⚖️ 考勤与惩罚", "任务管理", "质量裁决", "人员管理", "💾 数据冷备份"])
        
        # Tab 1: 发布
        with tabs[0]:
            c1, c2 = st.columns(2)
            with c1:
                title = st.text_input("任务名称")
                desc = st.text_area("详情")
                deadline = st.date_input("截止")
            with c2:
                d_f = st.number_input("难度系数", 1.0, step=0.1)
                t_s = st.number_input("工时系数", 0.1, step=0.5)
                ttype = st.radio("类型", ["公共任务池", "指定指派"])
                assignee = "待定"
                if ttype == "指定指派":
                    usrs = run_query("SELECT username FROM users WHERE role='member'", fetch=True)
                    assignee = st.selectbox("指派给", usrs['username'].tolist() if not usrs.empty else [])
            if st.button("🚀 发布"):
                stt = "待领取" if ttype == "公共任务池" else "进行中"
                final_a = assignee if ttype == "指定指派" else "待定"
                run_query("INSERT INTO tasks (title, description, difficulty, std_time, status, assignee, deadline, type) VALUES (?,?,?,?,?,?,?,?)", 
                          (title, desc, d_f, t_s, stt, final_a, deadline, ttype))
                st.success("发布成功")

        # Tab 2: 惩罚
        with tabs[1]:
            st.subheader("⚖️ 军法处置")
            p_users = run_query("SELECT username FROM users WHERE role='member'", fetch=True)
            if not p_users.empty:
                tu = st.selectbox("违规人员", p_users['username'])
                pd_date = st.date_input("缺勤日期")
                if st.button("🚨 记缺勤 (-20%)"):
                    run_query("INSERT INTO penalties (username, occurred_at, reason) VALUES (?, ?, '缺勤')", (tu, pd_date))
                    st.success(f"已惩罚 {tu}")
            st.dataframe(run_query("SELECT * FROM penalties ORDER BY id DESC", fetch=True), use_container_width=True)

        # Tab 3: 任务管理 (修改含理由)
        with tabs[2]:
            st.subheader("🛠️ 任务修正")
            tasks = run_query("SELECT id, title FROM tasks WHERE status!='完成'", fetch=True)
            if not tasks.empty:
                tid = st.selectbox("编辑任务", tasks['id'], format_func=lambda x: f"ID {x}")
                curr = run_query(f"SELECT * FROM tasks WHERE id={tid}", fetch=True).iloc[0]
                with st.form("edit"):
                    nt = st.text_input("标题", curr['title'])
                    nd = st.text_area("描述", curr['description'])
                    c1, c2 = st.columns(2)
                    ndf = c1.number_input("难度", value=float(curr['difficulty']))
                    nts = c2.number_input("工时", value=float(curr['std_time']))
                    nfb = st.text_area("✍️ 修改理由/备注", value=curr['feedback'] if curr['feedback'] else "")
                    
                    if st.form_submit_button("保存修改"):
                        run_query("UPDATE tasks SET title=?, description=?, difficulty=?, std_time=?, feedback=? WHERE id=?", 
                                  (nt, nd, ndf, nts, nfb, tid))
                        st.success("已更新")
                        st.rerun()

            st.markdown("---")
            st.subheader("🗑️ 历史清洗")
            dt = run_query("SELECT id, title FROM tasks WHERE status='完成'", fetch=True)
            if not dt.empty:
                did = st.selectbox("删除历史", dt['id'], key="dh")
                if st.button("❌ 永久删除"):
                    run_query("DELETE FROM tasks WHERE id=?", (did,))
                    st.rerun()

        # Tab 4: 评分 (含理由)
        with tabs[3]:
            pending = run_query("SELECT * FROM tasks WHERE status='待验收'", fetch=True)
            if not pending.empty:
                tid = st.selectbox("评分", pending['id'])
                tinfo = pending[pending['id']==tid].iloc[0]
                st.write(f"**{tinfo['title']}** - {tinfo['assignee']}")
                nq = st.slider("质量 (Max 3.0)", 0.0, 3.0, tinfo['quality'])
                reason = st.text_area("✍️ 评分理由 (必填)", placeholder="做得好在哪里？差在哪里？")
                ns = st.selectbox("状态", ["待验收", "完成", "返工"], index=1)
                
                if st.button("提交裁决"):
                    cd = datetime.date.today() if ns == '完成' else None
                    run_query("UPDATE tasks SET quality=?, status=?, completed_at=?, feedback=? WHERE id=?", (nq, ns, cd, reason, tid))
                    st.success("裁决已生效")
                    st.rerun()
            else:
                st.info("无待验收任务")

        # Tab 5: 人员管理 (含删除)
        with tabs[4]:
            st.subheader("💀 人员管理")
            users = run_query("SELECT username, role FROM users", fetch=True)
            for i, u in users.iterrows():
                c1, c2, c3 = st.columns([2, 1, 1])
                c1.write(f"**{u['username']}** ({u['role']})")
                if u['role'] != 'admin':
                    if c3.button("驱逐", key=f"del_{u['username']}"):
                        run_query("DELETE FROM users WHERE username=?", (u['username'],))
                        st.rerun()

        # Tab 6: 数据冷备份 (新功能)
        with tabs[5]:
            st.subheader("💾 数据方舟")
            st.info("由于系统运行在临时环境，请定期复制以下内容保存到本地 txt 文件。恢复时需技术支持。")
            
            # 生成 CSV 文本
            df_u = run_query("SELECT * FROM users", fetch=True)
            df_t = run_query("SELECT * FROM tasks", fetch=True)
            df_p = run_query("SELECT * FROM penalties", fetch=True)
            
            backup_txt = f"=== USERS ===\n{df_u.to_csv(index=False)}\n\n=== TASKS ===\n{df_t.to_csv(index=False)}\n\n=== PENALTIES ===\n{df_p.to_csv(index=False)}"
            
            st.text_area("全量数据 (Ctrl+A 全选复制)", value=backup_txt, height=300)

    # ================= 📋 任务大厅 =================
    elif choice == "📋 任务大厅":
        st.subheader("🛡️ 公共任务池")
        pool = run_query("SELECT * FROM tasks WHERE type='公共任务池' AND status='待领取'", fetch=True)
        if not pool.empty:
            for i, r in pool.iterrows():
                val = round(r['difficulty'] * r['std_time'], 2)
                with st.expander(f"💰 {val} | {r['title']}"):
                    st.write(r['description'])
                    # 阶级隔离：管理员看不到抢单按钮
                    if role != 'admin':
                        if st.button(f"抢单 {r['id']}"):
                            run_query("UPDATE tasks SET status='进行中', assignee=? WHERE id=?", (user, r['id']))
                            st.rerun()
                    else:
                        st.caption("🚫 管理员不可抢单")
        else:
            st.info("池空")
        
        st.markdown("---")
        st.subheader("🔭 进行中")
        st.dataframe(run_query("SELECT title, assignee, status, deadline FROM tasks WHERE status IN ('进行中','返工','待验收')", fetch=True), use_container_width=True)

        st.markdown("---")
        st.subheader("📜 历史完工 (含御批)")
        # 显示 feedback
        st.dataframe(run_query("SELECT title, assignee, difficulty*std_time*quality as 'Gold', feedback as '评语' FROM tasks WHERE status='完成' ORDER BY completed_at DESC", fetch=True), use_container_width=True)

    # ================= 👤 我的任务 (管理员不可见) =================
    elif choice == "👤 我的任务":
        # 双重保险：虽然菜单隐藏了，逻辑上也拦截
        if role == 'admin':
            st.error("管理员不参与具体任务。")
        else:
            mine = run_query("SELECT * FROM tasks WHERE assignee=? AND status!='完成'", (user,), fetch=True)
            if not mine.empty:
                for i, r in mine.iterrows():
                    c1, c2 = st.columns([3, 1])
                    val = round(r['difficulty'] * r['std_time'], 2)
                    c1.write(f"**{r['title']}** (预估 💰 {val})")
                    if c2.button("提交验收", key=f"sub_{r['id']}"):
                        run_query("UPDATE tasks SET status='待验收' WHERE id=?", (r['id'],))
                        st.rerun()
            
            st.subheader("📜 钱包历史")
            st.dataframe(run_query("SELECT title, completed_at, difficulty*std_time*quality as 'Gold', feedback FROM tasks WHERE assignee=? AND status='完成'", (user,), fetch=True))

    # ================= 🏆 排行榜 =================
    elif choice == "🏆 金币排行榜":
        st.header("🏆 颜祖富豪榜")
        
        # 计算逻辑简化版
        def get_data(days):
            data = []
            mems = run_query("SELECT username FROM users WHERE role='member'", fetch=True)['username'].tolist()
            for u in mems:
                # 查金币
                d_sql = ""
                p_params = [u]
                if days:
                    start = datetime.date.today() - timedelta(days=days)
                    d_sql = "AND completed_at >= ?"
                    p_params.append(start)
                
                # 收入
                inc = run_query(f"SELECT difficulty, std_time, quality FROM tasks WHERE assignee=? AND status='完成' {d_sql}", tuple(p_params), fetch=True)
                gross = (inc['difficulty'] * inc['std_time'] * inc['quality']).sum() if not inc.empty else 0
                
                # 惩罚 (简化：显示惩罚次数，不在此处动态计算复杂扣除，只显示净值)
                # 这里的净值逻辑同侧边栏：简单暴力扣除
                pen_sql = d_sql.replace('completed_at', 'occurred_at')
                pen = run_query(f"SELECT COUNT(*) FROM penalties WHERE username=? {pen_sql}", tuple(p_params), fetch=True).iloc[0][0]
                
                net = gross * (1 - min(pen*0.2, 1.0))
                data.append({"成员": u, "净金币": round(net, 2), "缺勤": pen})
            return pd.DataFrame(data).sort_values("净金币", ascending=False)

        t1, t2, t3 = st.tabs(["7天", "30天", "总榜"])
        with t1: st.dataframe(get_data(7), use_container_width=True)
        with t2: st.dataframe(get_data(30), use_container_width=True)
        with t3: st.dataframe(get_data(None), use_container_width=True)

if __name__ == "__main__":
    main()
EOF
