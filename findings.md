# Findings & Decisions

## Requirements
- 修复 `mitm-captures.bat` 中上一轮静态审查指出的全部问题。
- 明确计划，提升执行效率。
- 通过静态测试把问题锁住，避免回归。

## Research Findings
- 当前目录不是 Git 仓库，无法在收口时提交。
- 现有静态测试只覆盖了部分关键字与结构，需要继续增强行为约束。
- 本轮第一批待修的 3 个问题分别是：
  - `resolve_python_cmd` 可能误收 `WindowsApps\python.exe` alias。
  - `load_state` 对单个 `%` 不安全，且 `stop/status` 没有在导入失败时短路。
  - `start` 在 manifest/state/latest 落盘失败时仍可能回报成功。
- 跟进静态复核又确认了 2 个遗漏问题：
  - `resolve_python_cmd` 只验证首个 `where python` 候选，可能让首个假 alias 屏蔽后续真实解释器。
  - `cmd_stop` 对 `write_manifest` 和 `latest.*` 副本落地失败没有 fail-closed，可能在产物不完整时仍返回成功。
- 第三轮静态复核又确认了 3 个遗漏问题：
  - `cmd_stop` 在判定失败前就删除 `proxy_info.env`，会把可重试失败变成不可恢复状态。
  - 非 `--program` 模式下，`cmd_start` 对 Windows 代理设置失败只告警不失败，会误报启动成功。
  - `PRINT_STDOUT` 默认值与 `--stdout` 帮助语义不一致，实际变成总是打印。
- 第四轮静态复核又确认了 3 个遗漏问题：
  - `cmd_stop` 在任何清理动作前就要求 `ensure_deps` 成功，依赖损坏时会卡死代理恢复和停进程。
  - `cmd_stop` 先跑 `ai_brief.py`、后写最终 manifest，导致 AI 产物读取到 stop 前的旧 manifest。
  - `rollback_failed_start` 会删除 `latest.manifest.json`，可能抹掉上一轮成功抓包留下的 latest 元数据。
- 第五轮静态复核又确认了 3 个遗漏问题：
  - `cmd_stop` 在 `kill-failed` 后仍继续生成 HAR / report / AI 产物并刷新 `latest.*`，会污染 latest 视图。
  - `rollback_failed_start` 在 Windows 代理恢复失败时仍删除 `proxy_info.env` 与本轮 manifest，导致最需要重试恢复时反而丢状态。
  - `resolve_mitmdump_cmd` 仍然只取首个候选且不校验可执行性，和 Python 解析逻辑不一致。
- 第六轮静态复核又确认了 2 个遗漏问题：
  - `copy_latest_checked` 在本轮产物缺失时不会清理上一轮残留 `latest.*`，会让 `ai` 重新打包出“新 manifest + 旧 AI 产物”的混合视图。
  - `cmd_stop` 在 `kill-failed` 时虽然设置了 `blocked-by-active-capture`，但不会把这些状态写回本轮 manifest，结构化状态会停留在 stop 前的旧值。
- 第七轮静态复核又确认了 2 个遗漏问题：
  - `latest.*` 刷新在单个复制失败后仍会继续，可能留下“部分当前 run + 部分上一 run”的混合视图。
  - `--har-backend` 在 Windows 批处理入口里没有合法值校验，非法值会静默落到 Python 兜底路径。
- 第八轮静态复核又确认了 2 个遗漏问题：
  - 新会话 `start` 成功后会立即切换 `latest.manifest.json`，但旧的 `latest.ai.* / latest.summary / latest.index` 仍保留，导致 `ai` 可读出跨 run 混合视图。
  - `start` 更新 `latest.manifest.json` 仍是直接覆盖，失败时存在把旧 latest manifest 覆盖坏的静态风险。
- 第九轮静态复核又确认了 1 个遗漏问题：
  - `start` 在切换新 `latest.manifest.json` 前直接删除旧 latest 非 manifest 产物；若清理中途失败并回滚，旧 latest manifest 仍在，但关联的 `latest.flow/har/log/index/summary/ai*` 可能已被部分删空，形成撕裂视图。
- 第十轮静态复核又确认了 1 个遗漏问题：
  - `rollback_failed_start` 调用 latest 恢复 helper 时静默吞掉恢复失败；若旧 latest 产物恢复失败，脚本仍会删除本轮 `proxy_info.env` / manifest 并仅报“已回滚”，导致撕裂视图和诊断状态一起被掩盖。
- 第十一轮静态复核又确认了 1 个遗漏问题：
  - `rollback_failed_start` 在 latest 恢复失败时虽然会保留 `proxy_info.env` / manifest 和 `.bak`，但 `write_state` 没把 `START_LATEST_*_BACKUP_FILE` 写入状态文件，`--force-recover` 也不会清理这些遗留备份，导致保留下来的恢复状态不完整、`.bak` 会脱离管理。
- 第十二轮静态复核又确认了 3 个遗漏问题：
  - Windows 批处理入口没有 `captures/.capture.lock` 互斥，`start/stop/status/ai` 并发时会交叉读写 `proxy_info.env`、`latest.*` 和 Windows 代理恢复状态。
  - `--dir` 目标路径从未校验存在性，会把 typo 路径静默创建成新的 `captures/` 工作树，掩盖用户输入错误。
  - `start` 只在 1 秒后做一次存活探测，稳定窗口明显短于 shell 版本，可能把几秒内就退出的 `mitmdump` 误落盘为成功会话。
- 第十三轮静态复核又确认了 1 个遗漏问题：
  - Windows 新加的目录锁虽然能阻止并发，但没有 owner 元数据和 stale 恢复路径；一旦脚本/终端异常退出，遗留的 `.capture.lock` 会永久阻断后续 `start/stop/status/ai`，与 shell `flock` 的自动释放语义不等价。
- 第十四轮静态复核又确认了 2 个遗漏问题：
  - stale lock 恢复虽然引入了 owner PID，但记录的是当前宿主 shell PID；在交互式 `cmd.exe` 中，上轮批处理异常退出后 shell 仍存活，恢复逻辑会把锁误判为“owner 仍活着”，导致同 shell 永久无法自恢复。
  - `recover_stale_capture_lock` 在 owner 文件缺失时直接失败，`--force-recover` 实际根本走不到锁清理分支，和设计意图不一致。
- 第十五轮静态复核又确认了 2 个遗漏问题：
  - `write_state` 仍直接覆盖 `proxy_info.env`，异常中断时可能留下截断状态文件；而 `stop/status` 又高度依赖该文件，存在真实状态撕裂风险。
  - `load_state` 只导入存在的键，顶层默认 `PROGRAM_MODE=0` / `WINHTTP_SNAPSHOT_STATUS=not-requested` 会把部分损坏状态误解释成有效会话；`stop` 可能因此误进代理恢复分支，且原实现会先改注册表再校验 WinHTTP snapshot。
- 第十六轮静态复核又确认了 2 个遗漏问题：
  - `cmd_stop` 现在虽然会在恢复代理前校验快照，但顺序仍是先 `taskkill`、后 `validate_proxy_restore_state`；一旦状态损坏导致代理不可恢复，脚本会先杀掉仍在承载系统代理的 `mitmdump`，再带着错误退出，把 Windows 代理留在指向已死 localhost 的断网状态。
  - Windows 版 `start` 仍缺少 shell 已有的 `LISTEN_HOST/LISTEN_PORT` 显式校验，`load_state` 也只校验存在性不校验端口合法性；空 host、非数字端口或越界端口会被拖到运行期甚至 manifest 写入阶段才暴露。
- 第十七轮静态复核又确认了 3 个遗漏问题：
  - `load_state` 虽然已经开始 fail-closed，但 `validate_loaded_state` 仍不要求 `MITM_PID` 存在且为纯数字；`cmd_stop/status` 会继续把坏 PID 送进 `taskkill /pid` 或 `tasklist`，存在误杀和状态判断失真风险。
  - `validate_proxy_restore_state` 只要求 `PREV_PROXY_ENABLE` 存在，不校验值是否合法；恢复代理时会把坏值原样写回 `ProxyEnable` 注册表。
  - `cmd_start` 在拉起新 `mitmdump` 前不清空 `MITM_PID`；若外层环境残留旧 PID，而本次启动又没拿到新 PID，脚本会把旧 PID 误当成当前抓包进程继续落盘。
- 第十八轮静态复核又确认了 2 个遗漏问题：
  - loaded-state 当前只靠 `pid_running` 判断“抓包进程还在不在”；若 Windows 复用了同一个 PID，`status` 会误报仍在运行，`start` 会误判为已有活跃会话，`stop` 甚至会 `taskkill` 掉无关进程。
  - 代理快照当前无法表达“注册表键存在但值为空字符串”的合法状态；`read_reg_value` 会把这类值写成空变量，随后 `stop` 的恢复前校验把它误判成损坏状态，导致非 `--program` 会话无法正常恢复代理。
- 当前 36 类问题都已被测试和实现覆盖；本轮改动后未再发现同级别新增问题。

## Technical Decisions
| Decision | Rationale |
|----------|-----------|
| 使用 `task_plan.md / findings.md / progress.md` | 响应用户对“更多 plan”的要求，并让阶段更清晰 |
| 用静态测试约束批处理关键 token 和控制流 | 当前环境无法直接跑 Windows，测试是最稳的回归护栏 |
| 为 `resolve_python_cmd` 增加 `:validate_python_cmd` | 避免 `where python` 命中 `WindowsApps` 假解释器 |
| Python 候选改成逐个验证直到命中真解释器 | 避免首个假候选屏蔽后续真实解释器 |
| `stop/status` 改成 `call :load_state || exit /b 1` | 导入失败时必须 fail-closed，不能带半空变量继续跑 |
| `start` 的 state/manifest/latest.manifest 落盘失败统一回滚 | 保证成功返回时一定有可停止、可恢复的会话状态 |
| `stop` 的 manifest/latest 落地失败必须返回非零 | 保证 latest 产物和停止结果一致可信 |
| `stop` 只有成功时才删除 `proxy_info.env` | 失败时要保留状态，支持重试恢复和补落地 |
| `start` 的 Windows 代理设置失败也必须回滚 | 避免代理未接入时误报抓包已启动 |
| `ai --stdout` 改成显式 opt-in | 让 CLI 帮助和实际输出行为一致 |
| `stop` 先清理进程和代理，再尽力解析产物依赖 | 防止依赖损坏时连 stop 本身都跑不完 |
| `cmd_stop` 先写 stop 后 manifest，再生成 AI brief，最后刷新最终 manifest | 让 AI 产物与最终元数据一致 |
| `start` 回滚不再删除 `latest.manifest.json` | 保护上一轮成功 latest 元数据不被失败启动覆盖删除 |
| `kill-failed` 时禁止刷新新的 latest 产物 | 避免活跃 flow/har 污染 latest 视图 |
| 代理恢复失败时保留会话状态文件与本轮 manifest | 给后续 `stop/status` 恢复重试留下必需元数据 |
| `mitmdump` 路径解析也改成逐候选可执行性校验 | 防止首个坏候选屏蔽真实二进制 |
| `latest.*` 在源产物缺失时要清理旧文件 | 防止本轮失败结果和上一轮成功产物混出伪成功视图 |
| `kill-failed` 也要写回本轮 manifest，但不刷新 `latest.manifest.json` | 当前会话需要结构化失败记录，而 latest 仍应保留为最后一次完整收口结果 |
| `kill-failed` 写 manifest 时不得填 `stoppedAt` | 避免把仍在运行的抓包进程误标为已停止 |
| latest 刷新若任一复制失败则整体清空 latest | 比起留下跨 run 混合视图，空 latest 更安全且更容易触发上层显式失败 |
| Windows 批处理入口要显式拒绝非法 `--har-backend` | 保持与 shell 版本一致，避免无效参数悄悄改变执行路径 |
| `start` 在发布新 latest manifest 前先清理旧 latest 非 manifest 产物 | 避免当前 run manifest 与上一轮 AI/summary/index 混成伪最新视图 |
| `copy_latest` 改成临时文件 + move 原子发布 | 保证 start 切换 `latest.manifest.json` 时不会把旧 latest manifest 直接覆盖坏 |
| `start` 预发布阶段要先暂存旧 latest 非 manifest 产物，并在回滚时恢复 | 避免清理中途失败时把旧 latest manifest 留成指向残缺产物的悬空引用 |
| `rollback_failed_start` 中的 latest 恢复失败也必须显式置错并保留状态 | 避免回滚阶段再把 latest 视图撕裂一次，同时给后续排障保留 `proxy_info.env` 和本轮 manifest |
| latest 备份路径也要写入状态文件 | latest 恢复失败后如果要保留状态供后续清理/重试，必须连同 `START_LATEST_*_BACKUP_FILE` 一起持久化 |
| `--force-recover` 要先清理 start latest 备份再删除状态文件 | 防止 latest 回滚失败留下无人接管的 `.bak` 遗留物 |
| Windows 批处理入口也要持有 `captures/.capture.lock` | 防止 start/stop/status/ai 并发读写状态文件、latest 产物和代理恢复路径 |
| `--dir` 必须先指向已存在的项目目录 | 比起静默创建 typo 目录，fail-closed 更能保护真实目标工作树 |
| start 必须先经过独立稳定窗口再写状态 | 避免把短暂存活的 `mitmdump` 误标成成功启动并落盘状态 |
| Windows 目录锁要写入 owner PID，并在 owner 已死时自动回收 | 尽量逼近 shell `flock` 的自动释放语义，避免异常退出留下永久锁死 |
| owner 元数据缺失或损坏时，至少要允许 `--force-recover` 接管锁清理 | 防止最坏情况下 `.capture.lock` 变成无人能恢复的永久障碍 |
| stale lock 恢复时如果 owner PID 等于当前 shell PID，也应允许回收 | 同一交互式 `cmd.exe` 不存在并发重入，命中同 shell 只意味着上一轮异常退出遗留了锁 |
| owner 文件缺失时的 `--force-recover` 必须在锁恢复 helper 内真正生效 | 否则用户带着接管开关重试，目录锁仍会永久阻断后续入口 |
| `write_state` 必须改成临时文件 + 原子替换 | 防止 `proxy_info.env` 被写成半截后，让 `stop/status` 读到损坏状态 |
| `load_state` 导入前必须清空危险状态变量 | 防止顶层默认值或上一轮残留值污染本次状态导入 |
| `cmd_stop/status` 必须显式校验加载后的核心字段 | 避免 `PROGRAM_MODE/FLOW_FILE/LISTEN_*` 缺失时继续沿错误分支执行 |
| `restore_windows_proxy` 必须先验证 WinHTTP 快照完整性再修改注册表 | 避免坏状态下把当前 Windows 代理先改坏，再因 snapshot 缺失半路失败 |
| 非 `--program` 的 `cmd_stop` 必须先确认代理状态可恢复，再决定是否杀掉 mitmdump | 否则坏状态会把系统代理留在指向已死 localhost 的断网态 |
| Windows 版 `start` 和已加载状态都要显式校验 host/port | 保持与 shell 版 contract 一致，避免把空 host 或非法端口拖到更晚阶段才炸 |
| 已加载状态中的 `MITM_PID` 必须存在且为纯数字 | 避免坏状态把任意字符串送进 `taskkill /pid` 或 `tasklist` |
| `PREV_PROXY_ENABLE` 只能接受 `__UNSET__ / 0 / 1 / 0x0 / 0x1` | 避免把坏状态原样写回 Windows 代理注册表 |
| `cmd_start` 在 spawn 前必须先清空 `MITM_PID` | 防止外层残留 PID 伪装成本轮成功启动 |
| loaded-state 的 capture 身份必须同时匹配 PID 和 `FLOW_FILE` 命令行 | 避免 Windows PID 复用把无关进程误报成当前抓包进程，甚至被 stop 误杀 |
| PID 身份无法验证时必须 fail-closed，不能按 stale/已退出继续处理 | 避免活跃但失配的进程被 `stop/status/--force-recover` 误判成可安全接管 |
| PID 命令行校验至少要绑定 `mitmdump.exe` 与 `-w FLOW_FILE` | 单看 `FLOW_FILE` 子串过宽，仍可能把无关命令行误判成当前 capture |
| PID 身份失配时需要保留显式 `--force-recover` 逃生口 | 默认仍应 fail-closed，但不能让 stale `proxy_info.env` 永久阻断后续 stop/start 接管 |
| `validate_mitmdump_cmd` 也必须遵守 `mitmdump.exe` 进程名契约 | 否则 resolver 接受的 wrapper 候选会在后续 `capture_pid_matches_state` 中被永久判成身份失配 |
| `write_manifest` 和 `build_ai_bundle` 也必须用临时文件 + move 原子发布 | 否则 stop/ai 路径一旦在 PowerShell 写文件时失败或中断，最终 manifest / bundle 会被直接截断 |
| `load_state` 只能导入白名单状态键 | 否则损坏或被手改的 `proxy_info.env` 会在 `validate_loaded_state` 前先借生成的 `.cmd` 执行任意批处理片段 |
| `copy_latest_checked` 也必须用临时文件 + move 原子发布 | 否则 stop 刷新 `latest.*` 时被中断，最终 latest 文件仍可能被直接写半截 |
| 代理快照里的空字符串值必须持久化为显式 sentinel | 避免合法空字符串 `ProxyServer/ProxyOverride` 在恢复前校验里退化成“缺字段” |

## Issues Encountered
| Issue | Resolution |
|-------|------------|
| `CLAUDE_PLUGIN_ROOT` 未设置 | 直接读取本地 skill 模板路径，不依赖该环境变量 |
| 新增静态测试后首次回跑失败 3 项 | 按 TDD 逐项补 `mitm-captures.bat` 实现直到转绿 |
| 跟进补测时先命中了 `call :label` 而不是标签定义 | 用 `section_between()` 改成按真实 label 段截取 |
| 第三轮补测后新增 3 项失败 | 按 TDD 修正 stop 删除时机、start 代理失败回滚、stdout 默认语义 |
| 第四轮补测后新增 2 项失败 | 按 TDD 修正 stop 依赖前置、manifest 时序、latest manifest 回滚策略 |
| 第五轮补测后新增 3 项失败 | 按 TDD 修正 kill-failed latest 污染、回滚丢状态、mitmdump 候选误判 |
| 第六轮补测后新增 1 项失败 | 先按 TDD 补 `.bat`，再把过于依赖单行格式的静态断言收紧到真实语义 |
| 第七轮补测后新增 2 项失败 | 按 TDD 修正 latest 刷新失败回收和 `--har-backend` 非法值校验 |
| 第八轮补测后新增 1 项 error | 先按 TDD 补 start latest 清理 helper 与原子发布实现，再转绿 |
| 第九轮补测后新增 1 项失败 | 按 TDD 为 start 增加 latest 备份、回滚恢复和成功后清理链路 |
| 第十轮补测后新增 1 项失败 | 按 TDD 让 latest 恢复 helper 返回错误码，并让 rollback 在恢复失败时 fail-closed |
| 第十一轮补测后新增 1 项失败 | 按 TDD 持久化 `START_LATEST_*_BACKUP_FILE`，并让 `--force-recover` 先清理 latest `.bak` |
| 第十二轮补测后新增 2 项 error | 先按 TDD 补齐 lock wrapper、目标目录校验和 startup stability helper，再把旧 dispatch 假设改成新语义断言 |
| 第十三轮补测后新增 1 项 error | 按 TDD 补齐 lock owner PID 元数据、死 owner 自动回收与 `--force-recover` 锁恢复路径 |
| 第十四轮补测后新增 1 项失败 | 按 TDD 收紧 stale lock 恢复，补同 shell 回收与 owner 文件缺失时的 `--force-recover` 接管 |
| 第十五轮补测后新增 1 项 failure + 1 项 error | 按 TDD 补 `write_state` 原子发布、`load_state` 清空危险变量、`cmd_stop/status` 校验和 `restore_windows_proxy` 先验快照 |
| 第十六轮补测后新增 1 项 failure + 1 项 error | 按 TDD 把 `validate_proxy_restore_state` 前移到杀进程前，并补 `validate_start_args` 与 `LISTEN_PORT` 合法性校验 |
| 第十六轮绿灯复核时发现 `cmd_stop` 外层 `if defined MITM_PID` 少了闭括号 | 立即收紧静态结构断言，并补回缺失括号后再回跑全绿 |
| 第十七轮补测后新增 1 项 failure | 按 TDD 补 `validate_loaded_state` 的 `MITM_PID` 校验，并收紧 `validate_proxy_restore_state` 与 `pid_running` 的数字防护 |
| 第十七轮绿灯复核后新增 1 项 failure | 继续按 TDD 让 `cmd_start` 在 spawn 前先清空 `MITM_PID`，阻断外层残留 PID 污染 |
| 第十八轮补测后新增 2 项 failure | 按 TDD 补 `capture_pid_matches_state`，并让 `read_reg_value / restore_windows_proxy` 显式保留和恢复空字符串代理值 |
| 第十九轮补测后新增 1 项 failure | 按 TDD 把 `capture_pid_matches_state` 改成三态 fail-closed，并收紧到 `mitmdump.exe + -w + FLOW_FILE` 绑定 |
| 第二十轮静态审查发现 2 个真实问题 | 按 TDD 恢复 `--force-recover` 的显式接管逃生口，并收紧 `validate_mitmdump_cmd` 只接受 `mitmdump.exe` 候选 |
| 第二十一轮静态审查发现 1 个真实问题 | 按 TDD 把 `write_manifest` 和 `build_ai_bundle` 改成原子发布，避免最终产物被写半截 |
| 第二十二轮静态审查发现 2 个真实问题 | 按 TDD 收紧 `load_state` 的白名单键导入，并让 `copy_latest_checked` 也改成原子发布 |

## Resources
- `mitm-captures.bat`
- `tests/test_windows_bat_static.py`
- `/home/dtamade/.codex/skills/planning-with-files/templates/task_plan.md`
- `/home/dtamade/.codex/skills/planning-with-files/templates/findings.md`
- `/home/dtamade/.codex/skills/planning-with-files/templates/progress.md`

## Visual/Browser Findings
- 无
