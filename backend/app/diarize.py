import argparse
import json
import os
import subprocess
import tempfile
from pathlib import Path

import torch

AUDIO_MIN_SEC = 4
AUDIO_MAX_SEC = 4 * 60 * 60  # 4 hours


def get_duration(path: str) -> float:
    """Return duration of media file in seconds using ffprobe."""
    out = subprocess.check_output(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            path,
        ]
    )
    return float(out)


def convert_to_wav(src: str) -> str:
    """Convert input media to mono 16 kHz WAV."""
    if src.lower().endswith('.wav'):
        return src
    tmp = tempfile.NamedTemporaryFile(suffix='.wav', delete=False)
    tmp.close()
    subprocess.run(
        [
            'ffmpeg',
            '-y',
            '-i',
            src,
            '-ac',
            '1',
            '-ar',
            '16000',
            tmp.name,
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=True,
    )
    return tmp.name


def diarize_file(
    input_path: str,
    out_dir: str,
    num_speakers: int | None,
    max_speakers: int | None,
    device: str,
) -> Path:
    os.makedirs(out_dir, exist_ok=True)
    duration = get_duration(input_path)
    if not (AUDIO_MIN_SEC <= duration <= AUDIO_MAX_SEC):
        raise ValueError(
            f"Duration {duration:.2f}s out of supported range {AUDIO_MIN_SEC}s-{AUDIO_MAX_SEC}s"
        )
    wav_path = convert_to_wav(input_path)
    if device == "auto":
        device = "cuda" if torch.cuda.is_available() else "cpu"
    try:
        from nemo.collections.asr.models.msdd_models import NeuralDiarizer

        model = NeuralDiarizer.from_pretrained(
            model_name="diar_msdd_telephonic",
            map_location=device,
            verbose=False,
        )
    except Exception as e:
        raise RuntimeError(
            "Failed to load NeMo diarization model. Ensure internet access or"
            " pre-downloaded models in NEMO_CACHE_DIR."
        ) from e
    annotation = model(
        wav_path,
        out_dir=out_dir,
        num_speakers=num_speakers,
        max_speakers=max_speakers,
    )

    segments = [
        {'start': segment.start, 'end': segment.end, 'speaker': speaker}
        for segment, _, speaker in annotation.itertracks(yield_label=True)
    ]

    result_path = Path(out_dir) / f"{Path(input_path).stem}.json"
    with open(result_path, 'w', encoding='utf-8') as f:
        json.dump(segments, f, ensure_ascii=False, indent=2)
    return result_path


def main() -> None:
    parser = argparse.ArgumentParser(description='Run speaker diarization with NeMo')
    parser.add_argument('input', help='Path to mp3/mp4/wav file')
    parser.add_argument('--out-dir', default='diarization_results', help='Directory for results')
    parser.add_argument('--num-speakers', type=int, default=None, help='Exact number of speakers')
    parser.add_argument('--max-speakers', type=int, default=None, help='Maximum number of speakers')
    parser.add_argument(
        '--device',
        choices=['cpu', 'cuda', 'auto'],
        default='cpu',
        help="Device to run the model on (default: cpu)",
    )
    args = parser.parse_args()

    result = diarize_file(
        args.input,
        args.out_dir,
        args.num_speakers,
        args.max_speakers,
        args.device,
    )
    print('Saved diarization result to', result)


if __name__ == '__main__':
    main()
