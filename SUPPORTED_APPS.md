# 支持列表

共 72 项识别规则。仅显示 C 盘中实际存在的目录；桌面端候选路径须通过缓存结构检查才开放清理。

缓存识别：仅独立渲染缓存；日志手选：不加入推荐全选；仅统计：保留会话、配置、技能、模型和运行时。

通过「支持列表 → 添加目录」可分析其他工具或自定义位置，添加的目录仅统计，重启后需重新添加。WSL、Docker、远程机器和非 C 盘数据不自动扫描；不保证覆盖所有产品和版本。

| 应用 | 范围 | 候选位置 | 来源 |
| --- | --- | --- | --- |
| Amazon Q | 仅统计 | `home:.aws/amazonq`<br>`home:.amazonq`<br>`User/globalStorage/amazonwebservices.amazon-q-vscode` | [来源 1](https://docs.aws.amazon.com/amazonq/latest/qdeveloper-ug/)、[来源 2](https://aws.amazon.com/q/developer/) |
| Amp | 仅统计 | `home:.config/amp`<br>`home:.local/share/amp` | [来源 1](https://ampcode.com/manual) |
| Antigravity | 缓存识别 / 数据统计 | `%APPDATA% / %LOCALAPPDATA% / Antigravity` | [来源 1](https://antigravity.google/) |
| AnythingLLM | 缓存识别 / 数据统计 | `%APPDATA% / %LOCALAPPDATA% / anythingllm-desktop`<br>`%APPDATA% / %LOCALAPPDATA% / AnythingLLM` | [来源 1](https://github.com/Mintplex-Labs/anything-llm) |
| Auggie | 仅统计 | `home:.augment`<br>`User/globalStorage/augment.vscode-augment` | [来源 1](https://docs.augmentcode.com/cli/overview)、[来源 2](https://docs.augmentcode.com/) |
| AutoClaw | 缓存识别 / 数据统计 | `%APPDATA% / %LOCALAPPDATA% / AutoClaw` | [来源 1](https://autoglm.zhipuai.cn/) |
| Chatbox | 缓存识别 / 数据统计 | `%APPDATA% / %LOCALAPPDATA% / Chatbox`<br>`%APPDATA% / %LOCALAPPDATA% / xyz.chatboxapp.ce` | [来源 1](https://github.com/chatboxai/chatbox) |
| ChatGPT | 缓存识别 / 数据统计 | `%APPDATA% / %LOCALAPPDATA% / ChatGPT`<br>`%APPDATA% / %LOCALAPPDATA% / OpenAI/ChatGPT` | [来源 1](https://chatgpt.com/download/) |
| Cherry Studio | 缓存识别 / 数据统计 | `%APPDATA% / %LOCALAPPDATA% / Cherry Studio`<br>`%APPDATA% / %LOCALAPPDATA% / cherry-studio` | [来源 1](https://github.com/CherryHQ/cherry-studio) |
| Claude | 缓存识别 / 数据统计 | `%APPDATA% / %LOCALAPPDATA% / Claude` | [来源 1](https://claude.com/download) |
| Claude Code | 日志手选 / 数据统计 | `home:.claude` | [来源 1](https://code.claude.com/docs/en/how-claude-code-works) |
| ClawX | 缓存识别 / 数据统计 | `%APPDATA% / %LOCALAPPDATA% / ClawX`<br>`%APPDATA% / %LOCALAPPDATA% / clawx`<br>`home:.clawx` | [来源 1](https://github.com/ValueCell-ai/ClawX)、[来源 2](https://github.com/ValueCell-ai/ClawX/blob/main/electron/utils/paths.ts) |
| Cline | 仅统计 | `home:.cline`<br>`User/globalStorage/saoudrizwan.claude-dev` | [来源 1](https://docs.cline.bot/) |
| CodeArts | 缓存识别 / 数据统计 | `%APPDATA% / %LOCALAPPDATA% / CodeArts`<br>`%APPDATA% / %LOCALAPPDATA% / CodeArts Snap` | [来源 1](https://www.huaweicloud.com/product/codeartside.html) |
| CodeBuddy | 缓存识别 / 数据统计 | `%APPDATA% / %LOCALAPPDATA% / CodeBuddy`<br>`%APPDATA% / %LOCALAPPDATA% / CodeBuddy CN`<br>`User/globalStorage/tencent-cloud.coding-copilot` | [来源 1](https://www.codebuddy.cn/) |
| CodeBuddy CLI | 仅统计 | `home:.codebuddy`<br>`local:CodeBuddyExtension`<br>`roaming:CodeBuddyExtension` | [来源 1](https://www.codebuddy.cn/docs/) |
| CodeGeeX | 仅统计 | `User/globalStorage/aminer.codegeex` | [来源 1](https://codegeex.cn/) |
| Codex | 缓存识别 / 数据统计 | `%APPDATA% / %LOCALAPPDATA% / Codex`<br>`%APPDATA% / %LOCALAPPDATA% / OpenAI/Codex` | [来源 1](https://developers.openai.com/codex/app/) |
| Codex CLI | 日志手选 / 数据统计 | `home:.codex` | [来源 1](https://developers.openai.com/codex/config-reference/) |
| Continue | 日志手选 / 数据统计 | `home:.continue`<br>`User/globalStorage/continue.continue` | [来源 1](https://docs.continue.dev/troubleshooting)、[来源 2](https://docs.continue.dev/) |
| Crush | 仅统计 | `home:.local/share/crush`<br>`home:.config/crush`<br>`local:crush`<br>`roaming:crush` | [来源 1](https://github.com/charmbracelet/crush) |
| Cursor | 缓存识别 / 数据统计 | `%APPDATA% / %LOCALAPPDATA% / Cursor` | [来源 1](https://docs.cursor.com/) |
| Droid | 仅统计 | `home:.factory` | [来源 1](https://docs.factory.ai/cli/getting-started/overview) |
| Gemini CLI | 仅统计 | `home:.gemini` | [来源 1](https://github.com/google-gemini/gemini-cli/blob/main/docs/cli/session-management.md) |
| GitHub Copilot | 仅统计 | `User/globalStorage/github.copilot-chat` | [来源 1](https://docs.github.com/en/copilot) |
| GitHub Copilot CLI | 日志手选 / 数据统计 | `home:.copilot` | [来源 1](https://docs.github.com/en/copilot/how-tos/copilot-cli) |
| Goose | 仅统计 | `home:.config/goose`<br>`home:.local/share/goose`<br>`home:.local/state/goose`<br>`roaming:Block/goose`<br>`local:Block/goose` | [来源 1](https://github.com/block/goose/blob/main/crates/goose/src/config/paths.rs) |
| Goose Desktop | 缓存识别 / 数据统计 | `%APPDATA% / %LOCALAPPDATA% / Goose` | [来源 1](https://github.com/block/goose) |
| GPT4All | 缓存识别 / 数据统计 | `%APPDATA% / %LOCALAPPDATA% / nomic.ai/GPT4All`<br>`%APPDATA% / %LOCALAPPDATA% / GPT4All` | [来源 1](https://docs.gpt4all.io/) |
| Hermes Agent | 日志手选 / 数据统计 | `home:.hermes` | [来源 1](https://github.com/NousResearch/hermes-agent/blob/main/hermes_constants.py) |
| Hermes Desktop | 缓存识别 / 数据统计 | `%APPDATA% / %LOCALAPPDATA% / Hermes` | [来源 1](https://github.com/NousResearch/hermes-agent/tree/main/apps/desktop) |
| Hugging Face | 仅统计 | `home:.cache/huggingface/hub` | [来源 1](https://huggingface.co/docs/huggingface_hub/guides/manage-cache) |
| iFlow | 仅统计 | `home:.iflow` | [来源 1](https://github.com/iflow-ai/iflow-cli) |
| Jan | 缓存识别 / 数据统计 | `%APPDATA% / %LOCALAPPDATA% / Jan`<br>`%APPDATA% / %LOCALAPPDATA% / jan.ai.app`<br>`home:.jan`<br>`roaming:jan.ai.app` | [来源 1](https://github.com/janhq/jan) |
| Kimi | 缓存识别 / 数据统计 | `%APPDATA% / %LOCALAPPDATA% / Kimi` | [来源 1](https://www.kimi.com/) |
| Kimi Code | 日志手选 / 数据统计 | `home:.kimi`<br>`home:.kimi-code` | [来源 1](https://github.com/MoonshotAI/kimi-cli/blob/main/docs/en/configuration/data-locations.md) |
| Kiro | 缓存识别 / 数据统计 | `%APPDATA% / %LOCALAPPDATA% / Kiro` | [来源 1](https://kiro.dev/docs/) |
| Kiro CLI | 仅统计 | `home:.kiro` | [来源 1](https://kiro.dev/docs/) |
| LM Studio | 缓存识别 / 数据统计 | `%APPDATA% / %LOCALAPPDATA% / LM Studio`<br>`%APPDATA% / %LOCALAPPDATA% / lm-studio`<br>`home:.lmstudio` | [来源 1](https://lmstudio.ai/docs/) |
| LobeHub | 缓存识别 / 数据统计 | `%APPDATA% / %LOCALAPPDATA% / LobeHub`<br>`%APPDATA% / %LOCALAPPDATA% / lobehub-desktop` | [来源 1](https://github.com/lobehub/lobehub) |
| LobsterAI | 缓存识别 / 数据统计 | `%APPDATA% / %LOCALAPPDATA% / LobsterAI`<br>`%APPDATA% / %LOCALAPPDATA% / lobsterai` | [来源 1](https://github.com/netease-youdao/LobsterAI) |
| ModelScope | 仅统计 | `home:.cache/modelscope/hub` | [来源 1](https://github.com/modelscope/modelscope) |
| Msty | 缓存识别 / 数据统计 | `%APPDATA% / %LOCALAPPDATA% / Msty` | [来源 1](https://msty.ai/) |
| nanobot | 仅统计 | `home:.nanobot` | [来源 1](https://github.com/HKUDS/nanobot/blob/main/docs/configuration.md) |
| Ollama | 缓存识别 / 数据统计 | `%APPDATA% / %LOCALAPPDATA% / ollama app.exe`<br>`%APPDATA% / %LOCALAPPDATA% / Ollama`<br>`home:.ollama` | [来源 1](https://docs.ollama.com/windows) |
| OpenClaw | 日志手选 / 数据统计 | `home:.openclaw`<br>`home:.clawdbot`<br>`home:.moltbot` | [来源 1](https://docs.openclaw.ai/help/faq/where-things-live-on-disk) |
| OpenCode | 日志手选 / 数据统计 | `home:.local/share/opencode`<br>`home:.config/opencode`<br>`home:.cache/opencode`<br>`local:opencode` | [来源 1](https://opencode.ai/docs/troubleshooting/) |
| OpenFang | 仅统计 | `home:.openfang` | [来源 1](https://github.com/RightNow-AI/openfang/blob/main/crates/openfang-types/src/config.rs) |
| OpenHands | 仅统计 | `home:.openhands`<br>`home:.open-devin` | [来源 1](https://docs.openhands.dev/) |
| PearAI | 缓存识别 / 数据统计 | `%APPDATA% / %LOCALAPPDATA% / PearAI` | [来源 1](https://github.com/trypear/pearai-app) |
| Pi | 仅统计 | `home:.pi` | [来源 1](https://github.com/badlogic/pi-mono) |
| PicoClaw | 仅统计 | `home:.picoclaw` | [来源 1](https://github.com/sipeed/picoclaw) |
| QClaw | 缓存识别 / 数据统计 | `%APPDATA% / %LOCALAPPDATA% / QClaw`<br>`%APPDATA% / %LOCALAPPDATA% / Tencent/QClaw` | [来源 1](https://qclaw.qq.com/) |
| Qoder | 缓存识别 / 数据统计 | `%APPDATA% / %LOCALAPPDATA% / Qoder`<br>`home:.qoderwork` | [来源 1](https://docs.qoder.com/) |
| Qoder CLI | 仅统计 | `home:.qoder` | [来源 1](https://docs.qoder.com/) |
| Qwen Code | 仅统计 | `home:.qwen` | [来源 1](https://github.com/QwenLM/qwen-code/blob/main/packages/core/src/config/storage.ts) |
| Roo Code | 仅统计 | `home:.roo`<br>`User/globalStorage/rooveterinaryinc.roo-cline` | [来源 1](https://docs.roocode.com/) |
| Trae | 缓存识别 / 数据统计 | `%APPDATA% / %LOCALAPPDATA% / Trae`<br>`%APPDATA% / %LOCALAPPDATA% / Trae CN` | [来源 1](https://www.trae.cn/) |
| Void | 缓存识别 / 数据统计 | `%APPDATA% / %LOCALAPPDATA% / Void` | [来源 1](https://github.com/voideditor/void) |
| VS Code | 缓存识别 / 数据统计 | `%APPDATA% / %LOCALAPPDATA% / Code`<br>`%APPDATA% / %LOCALAPPDATA% / Code - Insiders` | [来源 1](https://code.visualstudio.com/docs/setup/windows) |
| VSCodium | 缓存识别 / 数据统计 | `%APPDATA% / %LOCALAPPDATA% / VSCodium` | [来源 1](https://github.com/VSCodium/vscodium) |
| Whisper | 仅统计 | `home:.cache/whisper` | [来源 1](https://github.com/openai/whisper) |
| Windsurf | 缓存识别 / 数据统计 | `%APPDATA% / %LOCALAPPDATA% / Windsurf` | [来源 1](https://docs.windsurf.com/) |
| WorkBuddy | 缓存识别 / 数据统计 | `%APPDATA% / %LOCALAPPDATA% / WorkBuddy`<br>`%APPDATA% / %LOCALAPPDATA% / Tencent WorkBuddy`<br>`home:.workbuddy` | [来源 1](https://www.codebuddy.cn/docs/workbuddy/From-Beginner-to-Expert-Guide/FAQ) |
| WorkBuddy AI | 缓存识别 / 数据统计 | `%APPDATA% / %LOCALAPPDATA% / WorkBuddy AI`<br>`home:.workbuddy-ai` | [来源 1](https://www.codebuddy.ai/) |
| ZCode | 缓存识别 / 数据统计 | `%APPDATA% / %LOCALAPPDATA% / ZCode`<br>`%APPDATA% / %LOCALAPPDATA% / zcode`<br>`home:.zcode` | [来源 1](https://github.com/zai-org/ZCode) |
| ZeroClaw | 仅统计 | `home:.zeroclaw` | [来源 1](https://github.com/zeroclaw-labs/zeroclaw/tree/master) |
| 千问 | 缓存识别 / 数据统计 | `%APPDATA% / %LOCALAPPDATA% / Qwen`<br>`%APPDATA% / %LOCALAPPDATA% / Qianwen` | [来源 1](https://www.qianwen.com/) |
| 百度 Comate | 缓存识别 / 数据统计 | `%APPDATA% / %LOCALAPPDATA% / Comate`<br>`%APPDATA% / %LOCALAPPDATA% / Baidu Comate`<br>`User/globalStorage/baidu.comate` | [来源 1](https://comate.baidu.com/) |
| 腾讯元宝 | 缓存识别 / 数据统计 | `%APPDATA% / %LOCALAPPDATA% / Yuanbao`<br>`%APPDATA% / %LOCALAPPDATA% / Tencent/Yuanbao` | [来源 1](https://yuanbao.tencent.com/) |
| 豆包 | 缓存识别 / 数据统计 | `%APPDATA% / %LOCALAPPDATA% / Doubao` | [来源 1](https://www.doubao.com/) |
| 通义灵码 | 缓存识别 / 数据统计 | `%APPDATA% / %LOCALAPPDATA% / Lingma`<br>`%APPDATA% / %LOCALAPPDATA% / Tongyi Lingma`<br>`User/globalStorage/alibaba-cloud.tongyi-lingma` | [来源 1](https://lingma.aliyun.com/) |
