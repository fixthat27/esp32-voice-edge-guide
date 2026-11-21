from augmentation import generate_augmented
from pathlib import Path

raw_dir = Path("ml/data/raw/s01_day1")

for wav_path in sorted(raw_dir.glob("*.wav")):
    output_dir = Path("ml/data/augmented/s01_day1") / wav_path.stem

    generate_augmented(
        input_path=str(wav_path),
        output_dir=str(output_dir),
        noise_path=None,
        count=20
    )
