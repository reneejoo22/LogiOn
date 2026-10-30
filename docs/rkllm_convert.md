# RKLLM 변환 절차 (단일 모델 v3-single)

의도분류 없이 function calling 모델(`out/fc_merged`, Qwen2.5-1.5B + LoRA 병합본) 하나만 보드에 올립니다. 변환할 모델은 이것 하나입니다.

**상태: 이 PC 에서는 변환을 실행하지 못했습니다.** 준비(설정·캘리브레이션 질의·모델 폴더 구성·배포물 SHA256 확인)까지 끝냈고, 변환 4단계(`check → calib → convert → build-demo`)는 **미실행**입니다. 이유는 아래 "이 PC 에서 못 돌린 이유"에 적었습니다.

## 준비된 것

| 항목 | 값 | 확인 |
| --- | --- | --- |
| 도커 이미지 `rkllm-class-1.3.0.tar.gz` | SHA256 `14023956…f37c22` | `SHA256SUMS` 와 **일치** (실제 계산) |
| `rkllm-team-template.zip` | SHA256 `c1c77c94…e1fd` | 일치 |
| `rkllm-board-package.tar.gz` | SHA256 `daff239c…9014` | 일치 |
| 작업 폴더 | `E:\logion-rkllm\rkllm-team\` (저장소 밖) | 템플릿 압축 해제 후 채움 |
| 작업 폴더 압축본 | `E:\logion-rkllm\logion-rkllm-team.zip` (2.41GB, SHA256 `96b02d6b1111fa80a1e5721e1fe697cb52878ae59d988a7ad90adcb11cbb88c7`) | 서버로 옮길 파일. 모델 포함이라 저장소에는 없음 |
| `model/` | `out/fc_merged` 복사 (fp16, 3.09GB) | `config.json` 의 `eos_token_id` = 151645, `generation_config.json` 의 `eos_token_id` = 151645 (사본에서만 수정) |
| `data/config.yaml` | 저장소 `rkllm/config.yaml` 과 동일 | `system_prompt` 가 `config/pipeline_v3_single.json` 의 문장과 **글자 단위로 같음**을 yaml 로 읽어 비교해 확인 |
| `data/queries.json` | 450건, 저장소 `rkllm/queries.json` 과 동일 | 아래 "알아둘 것" 참고 |

`config.yaml` 에서 정한 값:

| 키 | 값 | 근거 |
| --- | --- | --- |
| team / domain | `logion` / `delivery` | 지시 |
| prompt_template | `chat_template` | Qwen2.5 표준 템플릿으로 학습·평가함 |
| quantized_dtype / optimization_level | `w8a8` / `1` | 지시 (RK3588 은 4bit 미지원, 정확도 우선) |
| calib_stop_at | `"<\|im_end\|>"` | 종료 토큰 뒤 잡문 절단 |
| calib_max_new_tokens | 64 | 정답 JSON 최대 **36토큰**(train/val/test 전체 2,754건 실측) → 64 면 충분 |
| max_context | **256** | 시스템 프롬프트+발화+출력 최대 **179토큰**(전체 2,754건 실측) → 32 배수 192 → 여유 256 |
| target_platform / num_npu_core | `RK3588` / 3 | 전 팀 고정 |
| dtype | `float32` (템플릿 기본) | 서버 VRAM 이 모자라면 `float16`. 가중치가 원래 fp16 이라 로드 정밀도만 달라짐 |

## 알아둘 것 (확인하지 못했거나 판단한 것)

1. **캘리브레이션 450건은 모두 `data/fc_dataset.csv` 의 train 문장입니다.** val·test 와는 겹치지 않음(0건)을 확인했지만, "train 과도 겹치지 않을 것" 이라는 조건은 **지키지 못했습니다.** 새 문장을 만들면 test 전용 말 틀과 겹칠 위험이 있어 기존 450건을 그대로 썼습니다. 양자화 보정용이라 정확도 평가 오염은 아니지만, 팀이 실제 발화 300~1,000건을 따로 모을 수 있으면 `queries.json` 만 바꾸면 됩니다.
2. **`generation_config.json` 사본을 greedy 로 바꿨습니다** (`do_sample=false`, `top_k=1`, `temperature`/`top_p` 제거, `repetition_penalty=1.1` 유지). 원본(`out/fc_merged`)은 `do_sample=true, temperature=0.7` 이라 캘리브레이션 응답(`data_quant.json` 의 target)이 샘플링으로 나올 수 있어서, 학습·평가 때 쓴 설정(탐욕, 1.1)과 맞췄습니다. `./run.sh calib` 이 이 값을 실제로 쓰는지는 확인하지 못했습니다.
3. 도커 이미지의 `calib` 이 만드는 `data_quant.json` 의 target 이 **한 줄 JSON 이고 뒤에 잡문이 없는지**는 실행하지 못해 미확인입니다. 서버에서 앞 10건·무작위 10건을 눈으로 확인하세요.
4. PDF 안내문(`한성대학교_특강2_배포물_안내.pdf`)은 이 PC 에 PDF 변환 도구가 없어 읽지 못했습니다. 템플릿 README 기준으로 진행했습니다.

## 이 PC 에서 못 돌린 이유 (읽기 전용으로 확인만 함)

| 확인 | 결과 |
| --- | --- |
| CPU 하드웨어 가상화 (`VirtualizationFirmwareEnabled`) | **False** (BIOS 에서 꺼져 있음) |
| 하이퍼바이저 (`HypervisorPresent`) | False |
| `docker` 명령 | **없음** (미설치) |
| WSL | `wsl.exe` 는 있으나 배포판·기능 미설치 (`wsl --status` 가 설치 안내만 출력) |
| GPU | RTX 5050 8GB (Windows). 변환 이미지는 x86_64 리눅스 + NVIDIA 컨테이너 런타임 기준 |

BIOS 설정 변경과 대용량 설치(WSL, Docker Desktop)는 하지 않았습니다. 가상화를 켜도 이 PC 에서는 WSL2 + Docker + GPU 패스스루를 따로 구성해야 하므로, **수업 서버(x86_64 리눅스, A100 권장)에서 돌리는 쪽을 권합니다.** ARM 서버에서는 변환할 수 없습니다.

## 서버에서 할 일 (명령 순서)

```bash
# 0) 서버에 올리기 (로컬 PC → 서버)
scp /e/logion-rkllm/logion-rkllm-team.zip <서버>:~/
scp "<배포물 폴더>/rkllm-class-1.3.0.tar.gz" <서버>:~/       # 서버에서 직접 받아도 됨

# 1) 서버에서
sha256sum -c <(echo "14023956b28cb62cc27833271f18b035afdaae4d4e0721d0a7f0f9bc08f37c22  rkllm-class-1.3.0.tar.gz")
sha256sum logion-rkllm-team.zip     # 96b02d6b1111fa80a1e5721e1fe697cb52878ae59d988a7ad90adcb11cbb88c7 이어야 함
docker load < rkllm-class-1.3.0.tar.gz      # Loaded image: rkllm-class:1.3.0
unzip logion-rkllm-team.zip && cd rkllm-team

# 2) 변환 4단계
./run.sh check          # CHECK PASSED 가 나와야 다음 단계
./run.sh calib          # data/data_quant.json — 앞 10건·무작위 10건 눈으로 확인 (target 이 한 줄 JSON, 뒤 잡문 없음)
./run.sh convert        # output/logion-delivery_w8a8_opt1_cal450.rkllm (+ .rkllm.json)
./run.sh build-demo     # output/demo_Linux_aarch64/

# 3) 보드로
scp output/*.rkllm output/*.rkllm.json -r output/demo_Linux_aarch64 orangepi@<보드IP>:~/rkllm/
```

- GPU 를 쓰려면 호스트에 nvidia-container-toolkit 이 필요합니다. 없으면 CPU 로 돌고 약 10배 느립니다.
- 산출물 크기가 원본(3.09GB)의 1/3~1/4(약 0.8~1.0GB)이면 정상입니다.
- 실패하면 `output/*.log` 마지막 줄부터 보고, dtype → max_context → 모델 경로 순으로 확인합니다. 질문할 때는 실패한 명령·로그·`config.yaml` 을 함께 보냅니다.
- 저장소의 `rkllm/` 에는 `config.yaml`, `queries.json`, 템플릿 README, `run.sh` 만 있습니다 (모델·`.rkllm`·도커 이미지는 커밋하지 않음).

## 보드 쪽

- 보드 서버의 생성 설정은 학습·평가와 맞춰 **top_k=1(탐욕), repeat_penalty=1.1**, 종료 토큰 151645(`<|im_end|>`), 최대 생성 64토큰으로 둡니다.
- `.rkllm.json` 은 모델과 항상 같이 복사합니다 (보드 서버가 system 지시를 넣을 때 쓰는 조각).
- 변환 후에는 `scripts/board_eval.py --base-url http://<보드IP>:<포트>/v1` 로 test 431건 정확도를 PC 원본(fn 0.8863 / 최종 0.8469)과 비교하세요. 값 없는 명령(scan/other/next_stop)도 이제 LLM 을 거치므로 `scripts/board_latency.py` 로 보드 지연을 꼭 재야 합니다 (PC 에서는 평균 292ms, 생성 토큰 평균 5.4개).
