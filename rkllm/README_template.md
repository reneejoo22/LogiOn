# rkllm 팀 템플릿 — 서버에서 양자화 · 변환 (발표자료 Part 2, 23~29쪽)

이 폴더를 팀 이름으로 복사해서 씁니다. 보드 쪽은 보드 패키지의 GUIDE.md 를 봅니다.

## 0. 준비 (1회)
```bash
curl -L -o rkllm-class-1.3.0.tar.gz "<S3 링크>"
docker load < rkllm-class-1.3.0.tar.gz         # Loaded image: rkllm-class:1.3.0
```
서버는 x86_64 리눅스 + NVIDIA GPU(A100 권장). ARM 인스턴스는 변환할 수 없습니다.
GPU 를 쓰려면 호스트에 nvidia-container-toolkit 이 있어야 합니다. 없으면 CPU 로 폴백됩니다(약 10배 느림).

## 1. 폴더 구조
```
model/    학습된 HF 모델 디렉터리 — config.json 이 바로 아래. LoRA·QLoRA 는 반드시 병합본
data/     config.yaml (팀별 설정) · queries.json (실제 발화 300~1,000건)
output/   *.rkllm · *.rkllm.json · *.log · demo_Linux_aarch64/  ← 여기서 보드로 복사
```

## 2. 실행 순서
```bash
cp -r /path/to/hf-model/* model/
vi data/config.yaml             # team · domain · prompt_template · system_prompt
vi data/queries.json            # 팀 발화
./run.sh check                  # CHECK PASSED 가 나와야 다음 단계
./run.sh calib                  # data/data_quant.json — 앞 10건·무작위 10건 눈으로 검수
./run.sh convert                # output/<team>-<domain>_w8a8_opt1_cal<N>.rkllm (+ .rkllm.json)
./run.sh build-demo             # output/demo_Linux_aarch64/
scp output/*.rkllm output/*.rkllm.json -r output/demo_Linux_aarch64 orangepi@<보드IP>:~/rkllm/
```
`.rkllm.json` 은 보드 서버가 system 지시를 넣을 때 쓰는 템플릿 조각입니다. 모델과 항상 같이 복사합니다.

## 3. 확인할 것
- 산출물 크기가 원본 HF 모델의 1/3~1/4 이면 정상
- 실패하면 `output/*.log` 마지막 줄부터 — dtype · max_context · 모델 경로 순서로 확인
- 질문할 때는 실패한 명령 · 로그 파일 · config.yaml 세 가지를 함께 보냅니다
