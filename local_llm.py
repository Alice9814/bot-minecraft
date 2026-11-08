"""Embedded local inference for the Minecraft bot (no Ollama service required)."""
import concurrent.futures
import os
import shutil
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

MODEL_REPO = "second-state/gemma-3-270m-it-GGUF"
MODEL_FILE = "gemma-3-270m-it-Q4_K_M.gguf"
MODEL_URL = f"https://huggingface.co/{MODEL_REPO}/resolve/main/{MODEL_FILE}"
CHUNK_SIZE = 8 * 1024 * 1024
DOWNLOAD_WORKERS = 4


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

        parts_dir = self.model_dir / (MODEL_FILE + ".parts")
        parts_dir.mkdir(parents=True, exist_ok=True)
        headers = {"User-Agent": "MinecraftAIBot/1.1"}

        # Descobre o tamanho real e verifica se o servidor aceita downloads por partes.
        try:
            head = urllib.request.Request(MODEL_URL, headers=headers, method="HEAD")
            with urllib.request.urlopen(head, timeout=30) as response:
                total = int(response.headers.get("Content-Length", "0") or 0)
                range_supported = response.headers.get("Accept-Ranges", "").lower() == "bytes"
        except Exception as exc:
            raise RuntimeError(f"Não foi possível consultar o arquivo do Gemma: {exc}") from exc

        if total <= 100_000_000:
            raise RuntimeError("O servidor não informou o tamanho válido do modelo Gemma.")

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
                            f"[IA] Gemma: {percent}% | {speed:.2f} MB/s | "
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

            # Se uma tentativa anterior foi interrompida, continua a parte incompleta.
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
                with urllib.request.urlopen(request, timeout=90) as response:
                    if response.status != 206:
                        raise RuntimeError("O servidor não aceitou o download em partes.")
                    content_range = response.headers.get("Content-Range", "")
                    if not content_range.startswith(f"bytes {request_start}-"):
                        raise RuntimeError("O servidor retornou um intervalo inesperado.")
                    mode = "ab" if existing else "wb"
                    with part_path.open(mode) as output:
                        while True:
                            data = response.read(1024 * 1024)
                            if not data:
                                break
                            output.write(data)
                            report_progress(len(data))
                if part_path.stat().st_size != expected:
                    raise RuntimeError(f"Parte {index + 1} do Gemma ficou incompleta.")
            except Exception:
                # Mantém a parte no disco para que a próxima inicialização possa retomá-la.
                raise

        # O suporte a Range é confirmado pela resposta 206 de cada parte.
        if range_supported:
            try:
                with concurrent.futures.ThreadPoolExecutor(max_workers=DOWNLOAD_WORKERS) as pool:
                    futures = [pool.submit(download_part, i) for i in range(count)]
                    for future in concurrent.futures.as_completed(futures):
                        future.result()
            except Exception as exc:
                # Se o host não aceitar Range, preserva as partes e informa o motivo.
                raise RuntimeError(
                    f"Download paralelo do Gemma falhou: {exc}. "
                    "Os dados já baixados foram preservados; tente novamente."
                ) from exc
        else:
            raise RuntimeError(
                "O servidor de download não anunciou suporte a downloads por partes. "
                "Tente novamente mais tarde."
            )

        temporary = self.model_path.with_suffix(self.model_path.suffix + ".assembling")
        try:
            with temporary.open("wb") as output:
                for index in range(count):
                    part_path = parts_dir / f"part-{index:05d}.bin"
                    with part_path.open("rb") as part:
                        shutil.copyfileobj(part, output, length=1024 * 1024)
            if temporary.stat().st_size != total:
                raise RuntimeError("O arquivo final do Gemma ficou incompleto.")
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
            response_format={"type": "json_object"},
        )
        return result["choices"][0]["message"]["content"] or ""
