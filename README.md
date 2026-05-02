# mitm-captures

一组用于本地启动/停止 `mitmdump` 抓包并导出 HAR 的小脚本。
支持 Linux/macOS 的 shell 入口，也支持 Windows 的单文件批处理入口 `mitm-captures.bat`。

它解决三个问题：
- 一键启动抓包并落盘 `flow`
- 一键停止抓包并导出 HAR
- 在 Linux GNOME 下自动管理并恢复系统代理（可关闭）

## 目录结构

- `startCaptures.sh`: 启动抓包并写入会话状态
- `stopCaptures.sh`: 停止抓包、恢复代理、导出 HAR
- `flow2har.py`: Python 兜底 HAR 转换器
- `flow_report.py`: 从 `flow` 生成 `index.ndjson` 与 `summary.md`
- `ai_brief.py`: 从 `manifest + index` 生成 AI 友好分析包（`ai.json` + `ai.md`）
- `analyzeLatest.sh`: 一键拼装可直接贴给 AI 的整合文本
- `ai.sh`: 最短 AI 入口（等价于 `analyzeLatest.sh --stdout`）
- `.har_addon.py`: 旧版 addon（当前流程不依赖）

## 依赖

最小依赖：
- `mitmdump`
- `python3`（仅在 stop 的 Python 转换后端需要）

可选依赖：
- `gsettings`（GNOME 自动代理管理）

## 平台入口

Linux/macOS:

```bash
./startCaptures.sh
./stopCaptures.sh
./ai.sh
```

Windows:

```bat
mitm-captures.bat install
mitm-captures.bat start
mitm-captures.bat stop
mitm-captures.bat ai
```

首次在 Windows 上使用时，通常先执行一次：

```bat
mitm-captures.bat cert
```

它会安装 mitmproxy 当前用户证书，便于浏览器和系统流量被正确代理。

## 快速开始

在你要抓包的项目目录里运行：

```bash
~/projects/mitm-captures/startCaptures.sh
```

完成操作后停止并导出 HAR：

```bash
~/projects/mitm-captures/stopCaptures.sh
```

停止后你可以直接用固定快捷文件（不需要找时间戳）：

- `captures/latest.flow`
- `captures/latest.har`
- `captures/latest.summary.md`
- `captures/latest.ai.md`
- `captures/latest.ai.json`

输出文件默认在当前目录下：
- `captures/capture_<timestamp>_<pid>.flow`
- `captures/capture_<timestamp>_<pid>.har`
- `captures/capture_<timestamp>_<pid>.log`
- `captures/capture_<timestamp>_<pid>.manifest.json`
- `captures/capture_<timestamp>_<pid>.index.ndjson`
- `captures/capture_<timestamp>_<pid>.summary.md`
- `captures/capture_<timestamp>_<pid>.ai.json`
- `captures/capture_<timestamp>_<pid>.ai.md`

## 30 秒上手（人类 + AI）

### 人类快速看结果

```bash
~/projects/mitm-captures/startCaptures.sh
# 执行你的业务操作
~/projects/mitm-captures/stopCaptures.sh
less captures/latest.summary.md
```

如需深入回放：

```bash
mitmweb -r captures/latest.flow
```

### AI 快速分析

```bash
~/projects/mitm-captures/startCaptures.sh
# 执行业务操作
~/projects/mitm-captures/stopCaptures.sh
~/projects/mitm-captures/ai.sh
```

默认会生成：`captures/latest.ai.bundle.txt`。
把这个文件整体贴给 AI，通常最省心、最稳定。

## 安全提示

- 抓包文件通常包含 Cookie、Token、请求体、响应体与内部接口路径
- 不要把 `captures/`、`.har`、`.flow`、`.log` 提交到业务仓库或公开仓库
- 对外分享问题样本前，先确认已做脱敏或改用摘要类产物（如 `summary.md`、`ai.md`）

## 验证与 CI

本仓库当前通过两类验证：

- 本地静态回归：`python3 -m unittest tests.test_windows_bat_static`
- GitHub Actions：
  - `ubuntu-latest` / `macos-latest` / `windows-latest` 都会安装 `mitmproxy` 并真实跑一遍 smoke test
  - smoke test 会执行 `start -> 真实经过代理的 HTTP 请求 -> stop -> ai`，并校验 `latest.*` 产物全部落地
  - 同时保留 shell / Python 语法校验与 Windows 批处理静态契约测试

最小本地验证命令：

```bash
python3 -m unittest tests.test_windows_bat_static
bash -n startCaptures.sh stopCaptures.sh analyzeLatest.sh ai.sh
python3 -m py_compile .har_addon.py flow2har.py flow_report.py ai_brief.py
python3 tests/runtime_smoke.py --entrypoint shell
```

## startCaptures.sh

### 用法

```bash
./startCaptures.sh [options]
```

### 选项

- `-p, --program`: 程序模式，不改系统代理
- `-H, --host <host>`: 监听地址，默认 `127.0.0.1`
- `-P, --port <port>`: 监听端口，默认 `18080`
- `-d, --dir <path>`: 输出目录，默认当前目录
- `--force-recover`: 自动清理僵尸 `proxy_info.env`
- `-h, --help`: 查看帮助

### 安全与恢复机制

- 使用 `captures/.capture.lock` 防止并发 start/stop 竞争
- 已存在活跃 PID 时拒绝重复启动
- 检测到僵尸状态文件时要求显式 `--force-recover`
- 启动失败会自动清理子进程，并尝试恢复代理
- `proxy_info.env` 通过临时文件原子写入

## stopCaptures.sh

### 用法

```bash
./stopCaptures.sh [options]
```

### 选项

- `-d, --dir <path>`: 目标目录，默认当前目录
- `--keep-env`: 保留 `proxy_info.env` 便于排查
- `--har-backend <name>`: `auto|mitmdump|python`，默认 `auto`
- `--no-har`: 跳过 HAR 导出
- `-h, --help`: 查看帮助

### 幂等行为

- `proxy_info.env` 不存在时返回成功（提示 “Nothing to stop”）
- PID 不存在/无效不会导致脚本异常退出
- 失败项（如 kill 失败、代理恢复失败、HAR 导出失败）会在 summary 中标出并返回 `exit 2`

## HAR 转换行为

默认行为：
- 跳过静态资源（图片、字体、css/js、媒体等）
- 文本响应写入正文，二进制响应写入 `[binary content not captured]`
- 请求/响应正文保持抓包原始内容（不做脱敏、截断）

## 自动分析产物

在 `stopCaptures.sh` 执行时，会在不修改 raw 数据的前提下自动生成：

- `manifest.json`: 本次会话元数据与产物路径（包含 raw 不可变策略声明）
- `index.ndjson`: 每条请求的检索索引（method/host/path/status/duration/bytes）
- `summary.md`: 快速摘要（状态分布、Top Host、最慢请求 Top20）
- `ai.json`: 结构化 AI 输入（关键统计、异常端点、慢请求、建议分析目标）
- `ai.md`: 可直接复制给 AI 的分析 brief（含 prompt 模板）

这些文件是分析视图，不会覆盖或改写 `.flow`。

## 给 AI 的推荐输入顺序

1. 先给 `ai.md`（让 AI 快速建立分析框架）
2. 再给 `ai.json`（让 AI 做结构化统计推理）
3. 必要时补 `index.ndjson`（细粒度筛查）
4. 最后回到 `flow`/`har` 做证据核对

## analyzeLatest.sh

```bash
./analyzeLatest.sh [options]
```

- `-d, --dir <path>`: 目标目录，默认当前目录
- `-o, --out <path>`: 输出文件，默认 `captures/latest.ai.bundle.txt`
- `--stdout`: 生成后直接输出到终端

最常用：

```bash
~/projects/mitm-captures/analyzeLatest.sh --stdout
```

最短入口：

```bash
~/projects/mitm-captures/ai.sh
```

## 常见问题

### 1) 启动提示已有会话

说明 `captures/proxy_info.env` 存在且 PID 仍可用。请先执行：

```bash
~/projects/mitm-captures/stopCaptures.sh
```

若 PID 已失效但状态文件残留：

```bash
~/projects/mitm-captures/startCaptures.sh --force-recover
```

### 2) 代理没有恢复

请看 `stop` summary 里的 `Proxy restore` 字段。若是 `restore-failed`：
- 确认当前会话可执行 `gsettings`
- 手动执行：

```bash
gsettings set org.gnome.system.proxy mode 'none'
```

### 3) HAR 生成失败

尝试显式切换后端：

```bash
~/projects/mitm-captures/stopCaptures.sh --har-backend python
```

## 建议实践

- 将 `captures/` 加入你的项目 `.gitignore`
- 把 `.har` 当作敏感数据管理（包含请求和返回内容）
- 提 issue 或 PR 前先跑一遍最小本地验证，确保与 GitHub Actions 一致

## 贡献

协作约束见 [CONTRIBUTING.md](CONTRIBUTING.md)。
