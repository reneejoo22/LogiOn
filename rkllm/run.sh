#!/usr/bin/env bash
# rkllm-class 래퍼 — 사용: ./run.sh check | calib | convert | build-demo | shell | help
#
#   model/  → /work/model  (읽기 전용)   학습된 HF 모델 디렉터리 (config.json 이 바로 아래)
#   data/   → /work/data                 config.yaml, queries.json, data_quant.json
#   output/ → /work/output               *.rkllm, *.log, demo_Linux_aarch64/
#
# 환경변수:  RKLLM_IMAGE=<이미지>   RKLLM_GPU=auto|1|0
set -e
cd "$(dirname "$0")"
IMG="${RKLLM_IMAGE:-rkllm-class:1.3.0}"
mkdir -p model data output

GPU=""
case "${RKLLM_GPU:-auto}" in
  1) GPU="--gpus all" ;;
  0) ;;
  *) if docker info 2>/dev/null | grep -qi "nvidia"; then GPU="--gpus all"; fi ;;
esac
[ -z "$GPU" ] && echo "[run.sh] GPU 런타임 없음 → CPU 로 실행합니다 (nvidia-container-toolkit 설치 후 RKLLM_GPU=1)"

TTY=""; [ -t 0 ] && TTY="-it"

exec docker run --rm $TTY $GPU \
  --user "$(id -u):$(id -g)" \
  -v "$PWD/model:/work/model:ro" \
  -v "$PWD/data:/work/data" \
  -v "$PWD/output:/work/output" \
  "$IMG" "$@"
