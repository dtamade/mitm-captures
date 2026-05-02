# Task Plan: Harden Windows Batch Entrypoint

## Goal
修复 `mitm-captures.bat` 在静态审查中暴露的全部真实问题，并把这些问题写成静态测试防回归。

## Current Phase
Phase 26

## Phases
### Phase 1: Requirements & Discovery
- [x] 收敛本轮修复范围
- [x] 记录刚发现的 3 个真实问题
- [x] 建立文件化计划
- **Status:** complete

### Phase 2: Test Design
- [x] 为 Python alias 误判补失败测试
- [x] 为 `load_state` 导入和调用点短路补失败测试
- [x] 为 `start` 状态落盘失败回滚补失败测试
- **Status:** complete

### Phase 3: Implementation
- [x] 修正 Python 解析逻辑
- [x] 修正状态文件 `%` 导入与 `load_state` 错误处理
- [x] 修正 `start` 的状态落盘失败回滚
- **Status:** complete

### Phase 4: Verification
- [x] 回跑静态测试
- [x] 再做一轮静态审查确认没有遗漏
- **Status:** complete

### Phase 5: Delivery
- [x] 汇总修复与剩余风险
- [x] 说明 Git 提交受限原因
- **Status:** complete

### Phase 6: Follow-up Static Closure
- [x] 为 `where python` 多候选回退补失败测试
- [x] 为 `stop` 的 manifest/latest 落地失败补 fail-closed 测试
- [x] 修正 `resolve_python_cmd` 的逐候选验证逻辑
- [x] 修正 `cmd_stop` 的 manifest/latest 失败退出语义
- [x] 回跑静态测试并再次复核
- **Status:** complete

### Phase 7: Retry-Safe Stop and Start Proxy Closure
- [x] 为 `stop` 失败时保留 `proxy_info.env` 补失败测试
- [x] 为 `start` 的 Windows 代理设置失败补回滚测试
- [x] 为 `ai --stdout` 的显式开关语义补测试
- [x] 修正 `stop` 的状态文件删除时机
- [x] 修正 `start` 的 Windows 代理失败回滚路径
- [x] 修正 `PRINT_STDOUT` 默认值
- [x] 回跑静态测试并复核
- **Status:** complete

### Phase 8: Stop Dependency Decoupling and Manifest Ordering
- [x] 为 `stop` 不应被 `ensure_deps` 前置阻断补失败测试
- [x] 为 `ai_brief` 读取最终 stop manifest 的时序补测试
- [x] 为 `start` 回滚不抹掉旧 `latest.manifest.json` 补测试
- [x] 让 `stop` 的清理动作与运行时依赖解析解耦
- [x] 修正 `cmd_stop` 的 manifest 写入时序
- [x] 修正 `rollback_failed_start` 的 latest manifest 清理策略
- [x] 回跑静态测试并复核
- **Status:** complete

### Phase 9: Kill-Failed Containment and Mitmdump Validation
- [x] 为 `kill-failed` 后禁止刷新 latest 产物补失败测试
- [x] 为代理恢复失败时保留恢复状态补失败测试
- [x] 为 `mitmdump` 逐候选校验补静态测试
- [x] 修正 `cmd_stop` 的 `kill-failed` 阻断逻辑
- [x] 修正 `rollback_failed_start` 的状态保留语义
- [x] 修正 `resolve_mitmdump_cmd` 的候选校验逻辑
- [x] 回跑静态测试并复核
- **Status:** complete

### Phase 10: Latest Consistency and Kill-Failed Manifest Persistence
- [x] 为缺失产物时清理陈旧 `latest.*` 补静态断言
- [x] 为 `kill-failed` 也要写回本轮 manifest 状态补静态断言
- [x] 修正 `copy_latest_checked` 的缺失源文件清理语义
- [x] 修正 `kill-failed` 路径的 manifest 落地
- [x] 修正 `write_manifest`，避免把活跃失败会话误标为 stopped
- [x] 回跑静态测试并复核
- **Status:** complete

### Phase 11: Latest Refresh Fail-Closed and HAR Backend Validation
- [x] 为 `--har-backend` 非法值补失败静态测试
- [x] 为 `latest.*` 刷新失败时整体回收补静态断言
- [x] 修正批处理入口的 `--har-backend` 合法值校验
- [x] 修正 `cmd_stop` 的 latest 刷新失败回收语义
- [x] 回跑静态测试并复核
- **Status:** complete

### Phase 12: Start Latest Hygiene and Atomic Latest Manifest Publish
- [x] 为 `start` 清理旧 latest 非 manifest 产物补静态测试
- [x] 为 `copy_latest` 的原子发布补静态测试
- [x] 修正 `start`，在发布新 latest manifest 前清理旧 latest 非 manifest 产物
- [x] 修正 `copy_latest`，改为临时文件 + move 的原子发布
- [x] 回跑静态测试并复核
- **Status:** complete

### Phase 13: Start Latest Rollback Preservation
- [x] 为 `start` 预发布 latest 刷新中断时恢复旧 latest 视图补失败测试
- [x] 修正 `start`，先暂存旧 latest 非 manifest 产物，再在回滚时恢复
- [x] 修正 `start`，仅在新 `latest.manifest.json` 切换成功后清理暂存备份
- [x] 回跑静态测试并复核
- **Status:** complete

### Phase 14: Start Latest Restore Fail-Closed
- [x] 为 latest 恢复失败必须显式 fail-closed 补失败静态测试
- [x] 修正 `rollback_failed_start`，latest 恢复失败时保留状态并输出明确错误
- [x] 修正 latest 恢复 helper，返回真实错误码
- [x] 回跑静态测试并复核
- **Status:** complete

### Phase 15: Start Latest Backup State Persistence
- [x] 为 latest 备份路径必须写入状态文件补失败静态测试
- [x] 为 `--force-recover` 必须先清理遗留 start latest `.bak` 补静态断言
- [x] 修正 `write_state`，持久化全部 `START_LATEST_*_BACKUP_FILE`
- [x] 修正 `handle_existing_state_before_start`，先清理 latest 备份再删除 `proxy_info.env`
- [x] 回跑静态测试并复核
- **Status:** complete

### Phase 16: Windows Locking, Target Dir Validation, and Startup Stability
- [x] 为 `.capture.lock` 互斥补失败静态测试
- [x] 为 `--dir` 必须校验预存目录补失败静态测试
- [x] 为 start 必须经过稳定窗口再写状态补失败静态测试
- [x] 修正 Windows dispatch，给 start/stop/status/ai 增加互斥锁封装
- [x] 修正 `validate_target_dir`，拒绝把 typo 路径静默建成新工作树
- [x] 修正 start 启动探测，延长到独立稳定窗口 helper
- [x] 回跑静态测试并复核
- **Status:** complete

### Phase 17: Stale Capture Lock Recovery
- [x] 为 Windows stale lock 恢复补失败静态测试
- [x] 修正目录锁，写入 owner PID 元数据
- [x] 修正锁获取逻辑，死 owner 时自动清理陈旧锁
- [x] 修正锁恢复逻辑，缺失/坏 owner 元数据时允许 `--force-recover` 接管
- [x] 回跑静态测试并复核
- **Status:** complete

### Phase 18: Interactive Shell Lock Recovery Closure
- [x] 为同一 `cmd.exe` 壳中的 stale lock 回收补失败静态测试
- [x] 为 owner 文件缺失时 `--force-recover` 也能回收锁补失败静态测试
- [x] 修正 `recover_stale_capture_lock`，同 shell owner PID 命中时允许回收陈旧锁
- [x] 修正 `recover_stale_capture_lock`，owner 文件缺失时走 `--force-recover` 接管
- [x] 回跑静态测试并复核
- **Status:** complete

### Phase 19: Atomic State Publish and Corrupt-State Proxy Recovery Closure
- [x] 为 `write_state` 的原子写入补失败静态测试
- [x] 为损坏状态禁止误恢复 Windows 代理补失败静态测试
- [x] 修正 `write_state`，改为临时文件 + 原子替换发布 `proxy_info.env`
- [x] 修正 `load_state`，导入前清空危险状态变量
- [x] 修正 `cmd_stop/status`，对损坏状态显式 fail-closed
- [x] 修正 `restore_windows_proxy`，先校验 WinHTTP 快照再改注册表
- [x] 回跑静态测试并复核
- **Status:** complete

### Phase 20: Stop Ordering and Listen Validation Closure
- [x] 为 `stop` 必须先校验代理恢复状态再决定能否杀进程补失败静态测试
- [x] 为 `start` 的 host/port 参数校验补失败静态测试
- [x] 为已加载状态中的 `LISTEN_PORT` 合法性补静态断言
- [x] 修正 `cmd_stop`，把代理恢复前置校验移动到杀进程之前
- [x] 修正 Windows 入口，补齐 `validate_start_args`
- [x] 修正 `validate_loaded_state`，拒绝空 host 和非法 port
- [x] 回跑静态测试并复核
- **Status:** complete

### Phase 21: PID and Proxy State Hardening
- [x] 为已加载状态中的 `MITM_PID` 缺失/非数字补静态断言
- [x] 为 `PREV_PROXY_ENABLE` 只能接受 `__UNSET__ / 0 / 1 / 0x0 / 0x1` 补静态断言
- [x] 修正 `validate_loaded_state`，拒绝缺失或非数字 `MITM_PID`
- [x] 修正 `validate_proxy_restore_state`，拒绝非法 `PREV_PROXY_ENABLE`
- [x] 修正 `pid_running`，拒绝非数字 PID 输入
- [x] 绿灯复核时补出 `cmd_start` 未清空旧 `MITM_PID` 的静态测试
- [x] 修正 `cmd_start`，在 spawn 前显式清空 `MITM_PID`
- [x] 回跑静态测试并复核
- **Status:** complete

### Phase 22: Process Identity and Empty Proxy Snapshot Hardening
- [x] 为 loaded-state 的 PID 身份校验补静态断言，要求不能只看 PID 存活
- [x] 为代理快照中的空字符串注册表值补静态断言，要求与键缺失区分
- [x] 修正 `cmd_stop/status/handle_existing_state_before_start`，改为通过 `capture_pid_matches_state` 校验 PID 与 `FLOW_FILE` 命令行绑定
- [x] 修正 `read_reg_value`，对空字符串注册表值写入 `__EMPTY__` sentinel
- [x] 修正 `restore_windows_proxy`，把 `__EMPTY__` 还原成真正的空字符串而不是删键
- [x] 回跑静态测试并复核
- **Status:** complete

### Phase 23: Fail-Closed PID Identity Verification
- [x] 为 `capture_pid_matches_state` 的三态返回补静态断言，区分“已退出”和“身份不可信”
- [x] 为 PID 身份校验必须绑定 `mitmdump.exe` 与 `-w FLOW_FILE` 参数补静态断言
- [x] 修正 `capture_pid_matches_state`，在 `FLOW_FILE` 为空、CIM/命令行校验失败或不匹配时返回 `exit /b 2`
- [x] 修正 `cmd_stop/status/handle_existing_state_before_start`，对 `errorlevel 2` 直接 fail-closed 报错退出
- [x] 回跑静态测试并复核
- **Status:** complete

### Phase 24: Explicit Recovery Escape Hatch and Mitmdump Resolver Contract
- [x] 为 PID 身份失配时的 `stop --force-recover` / `start --force-recover` 逃生口补静态断言
- [x] 为 `validate_mitmdump_cmd` 必须拒绝非 `mitmdump.exe` wrapper 补静态断言
- [x] 修正 `cmd_stop`，在 `errorlevel 2` 且显式 `--force-recover` 时按 stale 会话继续收口
- [x] 修正 `handle_existing_state_before_start`，在 `errorlevel 2` 且显式 `--force-recover` 时允许清理旧状态并接管
- [x] 修正 `validate_mitmdump_cmd`，只接受 basename 为 `mitmdump.exe` 的候选，保持与运行期 PID 身份校验契约一致
- [x] 回跑静态测试并复核
- **Status:** complete

### Phase 25: Atomic Manifest and Bundle Publish
- [x] 为 `write_manifest` 必须用临时文件 + move 原子发布补静态断言
- [x] 为 `build_ai_bundle` 必须用临时文件 + move 原子发布补静态断言
- [x] 修正 `write_manifest`，失败时清理 tmp，成功后再原子替换最终 manifest
- [x] 修正 `build_ai_bundle`，失败时清理 tmp，成功后再原子替换最终 bundle
- [x] 回跑静态测试并复核
- **Status:** complete

### Phase 26: Safe State Import and Atomic Stop Latest Publish
- [x] 为 `load_state` 必须拒绝未知状态键补静态断言
- [x] 为 `copy_latest_checked` 必须用临时文件 + move 原子发布补静态断言
- [x] 修正 `load_state`，只允许白名单键进入生成的 `.cmd` 导入脚本
- [x] 修正 `copy_latest_checked`，缺源时仍保留删旧目标语义，命中源文件时改为原子替换 latest 目标
- [x] 回跑静态测试并复核
- **Status:** complete

## Key Questions
1. 如何在批处理里识别并规避 `WindowsApps\python.exe` 这类假阳性解释器？
2. `proxy_info.env` 导入失败时，哪些入口必须立即中止？
3. `start` 在状态落盘失败时，最小正确回滚动作是什么？
4. `stop` 在 latest/manifest 落地失败时，如何保证不会误报成功？
5. `stop` 返回失败时，何时必须保留 `proxy_info.env` 以支持重试？
6. `start` 的 Windows 代理设置失败时，是否必须回滚并返回非零？
7. `stop` 是否应该在恢复代理前要求 Python/mitmdump 可用？
8. AI 产物读取的 manifest，应该是 stop 前还是 stop 后最终版本？
9. `kill-failed` 时还能不能继续发布新的 `latest.*` 产物？
10. Windows 代理恢复失败时，哪些状态必须保留给后续 `stop/status` 重试？
11. 分析产物缺失时，旧的 `latest.ai.* / latest.summary / latest.index` 是否还能保留？
12. `kill-failed` 若要写回 manifest，是否应该同时写入 `stoppedAt`？
13. latest 刷新过程中若单个文件复制失败，是保留上一轮 latest，还是整体清空并 fail-closed？
14. Windows 批处理入口是否要和 shell 版本一样拒绝非法 `--har-backend`？
15. 新会话 start 成功后，旧的 latest AI/summary/index 是否还能继续留给 `ai/status` 使用？
16. start 发布 `latest.manifest.json` 时，如何避免写坏旧 latest manifest？
17. start 在切换 `latest.manifest.json` 前如果 latest 清理中途失败，如何保证旧 latest 视图不被撕裂？
18. start 回滚恢复旧 latest 视图时如果恢复动作本身失败，如何避免静默报“已回滚”？
19. latest 恢复失败后若保留了 `.bak`，如何保证状态文件和 `--force-recover` 都还能继续接管这些备份？
20. Windows 批处理入口如何补齐 `.capture.lock` 互斥，避免 start/stop/status/ai 并发踩状态？
21. `--dir` 指向不存在目录时，是自动建树还是 fail-closed 报用户输错路径？
22. start 在多长稳定窗口后才允许把 `proxy_info.env` / manifest 持久化为“已启动”？
23. Windows 目录锁在脚本/终端异常退出后，如何识别 stale owner 并恢复，而不是永久卡死所有后续命令？
24. 如果 owner PID 对应的是当前仍存活的交互式 `cmd.exe`，如何区分“壳还活着”与“上一轮批处理已死”？
25. `.capture.lock` 目录还在但 `.owner.pid` 丢失时，`--force-recover` 如何真正接管锁恢复？
26. `proxy_info.env` 在 Windows 批处理里如何做到掉电/中断下尽量原子发布？
27. `stop` 面对截断或缺字段的状态文件时，如何避免把默认值误当成真实代理快照并改坏系统代理？
28. 当 Windows 代理仍指向活跃 mitmdump 时，`stop` 遇到损坏快照应先拒绝还是先杀进程？
29. Windows 版 `start` 和已加载状态，是否应像 shell 一样显式拒绝空 host、非数字端口和越界端口？
30. `cmd_start` 在新进程 PID 获取失败时，如何避免外层残留 `MITM_PID` 伪装成本轮启动成功？
31. 如果 Windows 复用了同一个 PID，如何避免把无关进程误当成当前 capture 并误杀？
32. Windows 代理快照里的空字符串键值，如何和真正的“键不存在”区分开？
33. 如果 PID 还活着，但已经无法证明它仍属于当前 capture，`stop/status/--force-recover` 是否还能把它当 stale 继续处理？
34. 如果 `where mitmdump` 先命中 wrapper/shim，如何避免 start 能启动、但 stop/status 又因进程名契约不一致而永久 fail-closed？
35. `write_manifest` / `build_ai_bundle` 失败或中断时，如何避免最终 manifest 或 bundle 被写成半截文件？
36. `load_state` 如何在导入 `proxy_info.env` 时避免未知键或恶意键名先于 `validate_loaded_state` 被执行？

## Decisions Made
| Decision | Rationale |
|----------|-----------|
| 先补失败测试再改 `.bat` | 锁定回归边界，避免再次“看起来修了” |
| 本轮只修上一轮静态审查里的 3 个问题 | 保持收敛，避免范围漂移 |
| `start` 的状态落盘前置且失败即回滚 | 避免“进程已起但无状态文件”的失控状态 |
| `python` 候选必须通过真实解释器自检 | 防止命中 Windows Store alias 假阳性 |
| `stop` 的 manifest/latest 落地失败必须返回非零 | 保证 latest 产物和停止结果一致可信 |
| Python 路径解析对每个候选逐个验证 | 避免首个假候选屏蔽后续真实解释器 |
| `stop` 只有在成功退出时才删除 `proxy_info.env` | 失败时必须保留状态，支持恢复代理或补落地产物 |
| `start` 的 Windows 代理设置失败也走回滚 | 避免报告“已启动”但系统代理未接入抓包 |
| `ai` 的 stdout 输出改回显式 opt-in | 让帮助文案与真实行为一致 |
| `stop` 不再使用 `ensure_deps` 作为前置门槛 | 先完成停进程和代理恢复，再尽力生成产物 |
| `cmd_stop` 先写最终 manifest，再生成 AI brief，最后再刷新一次 manifest | 保证 AI 产物读到 stop 后元数据，同时让最终 manifest 记录 AI 状态 |
| `rollback_failed_start` 不再删除 `latest.manifest.json` | 避免失败的新启动抹掉上一轮成功 latest 元数据 |
| `kill-failed` 时禁止刷新新的 latest 产物 | 避免仍在写入的活跃 flow 污染 latest 视图 |
| 代理恢复失败时保留 `proxy_info.env` 与本轮 manifest | 给后续恢复重试留下必需元数据 |
| `mitmdump` 路径解析也改成逐候选可执行性校验 | 避免首个坏 shim 或假链接屏蔽真实二进制 |
| `copy_latest_checked` 在源文件缺失时要删除旧目标 | 避免本轮缺失产物和上一轮残留 latest 混成假成功视图 |
| `kill-failed` 时只写本轮 manifest，不刷新 `latest.manifest.json` | 保持 `latest.*` 继续指向最后一次完整收口的会话，同时给当前会话留下结构化失败状态 |
| `write_manifest` 在 `kill-failed` 时不写 `stoppedAt` | 避免把仍在运行的抓包进程误记为已停止 |
| latest 刷新若任一文件失败则整体清空 latest 并返回失败 | 比起留下跨 run 混合视图，空 latest 更安全且更容易被 `ai/status` 正确识别 |
| Windows 批处理入口也要校验 `--har-backend` 的枚举值 | 保持与 `stopCaptures.sh` 一致，避免非法值静默落到 Python 兜底 |
| `start` 发布新 latest manifest 前先清掉旧 latest 非 manifest 产物 | 避免“当前 run manifest + 上一轮 AI/summary”混成伪最新视图 |
| `copy_latest` 用临时文件 + move 原子发布 | 让 start 更新 `latest.manifest.json` 时要么保留旧值，要么完整切到新值 |
| `start` 切换新 latest manifest 前先把旧 latest 非 manifest 产物暂存到备份位 | 一旦 start 在预发布阶段失败，可以回滚恢复旧 latest 视图，而不是把旧 manifest 留成悬空引用 |
| `start` 回滚中的 latest 恢复失败也必须 fail-closed 并保留状态文件 | 否则仍会留下“旧 manifest + 缺失 latest 产物”的撕裂视图，而且脚本会误报已完成回滚 |
| latest 备份路径必须写入 `proxy_info.env` | latest 恢复失败后若要保留状态供 `stop/status/--force-recover` 接管，就不能让 `.bak` 路径脱离管理 |
| `--force-recover` 先清理 start latest `.bak` 再删状态文件 | 避免 latest 恢复失败后留下无人管理的遗留备份文件 |
| Windows 批处理入口也要持有 `captures/.capture.lock` | 防止 start/stop/status/ai 并发读写 `proxy_info.env`、`latest.*` 和代理恢复状态 |
| `--dir` 必须先指向已存在的项目目录 | 比起静默创建 typo 目录，fail-closed 更能保护真实抓包工作树和用户意图 |
| start 必须先经过独立稳定窗口再写状态 | 避免只活 1 秒的假启动被过早落盘为“可 stop/status 的成功会话” |
| Windows 目录锁必须写入 owner PID，并在 owner 已死时自动回收 | 尽量逼近 shell `flock` 的自动释放语义，避免异常退出后永久卡死全部入口 |
| owner 元数据缺失或损坏时，至少允许 `--force-recover` 清理锁 | 避免极端异常把 `.capture.lock` 留成无人能恢复的永久障碍 |
| stale lock 恢复时如果 owner PID 等于当前 shell PID，也应视作可回收 | 同一交互式 `cmd.exe` 内不可能并发执行两轮批处理，命中同 shell 只说明上轮异常退出留下了锁 |
| owner 文件缺失时的 `--force-recover` 必须在锁恢复 helper 内真正生效 | 否则用户虽然传了接管开关，目录锁仍会永久阻断所有后续命令 |
| `write_state` 必须用临时文件 + 原子替换发布 `proxy_info.env` | 避免中断时把唯一状态文件写成半截，导致后续 `stop/status` 读到损坏状态 |
| `load_state` 导入前要清空危险状态变量，`cmd_stop/status` 要显式校验核心字段 | 防止顶层默认值或上次残留变量把损坏状态误解释成有效会话 |
| `restore_windows_proxy` 必须先验证 WinHTTP snapshot，再修改注册表代理键 | 避免坏状态下先改坏 HKCU 代理，再因为 snapshot 缺失半路失败 |
| `cmd_stop` 在非 `--program` 会话中，必须先确认代理可恢复，再决定是否杀 mitmdump | 否则损坏状态会把系统代理留在指向已死 localhost 的断网状态 |
| Windows 入口和已加载状态都要显式校验 host/port | 保持与 shell 一致，避免空 host、非法端口或越界端口拖到运行期才失败 |
| 已加载状态里的 `MITM_PID` 必须存在且为纯数字 | 避免坏状态把任意字符串送进 `taskkill /pid` 或 `tasklist` |
| `PREV_PROXY_ENABLE` 只能接受 `__UNSET__ / 0 / 1 / 0x0 / 0x1` | 避免将坏状态原样写回 Windows 代理注册表 |
| `cmd_start` 在 spawn 新进程前必须先清空 `MITM_PID` | 防止外层残留 PID 伪装成本轮成功启动 |
| loaded-state 的进程身份不能只靠 PID 存活判断 | 避免 Windows PID 复用后把无关进程误报成当前 capture，甚至被 `stop` 误杀 |
| PID 身份失配时只有显式 `--force-recover` 才能接管 stale 会话 | 保持默认 fail-closed，同时给用户留下脚本内恢复出口，避免 `proxy_info.env` 永久卡死 |
| `resolve_mitmdump_cmd` 只能接受 basename 为 `mitmdump.exe` 的候选 | 让安装解析契约和运行期 PID 身份契约保持一致，避免 wrapper 启动后被 stop/status 自己拒掉 |
| `write_manifest` 和 `build_ai_bundle` 也必须原子发布 | 避免 stop/ai 路径在 PowerShell 写文件失败或中断时把最终 manifest / bundle 撕裂成半截 |
| `load_state` 只能导入白名单状态键 | 避免损坏或被手改的 `proxy_info.env` 在 `validate_loaded_state` 前先借生成的 `.cmd` 注入批处理片段 |
| `copy_latest_checked` 也必须原子发布 | 避免 stop 刷新 `latest.*` 时直接把最终文件写半截；失败后清理只能覆盖“脚本跑到失败分支”的情况 |
| 代理快照要把空字符串值和键缺失分开持久化 | 避免合法的空字符串 `ProxyServer/ProxyOverride` 在 stop 恢复时被误判成损坏状态 |

## Errors Encountered
| Error | Attempt | Resolution |
|-------|---------|------------|
| 第十一轮补测后 `write_state` 缺少 `START_LATEST_*_BACKUP_FILE` 持久化断言失败 | 1 | 按 TDD 补全状态写回，并让 `--force-recover` 先清理 latest `.bak` |
| 第十二轮补测后缺少 lock/target-dir/startup-stability label 导致静态断言 error | 1 | 按 TDD 补齐 dispatch wrapper、目录校验和启动稳定窗口 helper |
| 第十三轮补测后缺少 stale lock 恢复 helper 导致静态断言 error | 1 | 按 TDD 补齐 owner PID 元数据、死 owner 回收与 `--force-recover` 接管分支 |
| 第十四轮补测后 stale lock 仍无法覆盖交互式同 shell 与 owner 文件缺失两类恢复语义 | 1 | 按 TDD 收紧 `recover_stale_capture_lock`，补同 shell 回收与缺 owner 文件的 `--force-recover` 接管 |

## Notes
- 优先修真实运行风险，不做表面重构。
- 这是非 Git 目录，最终无法执行 `git commit`。
