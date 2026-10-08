"""DeepSeek 大模型客户端（OpenAI 兼容接口）+ 本地兜底回复。"""
import httpx

import config

SYSTEM_PROMPT = """你是"小颐"，一位服务于居家老人的中文语音助手。请遵守：
1. 用简短、口语化、温暖耐心的大白话回复，句子要短，方便语音朗读。
2. 不要使用 Markdown、表格、列表符号或专业术语。
3. 回复控制在 3 句话以内，重点突出。
4. 涉及健康问题不要下诊断，提醒老人及时就医或联系家人。
5. 始终对老人保持尊重和关怀。"""


async def chat_completion(messages: list[dict]) -> str:
    """调用 DeepSeek chat 接口，返回文本回复。"""
    if not config.DEEPSEEK_API_KEY:
        raise RuntimeError("未配置 DEEPSEEK_API_KEY")

    url = f"{config.DEEPSEEK_BASE_URL}/chat/completions"
    headers = {
        "Authorization": f"Bearer {config.DEEPSEEK_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": config.DEEPSEEK_MODEL,
        "messages": [{"role": "system", "content": SYSTEM_PROMPT}, *messages],
        "temperature": 0.7,
        "max_tokens": 400,
        "stream": False,
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(url, json=payload, headers=headers)
        resp.raise_for_status()
        data = resp.json()

    return data["choices"][0]["message"]["content"].strip()


def local_reply(text: str) -> str:
    """本地兜底回复：未配置 Key 或接口请求失败时使用。"""
    if any(k in text for k in ("社保", "医保", "养老金")):
        return "您好，社保查询可以用“掌上12333”APP，或者拨打12333热线电话。您具体想查什么呢？"
    if any(k in text for k in ("防跌", "跌倒", "摔跤")):
        return "预防跌倒要记住：家里地面防滑，浴室装扶手，起身慢一点，晚上走路开灯，穿防滑鞋。"
    if any(k in text for k in ("防火", "火灾", "着火")):
        return "防火要记住：做饭别离人，燃气用完要关好，别在床上抽烟，家里备个灭火器，出门记得断电。"
    if any(k in text for k in ("防诈骗", "诈骗", "骗子", "陌生电话")):
        return "防诈骗要记住：陌生电话要钱、要验证码的都不要信，有事先问家里人，别给陌生人转账。"
    if "天气" in text:
        return "我这边暂时查不到实时天气，建议您打开电视看天气预报，或者问问家里人。"
    if any(k in text for k in ("咨询", "不舒服", "难受", "头晕", "健康")):
        return "好的，请问您哪里不舒服？慢慢告诉我，我帮您看看。"
    if any(k in text for k in ("你好", "您好", "在吗")):
        return "您好，我在呢！有什么可以帮您的？"
    if "打电话" in text and any(k in text for k in ("儿子", "女儿", "家人", "孩子")):
        return "好的，我帮您呼叫家人。请问您要打给谁呢？"
    return "好的，我明白了。还有什么需要我帮忙的吗？"
