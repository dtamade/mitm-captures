# Contributing

感谢贡献。

## 提交边界

- 保持改动聚焦，不把功能修复、风格清理、文档改写混在同一个提交里
- 不要提交 `captures/`、`.har`、`.flow`、`.log` 或任何真实抓包数据
- 不要把 API Key、Cookie、Token、证书私钥或脱敏不充分的样本带进仓库

## 本地验证

提交前至少执行：

```bash
python3 -m unittest discover -s tests
bash -n startCaptures.sh stopCaptures.sh analyzeLatest.sh ai.sh
python3 -m py_compile .har_addon.py flow2har.py flow_report.py ai_brief.py state_import.py tests/runtime_smoke.py
python3 tests/runtime_smoke.py --entrypoint shell --proxy-mode program
TMP_HOME="$(mktemp -d)" && mkdir -p "$TMP_HOME/.config" "$TMP_HOME/.local/share" && XDG_CONFIG_HOME="$TMP_HOME/.config" XDG_DATA_HOME="$TMP_HOME/.local/share" dbus-run-session -- python3 tests/runtime_smoke.py --entrypoint shell --proxy-mode system
```

Windows 贡献者如果主要修改 `mitm-captures.bat`，也应确保上述 Python 静态测试通过。

## 文本与换行

- 仓库默认文本文件使用 LF
- `*.bat` 通过 `.gitattributes` 固定为 CRLF，避免 Windows 批处理在跨平台协作时反复改脏

## Pull Request

- 说明你改了什么、为什么改
- 如果改动影响 Windows 入口、代理恢复、latest 产物或锁机制，请在描述里写出验证方式
