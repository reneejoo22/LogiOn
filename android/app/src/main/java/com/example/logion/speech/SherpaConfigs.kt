package com.example.logion.speech

import com.k2fsa.sherpa.onnx.FeatureConfig
import com.k2fsa.sherpa.onnx.OfflineModelConfig
import com.k2fsa.sherpa.onnx.OfflineRecognizerConfig
import com.k2fsa.sherpa.onnx.OfflineSenseVoiceModelConfig
import com.k2fsa.sherpa.onnx.OfflineTtsConfig
import com.k2fsa.sherpa.onnx.OfflineTtsModelConfig
import com.k2fsa.sherpa.onnx.OfflineTtsVitsModelConfig
import com.k2fsa.sherpa.onnx.SileroVadModelConfig
import com.k2fsa.sherpa.onnx.VadModelConfig

// ==============================
// sherpa-onnx 모델 설정 (강의 자료 p.19~23 과 같은 구성)
// 모델 파일은 assets 폴더에 있음 → python speech/download_models.py 로 채움
// ==============================

const val STT_SAMPLE_RATE = 16000

const val VAD_MODEL = "silero_vad.onnx"
const val STT_MODEL_DIR = "sherpa-onnx-sense-voice-zh-en-ja-ko-yue-int8-2024-07-17"
const val TTS_MODEL_DIR = "vits-mimic3-ko_KO-kss_low"
const val TTS_MODEL_NAME = "ko_KO-kss_low.onnx"

// VAD: 말하는 구간만 잘라냄
fun getVadModelConfig(): VadModelConfig = VadModelConfig(
    sileroVadModelConfig = SileroVadModelConfig(
        model = VAD_MODEL,
        threshold = 0.5f,           // 이 확률 이상이면 음성
        minSilenceDuration = 0.8f,  // 이만큼 조용하면 말이 끝난 것으로 봄 (초)
        minSpeechDuration = 0.25f,  // 이보다 짧은 소리는 무시 (초)
        windowSize = 512,
        maxSpeechDuration = 15f,
    ),
    sampleRate = STT_SAMPLE_RATE,
    numThreads = 1,
    provider = "cpu",
)

// STT: SenseVoice-Small int8 (한국어, use_itn 으로 "두 개" → "2개")
fun getSenseVoiceConfig(): OfflineRecognizerConfig = OfflineRecognizerConfig(
    featConfig = FeatureConfig(sampleRate = STT_SAMPLE_RATE, featureDim = 80),
    modelConfig = OfflineModelConfig(
        senseVoice = OfflineSenseVoiceModelConfig(
            model = "$STT_MODEL_DIR/model.int8.onnx",
            language = "ko",
            useInverseTextNormalization = true,
        ),
        tokens = "$STT_MODEL_DIR/tokens.txt",
        numThreads = 4,
        provider = "cpu",
    ),
)

// TTS: 한국어 VITS. espeak-ng-data 는 파일 경로가 필요해서 앱 내부 저장소로 복사한 경로를 넘김
fun getTtsConfig(espeakDataDir: String): OfflineTtsConfig = OfflineTtsConfig(
    model = OfflineTtsModelConfig(
        vits = OfflineTtsVitsModelConfig(
            model = "$TTS_MODEL_DIR/$TTS_MODEL_NAME",
            tokens = "$TTS_MODEL_DIR/tokens.txt",
            dataDir = espeakDataDir,
        ),
        numThreads = 2,
        provider = "cpu",
    ),
    maxNumSentences = 1,
)
