"""STT/TTS 모델과 안드로이드용 sherpa-onnx AAR 을 받아 제자리에 둡니다.

저장소 루트(LogiOn\\)에서 한 번:
  python speech/download_models.py            # PC 용 모델 + 안드로이드 assets/libs 까지
  python speech/download_models.py --no-android

결과 위치
  speech/models/                              PC(파이썬) 용 모델
  android/app/src/main/assets/                앱에 들어갈 모델 (강의 p.20 과 같은 구조)
  android/app/libs/sherpa-onnx-<ver>.aar      안드로이드 라이브러리
모두 용량이 커서 git 에는 올리지 않습니다 (.gitignore).

버전 주의: sherpa-onnx 2.x 는 VITS 의 espeak-ng(발음 변환) 를 없앴습니다.
한국어 VITS 를 쓰려면 1.x 를 써야 해서 1.13.8 로 고정합니다 (파이썬도 같은 버전).
"""
from __future__ import annotations

import argparse
import shutil
import tarfile
import urllib.request
from pathlib import Path

SHERPA_VERSION = "1.13.8"
GH = "https://github.com/k2-fsa/sherpa-onnx/releases/download"
ROOT = Path(__file__).resolve().parent.parent
MODELS = ROOT / "speech" / "models"
ANDROID_ASSETS = ROOT / "android" / "app" / "src" / "main" / "assets"
ANDROID_LIBS = ROOT / "android" / "app" / "libs"

STT = "sherpa-onnx-sense-voice-zh-en-ja-ko-yue-int8-2024-07-17"
TTS = "vits-mimic3-ko_KO-kss_low"
VAD = "silero_vad.onnx"

# 앱에 넣을 파일만 (테스트 wav, 스크립트 등은 뺌)
ANDROID_FILES = {
    VAD: None,
    STT: ["model.int8.onnx", "tokens.txt"],
    TTS: ["ko_KO-kss_low.onnx", "tokens.txt", "espeak-ng-data"],
}


def fetch(url: str, dest: Path) -> None:
    if dest.exists() and dest.stat().st_size > 0:
        print(f"  있음  {dest.name}")
        return
    dest.parent.mkdir(parents=True, exist_ok=True)
    print(f"  받는 중 {url}")
    tmp = dest.with_suffix(dest.suffix + ".part")
    with urllib.request.urlopen(url) as r, open(tmp, "wb") as f:
        shutil.copyfileobj(r, f, length=1 << 20)
    tmp.replace(dest)


def fetch_tar(url: str, name: str) -> None:
    if (MODELS / name).is_dir():
        print(f"  있음  {name}/")
        return
    archive = MODELS / "_dl" / f"{name}.tar.bz2"
    fetch(url, archive)
    print(f"  압축 해제 {archive.name}")
    with tarfile.open(archive, "r:bz2") as t:
        t.extractall(MODELS, filter="data")


def copy_to_android() -> None:
    for name, parts in ANDROID_FILES.items():
        src = MODELS / name
        if parts is None:
            dst = ANDROID_ASSETS / name
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
            continue
        for p in parts:
            s, d = src / p, ANDROID_ASSETS / name / p
            d.parent.mkdir(parents=True, exist_ok=True)
            if s.is_dir():
                shutil.copytree(s, d, dirs_exist_ok=True)
            else:
                shutil.copy2(s, d)
    print(f"  assets 복사 완료 → {ANDROID_ASSETS}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-android", action="store_true")
    a = ap.parse_args()

    print("[1/3] 모델 (speech/models)")
    fetch(f"{GH}/asr-models/{VAD}", MODELS / VAD)
    fetch_tar(f"{GH}/asr-models/{STT}.tar.bz2", STT)
    fetch_tar(f"{GH}/tts-models/{TTS}.tar.bz2", TTS)

    if a.no_android:
        return
    print("[2/3] 안드로이드 라이브러리 (android/app/libs)")
    fetch(f"{GH}/v{SHERPA_VERSION}/sherpa-onnx-{SHERPA_VERSION}.aar",
          ANDROID_LIBS / f"sherpa-onnx-{SHERPA_VERSION}.aar")
    print("[3/3] 안드로이드 assets")
    copy_to_android()


if __name__ == "__main__":
    main()
