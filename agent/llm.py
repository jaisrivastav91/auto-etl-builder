import os
from config.settings import LLM_MODEL, LLM_PROVIDER, LLM_BASE_URL, LLM_API_KEY

def get_llm(temperature: float = 0.0):
    # temperature=0 for reproducibility (part of the harness contract)
    if LLM_PROVIDER == "anthropic":
        from langchain_anthropic import ChatAnthropic
        return ChatAnthropic(model=LLM_MODEL, temperature=temperature, max_tokens=4000)
    
    # local / OpenAI-compatible (Ollama, Docker Model Runner, vLLM, LM Studio, ...)
    from langchain_openai import ChatOpenAI
    return ChatOpenAI(
        model=LLM_MODEL,
        temperature=temperature,
        max_tokens=4000,
        base_url=LLM_BASE_URL,
        api_key=LLM_API_KEY, # dummy is fine; local servers ignore it
    )