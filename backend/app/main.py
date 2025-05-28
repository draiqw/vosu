# main.py

import os
import uuid
import math
import subprocess
import tempfile
import logging
from concurrent.futures import ThreadPoolExecutor

import aiofiles
from fastapi import FastAPI, File, UploadFile
from fastapi.responses import JSONResponse
import whisper

# ==== Конфигурация ====
DATA_DIR = "./data"
os.makedirs(DATA_DIR, exist_ok=True)

CHUNK_SEC = 540     # 9 минут
OVERLAP_SEC = 2     # перекрытие для плавных стыков
MAX_WORKERS = 4     # потоков для транскрипции

# ==== Логирование ====
logging.basicConfig(
    format="%(asctime)s %(levelname)s %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# ==== Инициализация ====
model = whisper.load_model("small")
executor = ThreadPoolExecutor(max_workers=MAX_WORKERS)
app = FastAPI()


def get_audio_duration(path: str) -> float:
    """Возвращает длительность файла (в секундах) через ffprobe."""
    out = subprocess.check_output([
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        path
    ])
    return float(out)


def transcribe_in_chunks(file_path: str) -> str:
    """Нарезает файл на чанки, транскрибирует их и собирает полный текст."""
    duration = get_audio_duration(file_path)
    n_chunks = math.ceil(duration / CHUNK_SEC)
    transcripts = []

    logger.info(f"Транскрипция {file_path}: длительность {duration:.1f}s → {n_chunks} чанков")

    for i in range(n_chunks):
        start = max(i * CHUNK_SEC - OVERLAP_SEC, 0)
        length = min(CHUNK_SEC + OVERLAP_SEC, duration - start)

        # создаём временный WAV-файл
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            chunk_path = tmp.name

        # вырезаем аудио-фрагмент и сразу перезаписываем при необходимости
        subprocess.run([
            "ffmpeg",
            "-y",
            "-hide_banner", "-loglevel", "error",
            "-ss", str(start),
            "-t", str(length),
            "-i", file_path,
            "-ar", "16000", "-ac", "1",
            "-f", "wav",
            chunk_path
        ], check=True)

        # транскрибируем
        result = model.transcribe(chunk_path)
        text = result.get("text", "").strip()
        transcripts.append((start, text))

        os.remove(chunk_path)
        logger.info(f"  чанк {i+1}/{n_chunks}: [{start:.1f}s–{start+length:.1f}s] → {len(text)} chars")

    # сортируем и объединяем по времени
    transcripts.sort(key=lambda x: x[0])
    return "\n".join(t for _, t in transcripts)


def process_file(job_id: str, file_path: str):
    """Фоновая функция: делает транскрипцию и пишет результат."""
    try:
        text = transcribe_in_chunks(file_path)
        out_path = os.path.join(DATA_DIR, f"{job_id}_transcript.txt")
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(text)
        logger.info(f"[{job_id}] Готово: {out_path}")
    except Exception as e:
        logger.error(f"[{job_id}] Ошибка: {e}", exc_info=True)
        err_path = os.path.join(DATA_DIR, f"{job_id}_error.txt")
        with open(err_path, "w", encoding="utf-8") as f:
            f.write(str(e))
    finally:
        if os.path.exists(file_path):
            os.remove(file_path)


@app.post("/transcribe")
async def transcribe_audio(file: UploadFile = File(...)):
    """Приём файла и постановка задачи транскрипции."""
    job_id = uuid.uuid4().hex
    filename = f"{job_id}_{file.filename}"
    file_path = os.path.join(DATA_DIR, filename)

    # стримовая запись на диск
    async with aiofiles.open(file_path, "wb") as out:
        while chunk := await file.read(1 << 20):
            await out.write(chunk)

    # отправляем в пул потоков, сразу возвращаем job_id
    executor.submit(process_file, job_id, file_path)
    logger.info(f"[{job_id}] Задача в пуле: {file.filename}")

    return {"job_id": job_id, "status": "processing"}


@app.get("/transcript/{job_id}")
async def get_transcript(job_id: str):
    """Проверка статуса: возвращает текст или статус processing/error."""
    txt_path = os.path.join(DATA_DIR, f"{job_id}_transcript.txt")
    err_path = os.path.join(DATA_DIR, f"{job_id}_error.txt")

    if os.path.exists(err_path):
        async with aiofiles.open(err_path, "r", encoding="utf-8") as f:
            detail = await f.read()
        return JSONResponse(status_code=500,
                            content={"job_id": job_id, "status": "error", "detail": detail})

    if os.path.exists(txt_path):
        async with aiofiles.open(txt_path, "r", encoding="utf-8") as f:
            text = await f.read()
        return {"job_id": job_id, "status": "done", "transcript": text}

    return JSONResponse(status_code=202,
                        content={"job_id": job_id, "status": "processing"})
