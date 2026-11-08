"""Embedded local inference for the Minecraft bot (no Ollama service required)."""
import concurrent.futures
import os
import shutil
import sys
import threading
import time
import urllib.request
from pathlib import Path

# Gemma 3 1B Instruct, GGUF Q4_K_M, pinned to a known revision.
MODEL_REPO = "unsloth/gemma-3-1b-it-GGUF"
MODEL_REVISION = "27fb5789df8ed327ee677caaf1ae80ac52e3b62e"
MODEL_FILE = "gemma-3-1b-it-Q4_K_M.gguf"
MODEL_URL = (
    f"https://huggingface.co/{MODEL_REPO}/resolve/"
    f"{MODEL_REVISION}/{MODEL_FILE}"
)
MODEL_MIN_SIZE = 500_000_000
CHUNK_SIZE = 8 * 1024 * 1024
DOWNLOAD_WORKERS = 4


class LocalGemma:
    def __init__(self, model_dir: Path, temperature: float = 0.7):
        self.model_dir = Path(model_dir)
        self.model_path = self.model_dir / MODEL_FILE
        self.temperature = float(temperature)
        self._model = None

    def _download_model(self):
        self.model_dir.mkdir(parents=True, exist_ok=True)
        if self.model_path.exists() and self.model_path.stat().st_size > MODEL_MIN_SIZE:
            return

        parts_dir = self.model_dir / (MODEL_FILE + ".parts")
        parts_dir.mkdir(parents=True, exist_ok=True)
        headers = {"User-Agent": "MinecraftAIBot/1.2"}

        try:
            head = urllib.request.Request(MODEL_URL, headers=headers, method="HEAD")
            with urllib.request.urlopen(head, timeout=30) as response:
                total = int(response.headers.get("Content-Length", "0") or 0)
                range_supported = (
                    response.headers.get("Accept-Ranges", "").lower() == "bytes"
                )
        except Exception as exc:
            raise RuntimeError(
                f"Não foi possível consultar o arquivo do Gemma 3 1B: {exc}"
            ) from exc

        if total <= MODEL_MIN_SIZE:
            raise RuntimeError(
                "O servidor não informou o tamanho válido do Gemma 3 1B."
            )

        count = (total + CHUNK_SIZE - 1) // CHUNK_SIZE
        progress_lock = threading.Lock()
        downloaded_now = 0
        started = time.monotonic()
        last_report = [started]

        def report_progress(amount):
            nonlocal downloaded_now
            with progress_lock:
                downloaded_now += amount
                now = time.monotonic()
                if now - last_report[0] >= 1.0 or downloaded_now >= total:
                    elapsed = max(now - started, 0.001)
                    speed = downloaded_now / elapsed / (1024 * 1024)
                    percent = min(100, downloaded_now * 100 // total)
                    remaining = max(0, total - downloaded_now)
                    eta = int(remaining / max(downloaded_now / elapsed, 1))
                    if sys.stdout is not None:
                        print(
                            f"[IA] Gemma 3 1B: {percent}% | {speed:.2f} MB/s | "
                            f"faltam aproximadamente {eta}s",
                            flush=True,
                        )
                    last_report[0] = now

        def download_part(index):
            start = index * CHUNK_SIZE
            end = min(total, start + CHUNK_SIZE) - 1
            expected = end - start + 1
            part_path = parts_dir / f"part-{index:05d}.bin"

            if part_path.exists() and part_path.stat().st_size == expected:
                return

            existing = part_path.stat().st_size if part_path.exists() else 0
            if existing > expected:
                part_path.unlink()
                existing = 0

            request_start = start + existing
            request = urllib.request.Request(
                MODEL_URL,
                headers={**headers, "Range": f"bytes={request_start}-{end}"},
            )

            try:
                with urllib.request.urlopen(request, timeout=120) as response:
                    if response.status != 206:
                        raise RuntimeError(
                            "O servidor não aceitou o download em partes."
                        )
                    content_range = response.headers.get("Content-Range", "")
                    if not content_range.startswith(f"bytes {request_start}-"):
                        raise RuntimeError(
                            "O servidor retornou um intervalo inesperado."
                        )

                    mode = "ab" if existing else "wb"
                    with part_path.open(mode) as output:
                        while True:
                            data = response.read(1024 * 1024)
                            if not data:
                                break
                            output.write(data)
                            report_progress(len(data))

                if part_path.stat().st_size != expected:
                    raise RuntimeError(
                        f"Parte {index + 1} do Gemma 3 1B ficou incompleta."
                    )
            except Exception:
                raise

        if not range_supported:
            raise RuntimeError(
                "O servidor de download não anunciou suporte a downloads por partes. "
                "Tente novamente mais tarde."
            )

        try:
            with concurrent.futures.ThreadPoolExecutor(
                max_workers=DOWNLOAD_WORKERS
            ) as pool:
                futures = [pool.submit(download_part, i) for i in range(count)]
                for future in concurrent.futures.as_completed(futures):
                    future.result()
        except Exception as exc:
            raise RuntimeError(
                f"Download do Gemma 3 1B falhou: {exc}. "
                "Os dados já baixados foram preservados; tente novamente."
            ) from exc

        temporary = self.model_path.with_suffix(
            self.model_path.suffix + ".assembling"
        )
        try:
            with temporary.open("wb") as output:
                for index in range(count):
                    part_path = parts_dir / f"part-{index:05d}.bin"
                    with part_path.open("rb") as part:
                        shutil.copyfileobj(part, output, length=1024 * 1024)

            if temporary.stat().st_size != total:
                raise RuntimeError(
                    "O arquivo final do Gemma 3 1B ficou incompleto."
                )

            os.replace(temporary, self.model_path)
            shutil.rmtree(parts_dir, ignore_errors=True)
        finally:
            try:
                temporary.unlink()
            except OSError:
                pass

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
            n_ctx=4096,
            n_threads=max(2, min(8, os.cpu_count() or 4)),
            n_gpu_layers=0,
            verbose=False,
        )

    def generate(self, messages):
        self.load()
        result = self._model.create_chat_completion(
            messages=messages,
            temperature=self.temperature,
            top_k=64,
            top_p=0.95,
            repeat_penalty=1.05,
            max_tokens=256,
            response_format={"type": "json_object"},
        )
        return result["choices"][0]["message"]["content"] or ""
