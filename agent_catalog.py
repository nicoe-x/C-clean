"""Offline product directory catalog. A name match alone never permits cleanup.

Sources identify the products and their storage conventions; desktop aliases are
candidate paths, not claims that every version uses every path. Chromium cache
layout must be present before a new desktop root permits cache cleanup.
"""
from dataclasses import dataclass
import os
from pathlib import Path
import re


@dataclass(frozen=True)
class Desktop:
    name: str
    aliases: tuple[str, ...]
    source: str


DESKTOPS = (
    Desktop('Codex', ('Codex', 'OpenAI/Codex'), 'https://developers.openai.com/codex/app/'),
    Desktop('Claude', ('Claude',), 'https://claude.com/download'),
    Desktop('ChatGPT', ('ChatGPT', 'OpenAI/ChatGPT'), 'https://chatgpt.com/download/'),
    Desktop('Cursor', ('Cursor',), 'https://docs.cursor.com/'),
    Desktop('Windsurf', ('Windsurf',), 'https://docs.windsurf.com/'),
    Desktop('Antigravity', ('Antigravity',), 'https://antigravity.google/'),
    Desktop('VS Code', ('Code', 'Code - Insiders'), 'https://code.visualstudio.com/docs/setup/windows'),
    Desktop('Trae', ('Trae', 'Trae CN'), 'https://www.trae.cn/'),
    Desktop('CodeBuddy', ('CodeBuddy', 'CodeBuddy CN'), 'https://www.codebuddy.cn/'),
    Desktop('WorkBuddy', ('WorkBuddy', 'Tencent WorkBuddy'), 'https://www.codebuddy.cn/docs/workbuddy/From-Beginner-to-Expert-Guide/FAQ'),
    Desktop('WorkBuddy AI', ('WorkBuddy AI',), 'https://www.codebuddy.ai/'),
    Desktop('ZCode', ('ZCode', 'zcode'), 'https://github.com/zai-org/ZCode'),
    Desktop('豆包', ('Doubao',), 'https://www.doubao.com/'),
    Desktop('腾讯元宝', ('Yuanbao', 'Tencent/Yuanbao'), 'https://yuanbao.tencent.com/'),
    Desktop('千问', ('Qwen', 'Qianwen'), 'https://www.qianwen.com/'),
    Desktop('Kimi', ('Kimi',), 'https://www.kimi.com/'),
    Desktop('Qoder', ('Qoder',), 'https://docs.qoder.com/'),
    Desktop('通义灵码', ('Lingma', 'Tongyi Lingma'), 'https://lingma.aliyun.com/'),
    Desktop('百度 Comate', ('Comate', 'Baidu Comate'), 'https://comate.baidu.com/'),
    Desktop('CodeArts', ('CodeArts', 'CodeArts Snap'), 'https://www.huaweicloud.com/product/codeartside.html'),
    Desktop('Kiro', ('Kiro',), 'https://kiro.dev/docs/'),
    Desktop('PearAI', ('PearAI',), 'https://github.com/trypear/pearai-app'),
    Desktop('Void', ('Void',), 'https://github.com/voideditor/void'),
    Desktop('VSCodium', ('VSCodium',), 'https://github.com/VSCodium/vscodium'),
    Desktop('Cherry Studio', ('Cherry Studio', 'cherry-studio'), 'https://github.com/CherryHQ/cherry-studio'),
    Desktop('Chatbox', ('Chatbox', 'xyz.chatboxapp.ce'), 'https://github.com/chatboxai/chatbox'),
    Desktop('LobeHub', ('LobeHub', 'lobehub-desktop'), 'https://github.com/lobehub/lobehub'),
    Desktop('AnythingLLM', ('anythingllm-desktop', 'AnythingLLM'), 'https://github.com/Mintplex-Labs/anything-llm'),
    Desktop('Msty', ('Msty',), 'https://msty.ai/'),
    Desktop('LM Studio', ('LM Studio', 'lm-studio'), 'https://lmstudio.ai/docs/'),
    Desktop('Ollama', ('ollama app.exe', 'Ollama'), 'https://docs.ollama.com/windows'),
    Desktop('Jan', ('Jan', 'jan.ai.app'), 'https://github.com/janhq/jan'),
    Desktop('GPT4All', ('nomic.ai/GPT4All', 'GPT4All'), 'https://docs.gpt4all.io/'),
    Desktop('Hermes Desktop', ('Hermes',), 'https://github.com/NousResearch/hermes-agent/tree/main/apps/desktop'),
    Desktop('Goose Desktop', ('Goose',), 'https://github.com/block/goose'),
    Desktop('ClawX', ('ClawX', 'clawx'), 'https://github.com/ValueCell-ai/ClawX'),
    Desktop('LobsterAI', ('LobsterAI', 'lobsterai'), 'https://github.com/netease-youdao/LobsterAI'),
    Desktop('QClaw', ('QClaw', 'Tencent/QClaw'), 'https://qclaw.qq.com/'),
    Desktop('AutoClaw', ('AutoClaw',), 'https://autoglm.zhipuai.cn/'),
)


@dataclass(frozen=True)
class StateApp:
    name: str
    roots: tuple[str, ...]
    logs: tuple[str, ...]
    source: str
    environments: tuple[str, ...] = ()
    profiles: bool = False


# State roots are ALWAYS read-only, even if called cache/tmp. Only the exact
# diagnostic-log children listed here may become manual cleanup targets.
STATES = (
    StateApp('Codex CLI', ('home:.codex',), ('log',), 'https://developers.openai.com/codex/config-reference/', ('CODEX_HOME',)),
    StateApp('Claude Code', ('home:.claude',), ('debug',), 'https://code.claude.com/docs/en/how-claude-code-works', ('CLAUDE_CONFIG_DIR',)),
    StateApp('OpenClaw', ('home:.openclaw', 'home:.clawdbot', 'home:.moltbot'), ('logs',), 'https://docs.openclaw.ai/help/faq/where-things-live-on-disk', ('OPENCLAW_STATE_DIR',), True),
    StateApp('Hermes Agent', ('home:.hermes',), ('logs',), 'https://github.com/NousResearch/hermes-agent/blob/main/hermes_constants.py', ('HERMES_HOME',), True),
    StateApp('Gemini CLI', ('home:.gemini',), (), 'https://github.com/google-gemini/gemini-cli/blob/main/docs/cli/session-management.md', ('GEMINI_CLI_HOME',)),
    StateApp('Qwen Code', ('home:.qwen',), (), 'https://github.com/QwenLM/qwen-code/blob/main/packages/core/src/config/storage.ts'),
    StateApp('Kimi Code', ('home:.kimi', 'home:.kimi-code'), ('logs',), 'https://github.com/MoonshotAI/kimi-cli/blob/main/docs/en/configuration/data-locations.md', ('KIMI_SHARE_DIR', 'KIMI_CODE_HOME')),
    StateApp('OpenCode', ('home:.local/share/opencode', 'home:.config/opencode', 'home:.cache/opencode', 'local:opencode'), ('log',), 'https://opencode.ai/docs/troubleshooting/'),
    StateApp('Goose', ('home:.config/goose', 'home:.local/share/goose', 'home:.local/state/goose', 'roaming:Block/goose', 'local:Block/goose'), (), 'https://github.com/block/goose/blob/main/crates/goose/src/config/paths.rs'),
    StateApp('Crush', ('home:.local/share/crush', 'home:.config/crush', 'local:crush', 'roaming:crush'), (), 'https://github.com/charmbracelet/crush'),
    StateApp('GitHub Copilot CLI', ('home:.copilot',), ('logs',), 'https://docs.github.com/en/copilot/how-tos/copilot-cli'),
    StateApp('Continue', ('home:.continue',), ('logs',), 'https://docs.continue.dev/troubleshooting'),
    StateApp('CodeBuddy CLI', ('home:.codebuddy', 'local:CodeBuddyExtension', 'roaming:CodeBuddyExtension'), (), 'https://www.codebuddy.cn/docs/'),
    StateApp('WorkBuddy', ('home:.workbuddy',), ('logs',), 'https://www.codebuddy.cn/docs/workbuddy/From-Beginner-to-Expert-Guide/FAQ'),
    StateApp('WorkBuddy AI', ('home:.workbuddy-ai',), ('logs',), 'https://www.codebuddy.ai/'),
    StateApp('ZCode', ('home:.zcode',), (), 'https://github.com/zai-org/ZCode', ('ZCODE_HOME', 'ZCODE_DESKTOP_USER_DATA_DIR', 'ZCODE_DESKTOP_SESSION_DATA_DIR')),
    StateApp('Qoder CLI', ('home:.qoder',), (), 'https://docs.qoder.com/'),
    StateApp('Kiro CLI', ('home:.kiro',), (), 'https://kiro.dev/docs/'),
    StateApp('Amazon Q', ('home:.aws/amazonq', 'home:.amazonq'), (), 'https://docs.aws.amazon.com/amazonq/latest/qdeveloper-ug/'),
    StateApp('ClawX', ('home:.clawx',), (), 'https://github.com/ValueCell-ai/ClawX/blob/main/electron/utils/paths.ts', ('CLAWX_USER_DATA_DIR',)),
    StateApp('OpenHands', ('home:.openhands', 'home:.open-devin'), (), 'https://docs.openhands.dev/'),
    StateApp('Cline', ('home:.cline',), (), 'https://docs.cline.bot/'),
    StateApp('Roo Code', ('home:.roo',), (), 'https://docs.roocode.com/'),
    StateApp('Auggie', ('home:.augment',), (), 'https://docs.augmentcode.com/cli/overview'),
    StateApp('Amp', ('home:.config/amp', 'home:.local/share/amp'), (), 'https://ampcode.com/manual'),
    StateApp('Droid', ('home:.factory',), (), 'https://docs.factory.ai/cli/getting-started/overview'),
    StateApp('Pi', ('home:.pi',), (), 'https://github.com/badlogic/pi-mono'),
    StateApp('PicoClaw', ('home:.picoclaw',), (), 'https://github.com/sipeed/picoclaw'),
    StateApp('nanobot', ('home:.nanobot',), (), 'https://github.com/HKUDS/nanobot/blob/main/docs/configuration.md'),
    StateApp('ZeroClaw', ('home:.zeroclaw',), (), 'https://github.com/zeroclaw-labs/zeroclaw/tree/master'),
    StateApp('OpenFang', ('home:.openfang',), (), 'https://github.com/RightNow-AI/openfang/blob/main/crates/openfang-types/src/config.rs', ('OPENFANG_HOME',)),
    StateApp('iFlow', ('home:.iflow',), (), 'https://github.com/iflow-ai/iflow-cli'),
    StateApp('Qoder', ('home:.qoderwork',), (), 'https://docs.qoder.com/'),
    StateApp('Jan', ('home:.jan', 'roaming:jan.ai.app'), (), 'https://github.com/janhq/jan'),
    StateApp('LM Studio', ('home:.lmstudio',), (), 'https://lmstudio.ai/docs/'),
    StateApp('Ollama', ('home:.ollama',), (), 'https://docs.ollama.com/windows'),
    StateApp('Hugging Face', ('home:.cache/huggingface/hub',), (), 'https://huggingface.co/docs/huggingface_hub/guides/manage-cache'),
    StateApp('ModelScope', ('home:.cache/modelscope/hub',), (), 'https://github.com/modelscope/modelscope'),
    StateApp('Whisper', ('home:.cache/whisper',), (), 'https://github.com/openai/whisper'),
)

RENDER_CACHES = ('Cache', 'Code Cache', 'GPUCache', 'DawnCache', 'DawnGraphiteCache',
                 'DawnWebGPUCache', 'GPUPersistentCache', 'GrShaderCache', 'ShaderCache')
CHROMIUM_MARKERS = ('Cache/Cache_Data/index', 'Cache/index', 'Code Cache/js/index',
                    'Code Cache/wasm/index', 'GPUCache/index')

EXTENSIONS = (
    ('Cline', 'saoudrizwan.claude-dev', 'https://docs.cline.bot/'),
    ('Roo Code', 'rooveterinaryinc.roo-cline', 'https://docs.roocode.com/'),
    ('Continue', 'continue.continue', 'https://docs.continue.dev/'),
    ('GitHub Copilot', 'github.copilot-chat', 'https://docs.github.com/en/copilot'),
    ('通义灵码', 'alibaba-cloud.tongyi-lingma', 'https://lingma.aliyun.com/'),
    ('CodeGeeX', 'aminer.codegeex', 'https://codegeex.cn/'),
    ('百度 Comate', 'baidu.comate', 'https://comate.baidu.com/'),
    ('CodeBuddy', 'tencent-cloud.coding-copilot', 'https://www.codebuddy.cn/'),
    ('Amazon Q', 'amazonwebservices.amazon-q-vscode', 'https://aws.amazon.com/q/developer/'),
    ('Auggie', 'augment.vscode-augment', 'https://docs.augmentcode.com/'),
)


def locations():
    home = Path.home()
    return {'home': home, 'roaming': Path(os.environ.get('APPDATA', str(home/'AppData/Roaming'))),
            'local': Path(os.environ.get('LOCALAPPDATA', str(home/'AppData/Local')))}


def state_roots(app, bases):
    roots = [(bases[key]/suffix, False) for key, suffix in (p.split(':', 1) for p in app.roots)]
    for variable in app.environments:
        raw = os.environ.get(variable, '').strip()
        if raw:
            path = Path(raw).expanduser()
            if path.is_absolute() and '..' not in path.parts:
                roots.append((path, True))  # redirected roots never grant deletion
    return roots


def profile_name(name):
    return name == 'Default' or bool(re.fullmatch(r'Profile [0-9]+', name))


def products():
    """Inspectable catalog, including products absent from this computer."""
    result = {}
    for product in (*DESKTOPS, *STATES):
        row = result.setdefault(product.name, {'name': product.name, 'sources': [], 'paths': [], 'cleanup': False})
        if product.source not in row['sources']: row['sources'].append(product.source)
        if isinstance(product, Desktop):
            row['paths'].extend('%APPDATA% / %LOCALAPPDATA% / '+a for a in product.aliases)
            row['cleanup'] = True
        else:
            row['paths'].extend(product.roots)
            row['cleanup'] |= bool(product.logs)
    for name, extension, source in EXTENSIONS:
        row = result.setdefault(name, {'name': name, 'sources': [], 'paths': [], 'cleanup': False})
        row['paths'].append('User/globalStorage/'+extension)
        if source not in row['sources']: row['sources'].append(source)
    return sorted(result.values(), key=lambda r:r['name'].casefold())
