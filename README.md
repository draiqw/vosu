# VOSU

This repository contains a simple FastAPI backend and a React frontend.

## Diarization helper

Inside `backend/app/diarize.py` there is a small utility for running speaker diarization using [NVIDIA NeMo](https://github.com/NVIDIA/NeMo).

### Requirements

- Poetry
- FFmpeg
- Python 3.10+

Install dependencies in the backend folder. FFmpeg must also be installed in your system:

```bash
cd backend
poetry install
```

### Usage

Run diarization on an audio or video file (4s–4h) and save segments to `diarization_results`.
By default the model runs on CPU:

```bash
poetry run python app/diarize.py /path/to/file.mp3

```

To use a specific device (e.g. GPU if available) pass `--device cuda` or `--device auto`.

```bash
poetry run python app/diarize.py /path/to/file.mp3 --device auto
```

The script will output a JSON file with speaker labels and timestamps.

The first run will download NeMo models (~1GB) from NVIDIA's servers.
If you need to work offline, pre-download the models and set
`NEMO_CACHE_DIR` to the directory containing them.
