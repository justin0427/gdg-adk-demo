"""
reset.py — 課堂輔助：一個指令切換 soc_agent/agent.py 的「從零開始 / 完成版」。

用法：
  python reset.py start   從零開始：備份現在的 agent.py 成 agent.py.bak，換成空白骨架
  python reset.py done    直接跟上：把 agent.py 換成完成版（solutions/agent.py）

情境：
- 課堂一開始（關卡 2）：大家一起執行 start，從空白骨架開始貼。
- 有人卡住跟不上：執行 done，立刻回到可運作的完成狀態，繼續往下上課。
- 你自己改壞了想重來：done 之後再 start 即可。
"""

import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
AGENT = os.path.join(HERE, "soc_agent", "agent.py")
STARTER = os.path.join(HERE, "starter", "agent_skeleton.py")
SOLUTION = os.path.join(HERE, "solutions", "agent.py")


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else ""
    if mode == "start":
        if os.path.exists(AGENT):
            shutil.copy(AGENT, AGENT + ".bak")
        shutil.copy(STARTER, AGENT)
        print("[OK] 已換成空白骨架，開始跟著講義關卡 2 動手吧。")
        print("     （原本的檔案備份在 soc_agent/agent.py.bak）")
    elif mode == "done":
        shutil.copy(SOLUTION, AGENT)
        print("[OK] 已換成完成版，你跟上進度了。接著跑：python soc_agent/agent.py 驗工具。")
    else:
        print(__doc__.strip())
        sys.exit(1)


if __name__ == "__main__":
    main()
