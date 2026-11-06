"""第 7 步：大模型接入（DeepSeek）

DeepSeek 兼容 OpenAI 协议，所以用 openai SDK、把 base_url 指过去即可。
以后要换成通义、Kimi、OpenAI，只改 base_url + model，代码不用动。

API key 只从环境变量读，绝不写进代码：

    Windows 永久设置（之后重开终端生效）:
        setx DEEPSEEK_API_KEY "sk-你的key"

    当前 shell 临时设置:
        export DEEPSEEK_API_KEY=sk-你的key

可选覆盖（一般不用动）:
    DEEPSEEK_BASE_URL   默认 https://api.deepseek.com
    DEEPSEEK_MODEL      默认 deepseek-chat（deepseek-reasoner 是推理模型，更慢）
"""

import asyncio
import os

BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")

SYSTEM_PROMPT = """你是一个严谨的问答助手。请严格依据下面提供的「参考资料」回答问题。

规则：
1. 只使用参考资料中的信息，不要编造任何资料里没有的内容。
2. 如果参考资料不足以回答问题，直接回答"根据已有资料无法回答"，不要猜测。
3. 回答简洁明确，并在引用了某条资料的地方用 [编号] 标注，例如 [1]。
4. 使用中文回答。
5. 排版用 Markdown（前端会渲染），遵守以下约束：
   - 可用：标题（最多到 ###，不要用 # 和 ##）、有序/无序列表、任务列表、**加粗**、`行内代码`,
     代码块（首行标注语言，如 ```java）、> 引用块、表格。
   - 加粗标记内侧不留空格：写 **加粗**，不要写 ** 加粗 **。
   - 标题、列表、代码块、表格前面留一个空行，避免和上一段粘在一起。
   - 不要输出 HTML 标签，不要输出图片，不要用 --- 分隔线。
"""

_client = None


# ----------------------------------------------------------------------
# 异常：交给 services 层映射成错误码（内核不认识 HTTP / 错误信封）
# ----------------------------------------------------------------------
class LlmKeyMissing(Exception):
    """未配置 DEEPSEEK_API_KEY。"""


class LlmTimeout(Exception):
    """首字节或总时长超时。"""


class LlmError(Exception):
    """其它调用失败（网络、限流、协议错误）。"""


def _get_client():
    """延迟创建异步客户端（同时校验 key 和 SDK）。"""
    global _client
    if _client is None:
        api_key = os.getenv("DEEPSEEK_API_KEY")
        if not api_key:
            raise LlmKeyMissing("未配置 DEEPSEEK_API_KEY")
        try:
            from openai import AsyncOpenAI
        except ImportError as exc:  # pragma: no cover
            raise LlmError("未安装 openai SDK") from exc
        _client = AsyncOpenAI(api_key=api_key, base_url=BASE_URL)
    return _client


# ----------------------------------------------------------------------
# 提示词组装
# ----------------------------------------------------------------------
def format_context(chunks: list[dict]) -> str:
    """把检索结果拼成带编号的参考资料。"""
    blocks = []
    for i, c in enumerate(chunks, 1):
        page = c.get("page")
        where = f"，第 {page} 页" if page else ""
        blocks.append(f"[{i}] {c.get('source') or '未知来源'}{where}\n{c.get('content', '')}")
    return "\n\n".join(blocks)


def build_messages(
    question: str, chunks: list[dict], history: list[dict] | None = None
) -> list[dict]:
    """system + 历史（按角色交替）+ 最后一条 user（参考资料 + 本轮问题）。

    历史**不进**"参考资料"区：混在一起会被模型当成证据，绕过 SYSTEM_PROMPT
    第 1 条"只使用参考资料"（10.多轮会话设计 §6.3/§6.4）。
    """
    context = format_context(chunks) if chunks else "（没有检索到任何资料）"
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    for h in history or []:
        role = h.get("role")
        content = (h.get("content") or "").strip()
        if role in ("user", "assistant") and content:
            messages.append({"role": role, "content": content})
    messages.append({"role": "user", "content": f"参考资料：\n{context}\n\n问题：{question}"})
    return messages


# ----------------------------------------------------------------------
# 调用（全部异步：AsyncOpenAI + async for，02 §5.3 P-4）
# ----------------------------------------------------------------------
def _delta_text(chunk) -> str:
    if not getattr(chunk, "choices", None):
        return ""
    delta = chunk.choices[0].delta
    return (getattr(delta, "content", None) or "")


async def chat(
    messages: list[dict],
    temperature: float = 0.3,
    max_tokens: int = 1024,
    timeout_total: float = 60.0,
) -> str:
    """一次性拿到完整回答。"""
    client = _get_client()
    try:
        async with asyncio.timeout(timeout_total):
            resp = await client.chat.completions.create(
                model=MODEL,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                timeout=timeout_total,
            )
    except TimeoutError as exc:
        raise LlmTimeout("大模型响应超时") from exc
    except Exception as exc:
        raise LlmError(str(exc)) from exc
    return resp.choices[0].message.content or ""


async def chat_stream(
    messages: list[dict],
    temperature: float = 0.3,
    max_tokens: int = 1024,
    timeout_first: float = 15.0,
    timeout_total: float = 60.0,
):
    """流式回答（异步生成器）：首字节 15 s / 总时长 60 s（06 A1）。"""
    client = _get_client()
    try:
        stream = await client.chat.completions.create(
            model=MODEL,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=True,
            timeout=timeout_total,
        )
    except TimeoutError as exc:
        raise LlmTimeout("大模型响应超时") from exc
    except Exception as exc:
        raise LlmError(str(exc)) from exc

    iterator = stream.__aiter__()
    try:
        async with asyncio.timeout(timeout_total):
            try:
                first = await asyncio.wait_for(iterator.__anext__(), timeout=timeout_first)
            except StopAsyncIteration:
                return
            text = _delta_text(first)
            if text:
                yield text
            async for chunk in iterator:
                text = _delta_text(chunk)
                if text:
                    yield text
    except TimeoutError as exc:
        raise LlmTimeout("大模型响应超时") from exc
    except Exception as exc:
        raise LlmError(str(exc)) from exc


async def answer(
    question: str,
    chunks: list[dict],
    stream: bool = False,
    history: list[dict] | None = None,
    temperature: float = 0.3,
    max_tokens: int = 1024,
    timeout_first: float = 15.0,
    timeout_total: float = 60.0,
):
    """RAG 回答入口：问题 + 检索结果 → 回答。

    stream=True  返回**异步生成器**（需 `agen = await answer(...)` 再 `async for`）
    stream=False 返回完整字符串
    """
    messages = build_messages(question, chunks, history)
    if stream:
        return chat_stream(
            messages,
            temperature=temperature,
            max_tokens=max_tokens,
            timeout_first=timeout_first,
            timeout_total=timeout_total,
        )
    return await chat(messages, temperature=temperature, max_tokens=max_tokens, timeout_total=timeout_total)
