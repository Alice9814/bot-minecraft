"""Embedded local inference for the Minecraft bot (no Ollama service required)."""
import os
import urllib.request
from pathlib import Path

MODEL_REPO = "second-state/gemma-3-270m-it-GGUF"
MODEL_FILE = "gemma-3-270m-it-Q4_K_M.gguf"
MODEL_URL = f"https://huggingface.co/{MODEL_REPO}/resolve/main/{MODEL_FILE}"


class LocalGemma:
    def __init__(self, model_dir: Path, temperature: float = 0.3):
        self.model_dir = Path(model_dir)
        self.model_path = self.model_dir / MODEL_FILE
        self.temperature = float(temperature)
        self._model = None

    def _download_model(self):
        self.model_dir.mkdir(parents=True, exist_ok=True)
        if self.model_path.exists() and self.model_path.stat().st_size > 100_000_000:
            return
        partial = self.model_path.with_suffix(self.model_path.suffix + ".part")
        request = urllib.request.Request(
            MODEL_URL, headers={"User-Agent": "MinecraftAIBot/1.0"}
        )
        try:
            with urllib.request.urlopen(request, timeout=60) as response, partial.open("wb") as output:
                total = int(response.headers.get("Content-Length", "0") or 0)
                downloaded = 0
                while True:
                    chunk = response.read(1024 * 1024)
                    if not chunk:
                        break
                    output.write(chunk)
                    downloaded += len(chunk)
                    if total:
                        print(f"[IA] Baixando modelo Gemma: {downloaded * 100 // total}%", flush=True)
            if partial.stat().st_size < 100_000_000:
                raise RuntimeError("O arquivo do modelo baixado está incompleto.")
            os.replace(partial, self.model_path)
        except Exception:
            try:
                partial.unlink()
            except OSError:
                pass
            raise

    def load(self):
        if self._model is not None:
            return
        self._download_model()
        try:
            from llama_cpp import Llama
        except ImportError as exc:
            raise RuntimeError(
                "O runtime local llama-cpp-python não está incluído nesta instalação."
            ) from exc
        self._model = Llama(
            model_path=str(self.model_path),
            n_ctx=2048,
            n_threads=max(2, min(8, os.cpu_count() or 4)),
            verbose=False,
        )

    def generate(self, messages):
        self.load()
        result = self._model.create_chat_completion(
            messages=messages,
            temperature=self.temperature,
            max_tokens=180,
        )
        return result["choices"][0]["message"]["content"] or ""
