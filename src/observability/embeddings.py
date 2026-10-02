"""Capture actual embedding response usage before LangChain drops it.

The HTTP hooks are inside CacheBackedEmbeddings: cache hits incur no call and
record no usage. Never persist response vectors or request text.
"""

def make_tracked_embeddings(model, tracker):
    import httpx
    from langchain_openai import OpenAIEmbeddings

    def record(response):
        if not response.is_success:
            return
        payload = response.json()
        usage = payload.get('usage') or {}
        tracker.record_embedding('embedding', model, usage.get('prompt_tokens'),
                                 raw_usage={'usage': usage, 'response_model': payload.get('model')})

    def sync_hook(response):
        response.read()
        record(response)

    async def async_hook(response):
        await response.aread()
        record(response)

    if tracker is None:
        return OpenAIEmbeddings(model=model,request_timeout=60,max_retries=2)
    return OpenAIEmbeddings(
        model=model,
        request_timeout=60,max_retries=2,
        http_client=httpx.Client(event_hooks={'response': [sync_hook]}),
        http_async_client=httpx.AsyncClient(event_hooks={'response': [async_hook]}),
    )
