from __future__ import annotations

import asyncio
import json
import os
import queue as thread_queue
from collections.abc import AsyncIterator
from pathlib import Path
from threading import Thread

import httpx

from app.config import settings


def _apply_hf_token() -> None:
    token = (settings.hf_token or "").strip()
    if token:
        os.environ["HF_TOKEN"] = token
        os.environ["HUGGING_FACE_HUB_TOKEN"] = token


class ModelClient:
    def __init__(self) -> None:
        self._hf_tokenizer = None
        self._hf_model = None
        self._hf_loading = False
        self._unsloth_tokenizer = None
        self._unsloth_model = None
        self._unsloth_source: str | None = None

    @property
    def hf_model_loaded(self) -> bool:
        return self._hf_model is not None

    @property
    def unsloth_model_loaded(self) -> bool:
        return self._unsloth_model is not None

    def _load_hf_model(self):
        if self._hf_model is not None:
            return self._hf_tokenizer, self._hf_model

        _apply_hf_token()
        from transformers import AutoModelForCausalLM, AutoTokenizer
        import torch

        token = (settings.hf_token or "").strip() or None
        tokenizer = AutoTokenizer.from_pretrained(
            settings.hf_model, trust_remote_code=True, token=token
        )
        if tokenizer.pad_token is None:
            tokenizer.pad_token = tokenizer.eos_token

        load_kwargs: dict = {"trust_remote_code": True, "attn_implementation": "eager"}
        if token:
            load_kwargs["token"] = token
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

    def _unsloth_resolve_path(self) -> str:
        adapter = Path(settings.unsloth_adapter_dir)
        if adapter.exists() and any(adapter.iterdir()):
            return str(adapter)
        return settings.unsloth_model

    def _load_unsloth_model(self):
        source = self._unsloth_resolve_path()
        if self._unsloth_model is not None and self._unsloth_source == source:
            return self._unsloth_tokenizer, self._unsloth_model

        _apply_hf_token()
        try:
            from unsloth import FastLanguageModel
        except ImportError as exc:
            raise RuntimeError(
                "Unsloth is not installed. Run: pip install unsloth\n"
                "Docs: https://unsloth.ai/docs/get-started/install/pip-install"
            ) from exc

        model, tokenizer = FastLanguageModel.from_pretrained(
            model_name=source,
            max_seq_length=settings.unsloth_max_seq_length,
            dtype=None,
            load_in_4bit=settings.unsloth_load_in_4bit,
            token=(settings.hf_token or "").strip() or None,
        )
        FastLanguageModel.for_inference(model)
        self._unsloth_model = model
        self._unsloth_tokenizer = tokenizer
        self._unsloth_source = source
        return tokenizer, model

    async def stream_chat(self, messages: list[dict[str, str]], *, route: dict | None = None) -> AsyncIterator[str]:
        backend = settings.model_backend
        override_model = ""
        if route and settings.router_enabled:
            rec = route.get("recommended_backend") or backend
            if rec in {
                "openai",
                "openrouter",
                "groq",
                "together",
                "fireworks",
                "openai_compat",
                "ollama",
                "hermes",
                "huggingface",
                "unsloth",
            }:
                backend = rec
            override_model = (route.get("recommended_model") or "").strip()

        if backend == "ollama":
            model = override_model or settings.ollama_model
            async for chunk in self._stream_ollama(messages, model=model):
                yield chunk
        elif backend in {"openai_compat", "openai", "openrouter", "groq", "together", "fireworks"}:
            async for chunk in self._stream_openai_compat(messages, backend=backend, model=override_model or None):
                yield chunk
        elif backend == "hermes":
            async for chunk in self._stream_hermes(messages):
                yield chunk
        elif backend == "unsloth":
            async for chunk in self._stream_unsloth(messages):
                yield chunk
        elif backend == "huggingface":
            async for chunk in self._stream_huggingface(messages):
                yield chunk
        else:
            yield f"Unknown MODEL_BACKEND: {backend}"

    async def stream_chat_hermes(
        self,
        messages: list[dict[str, str]],
        *,
        session_id: str | None = None,
    ) -> AsyncIterator[tuple[str, str | None]]:
        """Hermes stream with optional session id updates."""
        from app.hermes_client import stream_hermes_chat

        async for text, sid in stream_hermes_chat(
            messages,
            session_id=session_id,
            session_key=settings.hermes_session_key or None,
        ):
            if text and not settings.hermes_show_tool_progress and text.startswith("\n\n_Hermes tool"):
                continue
            yield text, sid

    async def _stream_ollama(
        self, messages: list[dict[str, str]], *, model: str | None = None
    ) -> AsyncIterator[str]:
        url = f"{settings.ollama_base_url.rstrip('/')}/api/chat"
        use_model = (model or settings.ollama_model).strip() or settings.ollama_model
        payload = {
            "model": use_model,
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
                            f"Make sure Ollama is running and model `{use_model}` is pulled:\n"
                            f"`ollama pull {use_model}`"
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
                f"2. Run: `ollama pull {use_model}`\n"
                "3. Start Ollama, then refresh this page."
            )
        except httpx.ReadTimeout:
            yield (
                f"**Ollama timed out** waiting for `{use_model}`.\n\n"
                "Try a smaller model (`tinyllama`) in the model dropdown, or disable RAG for faster replies."
            )

    async def _stream_openai_compat(
        self,
        messages: list[dict[str, str]],
        *,
        backend: str | None = None,
        model: str | None = None,
    ) -> AsyncIterator[str]:
        from app.model_router import CLOUD_PROVIDERS, resolve_openai_compat_endpoint

        b = backend or settings.model_backend
        base_url, api_key, default_model = resolve_openai_compat_endpoint(b)
        use_model = (model or default_model).strip() or default_model
        url = f"{base_url.rstrip('/')}/chat/completions"
        payload = {
            "model": use_model,
            "messages": messages,
            "stream": True,
            "temperature": 0.7,
        }
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        if b == "openrouter":
            headers["HTTP-Referer"] = "https://github.com/nrbns/SecuraIQ-ai"
            headers["X-Title"] = "SecuraIQ"
        label = CLOUD_PROVIDERS.get(b, {}).get("label") or "OpenAI-compatible"
        if b in CLOUD_PROVIDERS and not api_key:
            yield (
                f"**{label} API key not set.**\n\n"
                f"Add the key in Settings → AI Router / Cloud providers, then retry."
            )
            return
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                async with client.stream("POST", url, json=payload, headers=headers) as response:
                    if response.status_code != 200:
                        body = await response.aread()
                        yield (
                            f"**{label} error** ({response.status_code}): {body.decode()}\n\n"
                            f"Check URL `{base_url}` and model `{use_model}`."
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
                f"**Cannot connect to {label}.**\n\n"
                f"1. Confirm the server URL is `{base_url}`\n"
                f"2. Confirm API key and model `{use_model}` in Settings"
            )

    async def _stream_hermes(self, messages: list[dict[str, str]]) -> AsyncIterator[str]:
        """Stream from Nous Hermes Agent (legacy path without session headers)."""
        async for text, _sid in self.stream_chat_hermes(messages, session_id=None):
            if text:
                yield text

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

        inputs = tokenizer(prompt, return_tensors="pt", truncation=True, max_length=2048)
        if torch.cuda.is_available():
            inputs = {k: v.cuda() for k, v in inputs.items()}
        else:
            inputs = {k: v.to(model.device) for k, v in inputs.items()}

        streamer = TextIteratorStreamer(tokenizer, skip_prompt=True, skip_special_tokens=True)
        generation_kwargs = dict(
            **inputs,
            streamer=streamer,
            max_new_tokens=320,
            do_sample=True,
            temperature=0.6,
            top_p=0.9,
            use_cache=True,
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

    def _unsloth_stream_sync(self, messages: list[dict[str, str]], out_queue: thread_queue.Queue) -> None:
        from transformers import TextIteratorStreamer
        import torch

        tokenizer, model = self._load_unsloth_model()
        prompt = self._hf_build_prompt(tokenizer, messages)
        inputs = tokenizer(prompt, return_tensors="pt", truncation=True, max_length=settings.unsloth_max_seq_length)
        inputs = {k: v.to(model.device) for k, v in inputs.items()}

        streamer = TextIteratorStreamer(tokenizer, skip_prompt=True, skip_special_tokens=True)
        generation_kwargs = dict(
            **inputs,
            streamer=streamer,
            max_new_tokens=512,
            do_sample=True,
            temperature=0.7,
            use_cache=True,
        )

        def generate() -> None:
            with torch.inference_mode():
                model.generate(**generation_kwargs)

        thread = Thread(target=generate)
        thread.start()
        try:
            for text in streamer:
                out_queue.put(text)
        finally:
            thread.join()
            out_queue.put(None)

    async def _stream_unsloth(self, messages: list[dict[str, str]]) -> AsyncIterator[str]:
        try:
            import unsloth  # noqa: F401
        except ImportError:
            yield (
                "**Unsloth backend requires extra packages.**\n\n"
                "Run: `pip install unsloth`\n"
                "Then: `pip install datasets trl peft accelerate bitsandbytes`\n\n"
                "Docs: https://unsloth.ai/docs/get-started/install/pip-install\n"
                "Or use: `.\\scripts\\use_unsloth.ps1` / `bash scripts/use_unsloth.sh`"
            )
            return

        source = self._unsloth_resolve_path()
        if self._unsloth_model is None:
            yield f"**Loading Unsloth model** `{source}` — first request may take a few minutes…\n\n"

        try:
            out_queue: thread_queue.Queue[str | None] = thread_queue.Queue()
            loop = asyncio.get_running_loop()
            worker = loop.run_in_executor(None, self._unsloth_stream_sync, messages, out_queue)
            while True:
                chunk = await loop.run_in_executor(None, out_queue.get)
                if chunk is None:
                    break
                yield chunk
            await worker
        except Exception as exc:
            yield (
                f"**Unsloth error:** {exc}\n\n"
                "1. Install Unsloth (`pip install unsloth`)\n"
                "2. Set `HF_TOKEN` in Settings if the model is gated\n"
                f"3. Check `UNSLOTH_MODEL` / adapter at `{settings.unsloth_adapter_dir}`\n"
                "4. GPU + CUDA strongly recommended (CPU is slow / may fail)"
            )

    async def preload_huggingface(self) -> None:
        if settings.model_backend == "huggingface":
            await asyncio.to_thread(self._load_hf_model)

    async def preload_unsloth(self) -> None:
        if settings.model_backend == "unsloth":
            await asyncio.to_thread(self._load_unsloth_model)


model_client = ModelClient()
