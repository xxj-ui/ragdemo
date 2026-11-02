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

import os

BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")

SYSTEM_PROMPT = """你是一个严谨的问答助手。请严格依据下面提供的「参考资料」回答问题。

规则：
1. 只使用参考资料中的信息，不要编造任何资料里没有的内容。
2. 如果参考资料不足以回答问题，直接回答"根据已有资料无法回答"，不要猜测。
3. 回答简洁明确，并在引用了某条资料的地方用 [编号] 标注，例如 [1]。
4. 使用中文回答。
"""

_client = None


def _get_client():
    """延迟创建客户端（同时校验 key 和 SDK）。"""
    global _client
    if _client is None:
        api_key = os.getenv("DEEPSEEK_API_KEY")
        if not api_key:
            raise RuntimeError(
                "缺少 DEEPSEEK_API_KEY 环境变量。\n"
                '  永久设置: setx DEEPSEEK_API_KEY "sk-..."（之后重开终端）\n'
                "  临时设置: export DEEPSEEK_API_KEY=sk-..."
            )
        try:
            from openai import OpenAI
        except ImportError as e:
            raise ImportError("缺少 openai SDK，请先安装：pip install openai") from e

        _client = OpenAI(
            api_key=api_key,
            base_url=BASE_URL,
            timeout=60,
            max_retries=2,   # SDK 自带重试，应对偶发网络错误
        )
    return _client


# ----------------------------------------------------------------------
# 提示词组装
# ----------------------------------------------------------------------


def format_context(chunks: list[dict]) -> str:
    """把检索到的 chunk 拼成带编号的参考资料。"""
    parts = []
    for i, c in enumerate(chunks, 1):
        source = c.get("source") or "未知来源"
        page = c.get("page")
        where = f"{source}" + (f" 第 {page} 页" if page else "")
        parts.append(f"[{i}] 来源: {where}\n{(c.get('content') or '').strip()}")
    return "\n\n".join(parts)


def build_messages(question: str, chunks: list[dict]) -> list[dict]:
    """组装发给大模型的 messages。"""
    context = format_context(chunks) if chunks else "（没有检索到任何资料）"
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": f"参考资料：\n{context}\n\n问题：{question}",
        },
    ]


# ----------------------------------------------------------------------
# 调用
# ----------------------------------------------------------------------


def chat(
    messages: list[dict],
    temperature: float = 0.3,
    max_tokens: int = 1024,
) -> str:
    """一次性拿到完整回答。"""
    resp = _get_client().chat.completions.create(
        model=MODEL,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
    )
    return resp.choices[0].message.content or ""


def chat_stream(
    messages: list[dict],
    temperature: float = 0.3,
    max_tokens: int = 1024,
):
    """流式回答：逐段 yield 文本，前端可以边生成边显示。"""
    stream = _get_client().chat.completions.create(
        model=MODEL,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
        stream=True,
    )
    for chunk in stream:
        if not chunk.choices:
            continue
        delta = chunk.choices[0].delta.content
        if delta:
            yield delta


def answer(
    question: str,
    chunks: list[dict],
    stream: bool = False,
    temperature: float = 0.3,
    max_tokens: int = 1024,
):
    """RAG 回答入口：问题 + 检索结果 → 回答。

    stream=True  返回生成器（逐段输出）
    stream=False 返回完整字符串
    """
    messages = build_messages(question, chunks)
    if stream:
        return chat_stream(messages, temperature=temperature, max_tokens=max_tokens)
    return chat(messages, temperature=temperature, max_tokens=max_tokens)


if __name__ == "__main__":
    # 连通性自测：不走检索，直接问一句
    import sys

    sys.stdout.reconfigure(encoding="utf-8")

    question = sys.argv[1] if len(sys.argv) > 1 else "用一句话介绍你自己"
    print(f"模型: {MODEL}")
    print(f"问题: {question}")
    print("回答: ", end="", flush=True)
    for piece in chat_stream([{"role": "user", "content": question}]):
        print(piece, end="", flush=True)
    print()
