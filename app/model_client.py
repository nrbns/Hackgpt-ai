from __future__ import annotations

import asyncio
import json
import queue as thread_queue
from collections.abc import AsyncIterator
from threading import Thread

import httpx

from app.config import settings


class ModelClient:
    def __init__(self) -> None:
        self._hf_tokenizer = None
        self._hf_model = None
        self._hf_loading = False

    @property
    def hf_model_loaded(self) -> bool:
        return self._hf_model is not None

    def _load_hf_model(self):
        if self._hf_model is not None:
            return self._hf_tokenizer, self._hf_model

        from transformers import AutoModelForCausalLM, AutoTokenizer
        import torch

        tokenizer = AutoTokenizer.from_pretrained(settings.hf_model, trust_remote_code=True)
        if tokenizer.pad_token is None:
            tokenizer.pad_token = tokenizer.eos_token

        load_kwargs: dict = {"trust_remote_code": True, "attn_implementation": "eager"}
        if torch.cuda.is_available():
            load_kwargs["torch_dtype"] = torch.float16
            load_kwargs["device_map"] = "auto"
        else:
            load_kwargs["torch_dtype"] = torch.float32
            load_kwargs["low_cpu_mem_usage"] = True

        model = AutoModelForCausalLM.from_pretrained(settings.hf_model, **load_kwargs)
        self._hf_tokenizer = tokenizer
        self._hf_model = model
        return tokenizer, model

    async def stream_chat(self, messages: list[dict[str, str]]) -> AsyncIterator[str]:
        if settings.model_backend == "ollama":
            async for chunk in self._stream_ollama(messages):
                yield chunk
        elif settings.model_backend == "openai_compat":
            async for chunk in self._stream_openai_compat(messages):
                yield chunk
        elif settings.model_backend == "huggingface":
            async for chunk in self._stream_huggingface(messages):
                yield chunk
        else:
            yield f"Unknown MODEL_BACKEND: {settings.model_backend}"

    async def _stream_ollama(self, messages: list[dict[str, str]]) -> AsyncIterator[str]:
        url = f"{settings.ollama_base_url.rstrip('/')}/api/chat"
        payload = {
            "model": settings.ollama_model,
            "messages": messages,
            "stream": True,
        }
        try:
            timeout = httpx.Timeout(connect=10.0, read=600.0, write=30.0, pool=10.0)
            async with httpx.AsyncClient(timeout=timeout) as client:
                async with client.stream("POST", url, json=payload) as response:
                    if response.status_code != 200:
                        body = await response.aread()
                        yield (
                            f"**Ollama error** ({response.status_code}): {body.decode()}\n\n"
                            f"Make sure Ollama is running and model `{settings.ollama_model}` is pulled:\n"
                            f"`ollama pull {settings.ollama_model}`"
                        )
                        return
                    async for line in response.aiter_lines():
                        if not line.strip():
                            continue
                        data = json.loads(line)
                        if data.get("done"):
                            break
                        message = data.get("message", {})
                        content = message.get("content", "")
                        if content:
                            yield content
        except httpx.ConnectError:
            yield (
                "**Cannot connect to Ollama.**\n\n"
                "1. Install Ollama: https://ollama.com\n"
                f"2. Run: `ollama pull {settings.ollama_model}`\n"
                "3. Start Ollama, then refresh this page."
            )
        except httpx.ReadTimeout:
            yield (
                f"**Ollama timed out** waiting for `{settings.ollama_model}`.\n\n"
                "Try a smaller model (`tinyllama`) in the model dropdown, or disable RAG for faster replies."
            )

    async def _stream_openai_compat(self, messages: list[dict[str, str]]) -> AsyncIterator[str]:
        url = f"{settings.openai_compat_base_url.rstrip('/')}/chat/completions"
        payload = {
            "model": settings.openai_compat_model,
            "messages": messages,
            "stream": True,
            "temperature": 0.7,
        }
        headers = {
            "Authorization": f"Bearer {settings.openai_compat_api_key}",
            "Content-Type": "application/json",
        }
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                async with client.stream("POST", url, json=payload, headers=headers) as response:
                    if response.status_code != 200:
                        body = await response.aread()
                        yield (
                            f"**OpenAI-compatible backend error** ({response.status_code}): {body.decode()}\n\n"
                            "If you are using LM Studio, make sure the local server is running on "
                            f"`{settings.openai_compat_base_url}` and the loaded model name matches "
                            f"`{settings.openai_compat_model}`."
                        )
                        return

                    async for line in response.aiter_lines():
                        if not line.strip() or not line.startswith("data: "):
                            continue
                        data_str = line[6:]
                        if data_str == "[DONE]":
                            break
                        data = json.loads(data_str)
                        choices = data.get("choices", [])
                        if not choices:
                            continue
                        delta = choices[0].get("delta", {})
                        content = delta.get("content", "")
                        if content:
                            yield content
        except httpx.ConnectError:
            yield (
                "**Cannot connect to the OpenAI-compatible local server.**\n\n"
                "1. Start LM Studio or another OpenAI-compatible local endpoint\n"
                f"2. Confirm the server URL is `{settings.openai_compat_base_url}`\n"
                f"3. Set `OPENAI_COMPAT_MODEL` to the loaded local model name in `.env`"
            )

    def _hf_build_prompt(self, tokenizer, messages: list[dict[str, str]]) -> str:
        if hasattr(tokenizer, "apply_chat_template"):
            try:
                return tokenizer.apply_chat_template(
                    messages,
                    tokenize=False,
                    add_generation_prompt=True,
                )
            except Exception:
                pass

        parts = []
        for m in messages:
            role = m["role"]
            content = m["content"]
            if role == "system":
                parts.append(f"<|system|>\n{content}<|end|>")
            elif role == "user":
                parts.append(f"<|user|>\n{content}<|end|>")
            else:
                parts.append(f"<|assistant|>\n{content}<|end|>")
        parts.append("<|assistant|>\n")
        return "\n".join(parts)

    def _hf_stream_sync(self, messages: list[dict[str, str]], out_queue: thread_queue.Queue) -> None:
        from transformers import TextIteratorStreamer
        import torch

        tokenizer, model = self._load_hf_model()
        prompt = self._hf_build_prompt(tokenizer, messages)

        inputs = tokenizer(prompt, return_tensors="pt", truncation=True, max_length=3072)
        if torch.cuda.is_available():
            inputs = {k: v.cuda() for k, v in inputs.items()}
        else:
            inputs = {k: v.to(model.device) for k, v in inputs.items()}

        streamer = TextIteratorStreamer(tokenizer, skip_prompt=True, skip_special_tokens=True)
        generation_kwargs = dict(
            **inputs,
            streamer=streamer,
            max_new_tokens=512,
            do_sample=True,
            temperature=0.7,
        )

        def generate() -> None:
            model.generate(**generation_kwargs)

        thread = Thread(target=generate)
        thread.start()
        try:
            for text in streamer:
                out_queue.put(text)
        finally:
            thread.join()
            out_queue.put(None)

    async def _stream_huggingface(self, messages: list[dict[str, str]]) -> AsyncIterator[str]:
        try:
            import transformers  # noqa: F401
            import torch  # noqa: F401
        except ImportError:
            yield (
                "**HuggingFace backend requires extra packages.**\n\n"
                "Run: `pip install torch transformers accelerate`"
            )
            return

        if self._hf_model is None:
            yield f"**Loading model** `{settings.hf_model}` — first request may take a few minutes…\n\n"

        try:
            out_queue: thread_queue.Queue[str | None] = thread_queue.Queue()
            loop = asyncio.get_running_loop()
            worker = loop.run_in_executor(None, self._hf_stream_sync, messages, out_queue)
            while True:
                chunk = await loop.run_in_executor(None, out_queue.get)
                if chunk is None:
                    break
                yield chunk
            await worker
        except Exception as exc:
            yield f"**Model error:** {exc}\n\nCheck `HF_MODEL` in `.env` and your internet connection for first download."

    async def preload_huggingface(self) -> None:
        if settings.model_backend == "huggingface":
            await asyncio.to_thread(self._load_hf_model)


model_client = ModelClient()
