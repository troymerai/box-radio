# F1 Team Radio Voice Filter

> 디스코드 음성 통화에서 F1 팀 라디오처럼 들리게 만들어주는 실시간 마이크 필터

평범한 헤드셋 마이크 입력을 BBC F1 중계에서 들리는 그 깡통 같은 무전 사운드로 변환해 주는 Python 스크립트입니다. 띠리링 알림음 트리거, 캐리어 노이즈 자동 덕킹, 음성 활동 감지 등을 포함합니다.

```
[침묵]    치지지지지...
[말함]    "박스, 박스, 박스"   ← 깡통톤, 노이즈 차단됨
[멈춤]    치지지지지...        ← 0.45초 뒤 노이즈 복귀
```

## 주요 기능

- **F1 팀 라디오 풍 필터 체인** — Bandpass + Compressor + Distortion 조합. 실제 사인츠 2025 네덜란드 GP 라디오 클립의 스펙트럼/THD 분석을 기반으로 튜닝됨.
- **음성 감지 노이즈 덕킹** — 말할 때는 캐리어 노이즈가 즉시 차단되고, 침묵 구간에만 깔림. 홀드 타임 + 페이드 릴리스 적용.
- **글로벌 핫키 알림음 트리거** — 키 한 번 누르면 F1 라디오 시작 띠리링이 재생됨. 디스코드 화면에서도 작동.
- **크로스 플랫폼** — macOS, Windows 모두 지원.
- **세 가지 실행 모드** — 라이브(가상 케이블 출력), 모니터(스피커로 직접 듣기), 오프라인(WAV 파일 처리).

## 사운드 비교

| 구분 | 일반 마이크 | F1 Radio Filter |
|------|------------|-----------------|
| 주파수 대역 | 20Hz~20kHz | 100~1200Hz |
| 다이내믹 | 자연스러운 변화 | 4:1 압축 |
| 디스토션 | 거의 없음 | 18dB drive |
| 배경 | 무음 또는 환경음 | 침묵 시 캐리어 노이즈 |

## 요구사항

- Python 3.9 이상
- 가상 오디오 케이블 ([BlackHole](https://existential.audio/blackhole/) on macOS / [VB-Cable](https://vb-audio.com/Cable/) on Windows)
- 디스코드, Zoom, OBS 등 가상 마이크 입력을 받을 수 있는 어떤 통신 클라이언트

## 설치

### macOS

```bash
# 1. 저장소 클론
git clone https://github.com/YOUR_USERNAME/box-radio.git
cd box-radio

# 2. 의존성 설치
pip3 install -r requirements.txt

# 3. BlackHole 설치
# https://existential.audio/blackhole/ 에서 2ch 버전 받기

# 4. 권한 부여
# 시스템 설정 → 개인정보 보호 및 보안 → "입력 모니터링" → 터미널 토글 켜기
# (단순 "손쉬운 사용"이 아니라 "입력 모니터링"이어야 함)
# 권한 부여 후 터미널 재시작 (Cmd+Q)
```

### Windows

```cmd
:: 1. 저장소 클론
git clone https://github.com/YOUR_USERNAME/box-radio.git
cd box-radio

:: 2. 의존성 설치
pip install -r requirements.txt

:: 3. VB-Audio Virtual Cable 설치
:: https://vb-audio.com/Cable/ 에서 받아 관리자 권한으로 실행 후 재부팅
```

윈도우에서는 별도 권한 설정이 필요하지 않습니다. 일부 백신(알약, AhnLab 등)이 pynput을 키로거로 인식할 수 있으니 예외 등록이 필요할 수 있어요.

## 사용법

### 1. 장치 인덱스 확인

```bash
python3 f1_radio_filter.py --list
```

출력에서 BlackHole(macOS) 또는 CABLE Input(Windows)의 인덱스를 메모합니다.

### 2. 출력 장치 설정

`f1_radio_filter.py` 상단의 상수를 수정:

```python
OUTPUT_DEVICE = 4   # 위에서 메모한 인덱스
```

### 3. 모드별 실행

```bash
# 라이브 모드: 가상 케이블로 출력 (디스코드용)
python3 f1_radio_filter.py

# 모니터 모드: 본인 스피커/헤드폰으로 출력 (튜닝/테스트용)
python3 f1_radio_filter.py --monitor

# 오프라인 모드: WAV 파일에 필터 적용
python3 f1_radio_filter.py --process input.wav output.wav
```

### 4. 디스코드 설정

- **사용자 설정 → 음성 및 비디오**
- **입력 장치**: `BlackHole 2ch` (macOS) 또는 `CABLE Output (VB-Audio Virtual Cable)` (Windows)
- **노이즈 억제**: 반드시 "없음"으로 변경 — Krisp이 라디오 효과를 노이즈로 인식해 깎아냅니다
- **에코 제거 / 자동 게인 / 자동 입력 감도**: 모두 끄기

설정 페이지의 "Let's Check / 마이크 테스트" 버튼으로 친구가 듣게 될 사운드를 미리 확인할 수 있습니다.

### 5. 알림음 트리거

스크립트가 실행 중일 때 `` ` `` (백쿼트) 키를 누르면 F1 팀 라디오 시작 알림음이 재생됩니다. 디스코드, 브라우저, 어떤 앱에 포커스가 있어도 작동합니다.

알림음 재생 중에는 캐리어 노이즈가 자동으로 차단되니 "띠리링 → 무전" 흐름이 자연스럽게 연결됩니다.

## 설정

`f1_radio_filter.py` 상단의 상수들을 수정해 사운드를 본인 취향에 맞게 튜닝할 수 있습니다.

### 필터 강도

```python
HIGHPASS_HZ = 100              # 저음 컷 (낮출수록 두꺼움, 높일수록 가늘어짐)
LOWPASS_HZ = 1200              # 고음 컷 (낮출수록 깡통, 높일수록 명료)
COMPRESSOR_THRESHOLD_DB = -18  # 압축 시작점
COMPRESSOR_RATIO = 4           # 압축 비율 (높을수록 평탄함)
DISTORTION_DRIVE_DB = 18       # 디스토션 강도 (높을수록 거침)
OUTPUT_GAIN_DB = -3            # 최종 출력 게인
NOISE_AMOUNT = 0.030           # 캐리어 노이즈 양 (0이면 노이즈 없음)
```

### 노이즈 덕킹

```python
VOICE_THRESHOLD = 0.008  # 음성 감지 민감도 (낮을수록 민감)
DUCK_HOLD_MS = 300       # 음성 종료 후 노이즈 차단 유지 시간
DUCK_RELEASE_MS = 150    # 노이즈 복귀 페이드 시간
```

### 알림음 트리거

```python
ALERT_FILENAME = "f1_radio_alert.wav"   # 알림음 파일 이름
TRIGGER_KEY = "`"                       # 트리거 키 ("f1"~"f12" 또는 한 글자)
ALERT_GAIN = 1.0                        # 알림음 볼륨
```

## 튜닝 가이드

상황별 추천 조정:

| 증상 | 조정 |
|------|------|
| 너무 먹먹해서 알아듣기 힘듦 | `LOWPASS_HZ` ↑ (1500~2000) |
| 깡통감이 부족해서 평범함 | `LOWPASS_HZ` ↓ (800~1000) |
| 디스토션이 너무 거칠어서 거슬림 | `DISTORTION_DRIVE_DB` ↓ (10~14) |
| 친구가 노이즈 거슬려함 | `NOISE_AMOUNT` = 0 (또는 0.010) |
| 단어 사이로 노이즈 새어 나옴 | `DUCK_HOLD_MS` ↑ (500) |
| 노이즈 복귀가 너무 갑작스러움 | `DUCK_RELEASE_MS` ↑ (300~500) |

자세한 튜닝은 모니터 모드(`--monitor`)에서 빠르게 들으면서 반복하거나, 오프라인 모드(`--process`)에서 같은 입력에 다른 설정을 비교 청취하는 게 효율적입니다.

## 동작 원리

### 데이터 흐름

```
마이크 입력
   ↓
[모노 변환]
   ↓
[Highpass Filter] ── 100Hz 이하 컷
   ↓
[Lowpass Filter] ─── 1200Hz 이상 컷
   ↓
[Compressor] ─────── 다이내믹 평탄화 (4:1)
   ↓
[Distortion] ─────── 18dB 드라이브
   ↓
[Gain] ────────────── 클리핑 방지
   ↓
[Noise Mixing] ────── 음성 활동에 따라 0~1.0 스케일링
   ↓
가상 오디오 케이블 출력
```

### 노이즈 덕킹 상태 머신

```
        ┌─── 음성 감지 ───┐
        ↓                ↑
    [차단 (0)]        [홀드 (0)]
        │                ↑
        └─ 음성 끝 ──────┘
                         │ 300ms 경과
                         ↓
                   [릴리스 페이드]
                         │ 150ms 경과
                         ↓
                  [정상 (1.0)]
                         │
                         └─ 음성 감지되면 위로 ─┐
                                              ↑
```

### 키보드 트리거

- pynput 라이브러리로 글로벌 키보드 리스너를 백그라운드 스레드에서 실행
- 키 입력 시 lock-free 플래그(`_trigger_pending`)만 set
- 오디오 콜백이 매 블록마다 플래그를 check & consume
- 트리거 발견 시 알림음 position을 0으로 리셋해 처음부터 재생
- 락을 쓰지 않아 실시간 오디오 스레드의 지연 위험 없음

## 트러블슈팅

### macOS에서 Ctrl+C로 종료가 안 됨

PortAudio가 시그널을 가로채는 경우가 있어 스크립트는 `os._exit(0)`로 강제 종료합니다. 그래도 안 되면:

```bash
pkill -9 -f f1_radio_filter
```

### "Operation not permitted" (macOS)

Downloads, Documents, Desktop 폴더는 macOS의 TCC가 보호합니다. 스크립트를 홈 디렉토리(`~/`)로 옮기거나 시스템 설정에서 터미널에 해당 폴더 접근 권한을 부여하세요.

### 알림음 트리거가 작동하지 않음 (macOS)

1. 시스템 설정 → 개인정보 보호 및 보안 → **입력 모니터링** (손쉬운 사용 아님) → 터미널 토글 확인
2. 권한 변경 후 터미널 완전히 종료 후 재시작
3. F8 같은 미디어 키는 macOS가 가로챕니다 — 백쿼트(`` ` ``) 같은 일반 키로 변경

### Invalid number of channels 에러

AirPods 같은 블루투스 장치가 모노 출력만 지원하는 경우 발생합니다. 스크립트에 자동 채널 감지 로직이 있어 일반적으로 해결되지만, 그래도 발생하면 `--list`로 장치를 확인하고 `INPUT_DEVICE`/`OUTPUT_DEVICE`를 명시적으로 지정해 보세요.

### 무한 피드백 (위용위용 소리)

스피커로 듣고 있어서 출력이 다시 마이크로 들어가는 상황입니다. **반드시 헤드폰을 사용**하세요.

### 친구가 본인 목소리를 못 들음

- 디스코드 입력 장치가 가상 케이블로 잘 설정됐는지 확인
- 디스코드 노이즈 억제(Krisp)가 꺼져 있는지 확인 (켜져 있으면 라디오 효과를 노이즈로 인식해 음성을 거의 다 깎음)
- 가상 케이블이 시스템 기본 출력으로 잘못 잡혀 있는지 확인

## 비대칭 사용 시나리오

본인만 이 필터를 쓰고 친구는 평범하게 디스코드를 쓸 경우, 자연스러운 F1 팀 라디오 분위기가 됩니다.

- **본인** = 드라이버 (헬멧 안 라디오 사운드)
- **친구** = 레이스 엔지니어 (피트월의 깨끗한 헤드셋)

이 시나리오에서 친구가 치지직을 거슬려한다면 `NOISE_AMOUNT = 0`으로 설정해 노이즈만 빼고 깡통 사운드만 남기는 게 자연스러워요. 실제 F1에서도 캐리어 노이즈는 엔지니어 측의 환경 소음을 마스킹하기 위함이지, 음성 명료도를 위한 게 아니거든요.

## 의존성

- [sounddevice](https://github.com/spatialaudio/python-sounddevice) — PortAudio 바인딩, 실시간 오디오 입출력
- [numpy](https://numpy.org/) — 오디오 버퍼 처리
- [pedalboard](https://github.com/spotify/pedalboard) — Spotify의 오디오 이펙트 라이브러리 (Compressor, Distortion 등 고품질 구현)
- [pynput](https://github.com/moses-palmer/pynput) — 글로벌 키보드 리스너
- [scipy](https://scipy.org/) — 리샘플링 및 신호 처리

## 라이선스

MIT License — 자세한 내용은 [LICENSE](./LICENSE) 참고.

## 기여

기여는 환영입니다.
- 다른 드라이버 스타일 프리셋 (해밀턴, 페르스타펜, 르클레르 등)
- 다른 시뮬레이터/게임 통합
- 다른 OS 지원

## 면책

오픈소스 프로젝트입니다. 친구와의 디스코드 통화에서 F1 분위기를 즐기는 용도로 만들어졌습니다. 실제 F1 팀과는 무관하며, 사인츠 분석에 사용된 오디오는 공개된 방송 클립이고 분석 목적으로만 사용했습니다.

알림음 파일(`f1_radio_alert.wav`)은 F1 라디오 인트로 사운드 효과를 모방한 1초 클립입니다. 상업적 사용 시 별도의 라이선스 검토가 필요합니다.