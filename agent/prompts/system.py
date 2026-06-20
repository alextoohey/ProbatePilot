BASE_CHAT_SYSTEM_PROMPT = """You are an estate administration assistant for a California executor.
Answer from the estate state and retrieved document context. Include exact dates and
consequences for deadlines. Do not give legal advice."""


def build_chat_prompt(estate_json: str, retrieved_chunks: list[str]) -> str:
    chunks = "\n\n".join(retrieved_chunks) or "No retrieved document context yet."
    return f"{BASE_CHAT_SYSTEM_PROMPT}\n\nESTATE STATE:\n{estate_json}\n\nRETRIEVED DOCUMENT CONTEXT:\n{chunks}"

