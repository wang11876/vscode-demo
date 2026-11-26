"""

每日 23:50 自动注销所有 RDP 远程登录用户
================================================
适用：Windows Server 2019，RDP 监听端口已改为 10808
原理：query session 列出所有终端服务会话 → logoff <session_id> 逐个注销
      （query session / logoff 是会话级接口，与 RDP 监听端口是 3389 还是 10808 无关）
跳过：console（本地控制台）、services（Session 0）、监听态 rdp-tcp 行
运行：必须管理员；建议用任务计划程序“不管用户是否登录都运行”跑在 Session 0，
      避免脚本自身被当作远程用户踢掉。
"""
import logging
import subprocess
import sys
import time
import datetime

logging.basicConfig(
    filename='demo_result_log.log',        # 日志文件
    filemode='a',              # 'a' 追加，'w' 每次覆盖
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

def log(msg):
    
    print(f"[{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}",
          flush=True)
    logging.info(msg)


def is_admin():
    try:
        r = subprocess.run(['net', 'session'],
                           capture_output=True, text=True,
                           encoding='gbk', errors='ignore')
        return r.returncode == 0
    except Exception:
        return False


def logoff_all_rdp_sessions():
    """
    列出所有终端服务会话，逐个 logoff。
    query session 输出列：
        会话名  用户名  会话ID  状态  [类型]  [设备]
    行首 '>' 表示当前会话；rdp-tcp 无用户名那行是“监听”态，要跳过。
    """
    log("开始扫描所有 RDP 会话...")

    try:
        r = subprocess.run(['query', 'session'],
                           capture_output=True, text=True,
                           encoding='gbk', errors='ignore')
        if r.returncode != 0:
            raise RuntimeError(r.stderr.strip() or r.stdout.strip())
    except Exception as e:
        log(f"query session 失败，回退 qwinsta: {e}")
        try:
            r = subprocess.run(['qwinsta'],
                               capture_output=True, text=True,
                               encoding='gbk', errors='ignore')
        except Exception as e2:
            log(f"qwinsta 也失败: {e2}，本次无法执行")
            return 0
    
    lines = r.stdout.strip().splitlines()
    killed = 0
    
    for line in lines[1:]:                      # 跳过表头
        raw = line.strip()
        if not raw:
            continue
        stripped = raw.lstrip('>').strip()     # 剥掉当前会话标记
        parts = stripped.split()
        if len(parts) < 3:
            continue
    
        sess_name = parts[0].lower()
    
        # 跳过本地控制台 / 服务会话
        if sess_name in ('console', 'services'):
            continue
        # 跳过 rdp-tcp 监听态行（无用户名、状态=监听）
        if '监听' in stripped or 'Listen' in stripped:
            continue
    
        # 第 3 列是 session_id
        try:
            session_id = int(parts[2])
        except ValueError:
            continue
        if session_id == 0:
            continue
    
        # === 核心动作：logoff <session_id> ===
        lo = subprocess.run(['logoff', str(session_id)],
                             capture_output=True, text=True,
                             encoding='gbk', errors='ignore')
        user = parts[1] if len(parts) >= 4 else '(无用户名)'
        if lo.returncode == 0:
            log(f"  已注销 session_id={session_id:<4} 用户={user}")
            killed += 1
        else:
            log(f"  注销 session_id={session_id} 失败: "
                f"{lo.stderr.strip() or lo.stdout.strip()}")
    
    log(f"本次共注销 {killed} 个远程会话")
    return killed


def main():
    if not is_admin():
        log("警告: 未以管理员身份运行，logoff 会失败！")
        log("请右键 → 以管理员身份运行，或任务计划程序勾选“最高权限”。")

    log("=" * 60)
    log("RDP 注销脚本已启动")
    log("动作    : query session → logoff <session_id>")
    log("=" * 60)

    log(">>> 开始执行强制下线 <<<")
    logoff_all_rdp_sessions()
    log(">>>> 执行完毕 <<<<")

    time.sleep(60)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt as e:
        log("收到 Ctrl+C，退出")
        log(e)
        sys.exit(0)
