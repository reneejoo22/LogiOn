import pytest


@pytest.fixture(autouse=True)
def no_models(monkeypatch):
    # 테스트마다 실제 모델(수 GB)을 올리지 않게 한다. 음성 비서 테스트는 가짜 모델을 직접 끼운다
    monkeypatch.setenv("LOGION_ASSISTANT", "0")
