"""
F1 Team Radio Voice Filter for Discord
=======================================

마이크 입력에 F1 팀 라디오 풍 필터를 실시간으로 걸어서
가상 오디오 케이블(VB-Cable / BlackHole)로 출력합니다.

이 버전 추가 기능:
- F8 키 트리거 알림음 재생 (사인츠 라디오 시작 띠리링)
- 알림음 재생 중 캐리어 노이즈 자동 차단
- macOS 글로벌 핫키 지원 (디스코드 화면에서도 작동)

사전 준비
---------
1. 가상 오디오 케이블 설치 (VB-Cable / BlackHole)
2. pip3 install sounddevice numpy pedalboard pynput scipy
3. 알림음 파일 'f1_radio_alert.wav'을 스크립트와 같은 디렉토리에 두기
4. macOS: 시스템 설정 → 개인정보 보호 및 보안 → 손쉬운 사용
   에서 터미널 앱에 권한 부여 (글로벌 핫키 작동에 필요)

사용 모드
---------
    python3 f1_radio_filter.py --list
    python3 f1_radio_filter.py            # 라이브
    python3 f1_radio_filter.py --monitor  # 모니터
    python3 f1_radio_filter.py --process input.wav output.wav
"""

import argparse
import os
import signal
import sys
import threading
from math import gcd
from pathlib import Path

import numpy as np
import sounddevice as sd
from pedalboard import (
    Pedalboard,
    HighpassFilter,
    LowpassFilter,
    Compressor,
    Distortion,
    Gain,
)

# ============================================================
# 오디오 설정
# ============================================================
SAMPLE_RATE = 48000
BLOCK_SIZE = 512

INPUT_DEVICE = None
OUTPUT_DEVICE = None

# ============================================================
# 필터 튜닝 (사인츠 레퍼런스 기반)
# ============================================================
HIGHPASS_HZ = 100
LOWPASS_HZ = 1200
COMPRESSOR_THRESHOLD_DB = -18
COMPRESSOR_RATIO = 4
DISTORTION_DRIVE_DB = 18
OUTPUT_GAIN_DB = -3

# default 노이즈(치지직 소리)를 넣고싶으면
# NOISE_AMOUNT = 0.030

# default 노이즈를 제거하고싶으면 
NOISE_AMOUNT = 0

# ============================================================
# 노이즈 덕킹
# ============================================================
VOICE_THRESHOLD = 0.008
DUCK_HOLD_MS = 300
DUCK_RELEASE_MS = 150

# ============================================================
# 알림음 트리거
# ============================================================
ALERT_FILENAME = "f1_radio_alert.wav"   # 스크립트와 같은 디렉토리에 위치
TRIGGER_KEY = "`"                       # f1~f12 또는 알파벳 한 글자
ALERT_GAIN = 1.0                         # 알림음 볼륨 (1.0 = 원본)


# ============================================================
# pynput 임포트 (없으면 알림 기능 비활성화)
# ============================================================
try:
    from pynput import keyboard as pynput_keyboard
    HAS_PYNPUT = True
except ImportError:
    HAS_PYNPUT = False


def _ms_to_blocks(ms: float) -> int:
    return max(1, int(ms / 1000 * SAMPLE_RATE / BLOCK_SIZE))


# ============================================================
# 노이즈 덕커
# ============================================================
class NoiseDucker:
    def __init__(self):
        self.threshold = VOICE_THRESHOLD
        self.hold_blocks = _ms_to_blocks(DUCK_HOLD_MS)
        self.release_blocks = _ms_to_blocks(DUCK_RELEASE_MS)
        self.hold_counter = 0
        self.release_counter = 0

    def get_noise_scale(self, mono_input: np.ndarray) -> float:
        rms = float(np.sqrt(np.mean(mono_input ** 2)))

        if rms > self.threshold:
            self.hold_counter = self.hold_blocks
            self.release_counter = self.release_blocks
            return 0.0

        if self.hold_counter > 0:
            self.hold_counter -= 1
            return 0.0

        if self.release_counter > 0:
            self.release_counter -= 1
            return 1.0 - (self.release_counter / self.release_blocks)

        return 1.0


# ============================================================
# 알림음 플레이어 (락 없이 단방향 트리거 플래그 사용)
# ============================================================
class AlertPlayer:
    def __init__(self, alert_audio: np.ndarray):
        self.alert = alert_audio
        self._position = -1            # -1 = 유휴 상태
        self._trigger_pending = False  # 키 입력으로 set, 콜백이 consume

    def trigger(self):
        """키보드 스레드에서 호출 — 다음 콜백에서 재생 시작."""
        self._trigger_pending = True

    def get_chunk(self, frames: int):
        """오디오 콜백에서 호출 — 알림음 청크 반환 (없으면 None)."""
        # 트리거 대기 중이면 처음부터 다시 재생
        if self._trigger_pending:
            self._trigger_pending = False
            self._position = 0

        if self._position < 0:
            return None

        end = min(self._position + frames, len(self.alert))
        chunk_size = end - self._position

        chunk = np.zeros(frames, dtype=np.float32)
        chunk[:chunk_size] = self.alert[self._position:end]

        self._position = end
        if self._position >= len(self.alert):
            self._position = -1

        return chunk


def load_alert() -> np.ndarray:
    """알림음 파일을 모노 + 48kHz로 로드. 실패 시 None."""
    alert_path = Path(__file__).parent / ALERT_FILENAME
    if not alert_path.exists():
        # 현재 디렉토리에서도 한 번 찾아봄
        alert_path = Path.cwd() / ALERT_FILENAME
        if not alert_path.exists():
            return None

    try:
        from pedalboard.io import AudioFile
        with AudioFile(str(alert_path)) as f:
            audio = f.read(f.frames)
            sr = f.samplerate

        if audio.ndim > 1 and audio.shape[0] > 1:
            mono = audio.mean(axis=0).astype(np.float32)
        else:
            mono = audio.flatten().astype(np.float32)

        if sr != SAMPLE_RATE:
            from scipy.signal import resample_poly
            g = gcd(sr, SAMPLE_RATE)
            mono = resample_poly(mono, SAMPLE_RATE // g, sr // g).astype(np.float32)

        return mono
    except Exception as e:
        print(f"[warning] 알림음 로드 실패: {e}", file=sys.stderr)
        return None


# ============================================================
# 키보드 리스너
# ============================================================
def parse_trigger_key(key_str: str):
    """문자열을 pynput 키 객체로 변환."""
    key_str = key_str.lower()
    if hasattr(pynput_keyboard.Key, key_str):
        return getattr(pynput_keyboard.Key, key_str)
    if len(key_str) == 1:
        return pynput_keyboard.KeyCode.from_char(key_str)
    raise ValueError(f"인식할 수 없는 키: {key_str}")


def start_keyboard_listener(alert_player: AlertPlayer):
    """글로벌 키보드 리스너 시작. F8 누르면 알림음 트리거."""
    target_key = parse_trigger_key(TRIGGER_KEY)

    def on_press(key):
        if key == target_key:
            alert_player.trigger()
            print("  ♪ 알림음", flush=True)

    listener = pynput_keyboard.Listener(on_press=on_press)
    listener.daemon = True
    listener.start()
    return listener


# ============================================================
# 필터 체인
# ============================================================
def build_board() -> Pedalboard:
    return Pedalboard([
        HighpassFilter(cutoff_frequency_hz=HIGHPASS_HZ),
        LowpassFilter(cutoff_frequency_hz=LOWPASS_HZ),
        Compressor(
            threshold_db=COMPRESSOR_THRESHOLD_DB,
            ratio=COMPRESSOR_RATIO,
            attack_ms=5,
            release_ms=50,
        ),
        Distortion(drive_db=DISTORTION_DRIVE_DB),
        Gain(gain_db=OUTPUT_GAIN_DB),
    ])


# ============================================================
# 채널 자동 감지
# ============================================================
def detect_channels(input_device, output_device):
    in_idx = input_device if input_device is not None else sd.default.device[0]
    out_idx = output_device if output_device is not None else sd.default.device[1]

    try:
        max_in = sd.query_devices(in_idx).get("max_input_channels", 1)
    except Exception:
        max_in = 1
    try:
        max_out = sd.query_devices(out_idx).get("max_output_channels", 2)
    except Exception:
        max_out = 2

    in_channels = 1 if max_in >= 1 else 0
    out_channels = 2 if max_out >= 2 else (1 if max_out >= 1 else 0)

    if in_channels == 0:
        raise RuntimeError("입력 장치가 마이크 입력을 지원하지 않습니다.")
    if out_channels == 0:
        raise RuntimeError("출력 장치가 출력을 지원하지 않습니다.")
    return (in_channels, out_channels)


# ============================================================
# 콜백
# ============================================================
def make_callback(board: Pedalboard, alert_player):
    ducker = NoiseDucker()

    def audio_callback(indata, outdata, frames, time, status):
        if status:
            print(f"[stream] {status}", file=sys.stderr)

        mono = indata[:, 0].astype(np.float32)
        processed = board(mono, SAMPLE_RATE, reset=False)

        # 덕커 상태는 항상 갱신 (입력 음성 추적)
        noise_scale = ducker.get_noise_scale(mono)

        # 알림음 청크 가져오기
        alert_chunk = alert_player.get_chunk(frames) if alert_player is not None else None

        if alert_chunk is not None:
            # 알림음 재생 중 — 알림음 믹스, 노이즈 차단
            processed = processed + alert_chunk * ALERT_GAIN
        elif NOISE_AMOUNT > 0 and noise_scale > 0:
            # 평소 — 덕킹된 노이즈 추가
            noise = np.random.randn(frames).astype(np.float32) * NOISE_AMOUNT * noise_scale
            processed = processed + noise

        processed = np.clip(processed, -1.0, 1.0)

        for ch in range(outdata.shape[1]):
            outdata[:, ch] = processed

    return audio_callback


# ============================================================
# 시그널 처리
# ============================================================
def _handle_signal(signum, frame):
    print("\n[F1 Radio Filter] 종료", flush=True)
    os._exit(0)


def _install_signal_handlers():
    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)


# ============================================================
# 모드 1: 장치 목록
# ============================================================
def list_devices():
    print(sd.query_devices())
    print()
    default_in, default_out = sd.default.device
    print(f"기본 입력: {default_in}, 기본 출력: {default_out}")


# ============================================================
# 모드 2: 라이브 / 모니터
# ============================================================
def run_live(monitor: bool = False):
    _install_signal_handlers()

    board = build_board()

    # 알림음 로드 시도
    alert_audio = load_alert()
    alert_player = AlertPlayer(alert_audio) if alert_audio is not None else None

    # 키보드 리스너 시작 시도
    listener = None
    if alert_player is not None and HAS_PYNPUT:
        try:
            listener = start_keyboard_listener(alert_player)
        except Exception as e:
            print(f"[warning] 키보드 리스너 시작 실패: {e}", file=sys.stderr)

    callback = make_callback(board, alert_player)

    out_device = None if monitor else OUTPUT_DEVICE
    mode_label = "MONITOR (마이크 → 기본 스피커)" if monitor else "LIVE (마이크 → 가상 케이블)"

    try:
        channels = detect_channels(INPUT_DEVICE, out_device)
    except RuntimeError as e:
        print(f"[error] {e}", file=sys.stderr)
        sys.exit(1)

    print(f"[F1 Radio Filter] {mode_label}")
    print(f"  - 채널: {channels[0]}ch in / {channels[1]}ch out")
    print(f"  - 대역: {HIGHPASS_HZ}~{LOWPASS_HZ} Hz, 압축비 {COMPRESSOR_RATIO}:1, "
          f"드라이브 {DISTORTION_DRIVE_DB}dB")
    print(f"  - 노이즈: {NOISE_AMOUNT}, 덕킹 홀드 {DUCK_HOLD_MS}ms")

    # 알림음 / 키보드 상태 표시
    if alert_player is None:
        print(f"  - 알림음: 비활성 (파일 '{ALERT_FILENAME}' 없음)")
    elif not HAS_PYNPUT:
        print(f"  - 알림음: 로드됨, 트리거 비활성 (pip3 install pynput 필요)")
    elif listener is None:
        print(f"  - 알림음: 로드됨, 트리거 시작 실패")
    else:
        print(f"  - 알림음: '{TRIGGER_KEY.upper()}' 키로 트리거")
        print(f"           (macOS는 터미널 앱에 손쉬운 사용 권한 필요)")

    print("  Ctrl+C 로 종료\n")

    try:
        with sd.Stream(
            samplerate=SAMPLE_RATE,
            blocksize=BLOCK_SIZE,
            device=(INPUT_DEVICE, out_device),
            channels=channels,
            dtype="float32",
            callback=callback,
        ):
            threading.Event().wait()
    except Exception as e:
        print(f"\n[error] {e}", file=sys.stderr)
        print("→ --list 로 장치 목록을 확인해 보세요.", file=sys.stderr)
        sys.exit(1)


# ============================================================
# 모드 3: 오프라인 파일 처리 (알림음 미적용)
# ============================================================
def process_file(input_path: str, output_path: str):
    from pedalboard.io import AudioFile

    src = Path(input_path)
    if not src.exists():
        print(f"[error] 입력 파일 없음: {src}", file=sys.stderr)
        sys.exit(1)

    print(f"[F1 Radio Filter] 오프라인 처리")
    print(f"  - 입력: {src}")
    print(f"  - 출력: {output_path}")

    board = build_board()

    with AudioFile(str(src)) as f:
        audio = f.read(f.frames)
        sr = f.samplerate

    if audio.ndim > 1 and audio.shape[0] > 1:
        audio_mono = audio.mean(axis=0).astype(np.float32)
    else:
        audio_mono = audio.flatten().astype(np.float32)

    print(f"  - 길이: {len(audio_mono) / sr:.2f}초 @ {sr}Hz")

    processed = board(audio_mono, sr, reset=True)

    if NOISE_AMOUNT > 0:
        ducker = NoiseDucker()
        for i in range(0, len(processed), BLOCK_SIZE):
            end = min(i + BLOCK_SIZE, len(processed))
            input_chunk = audio_mono[i:end]
            scale = ducker.get_noise_scale(input_chunk)
            if scale > 0:
                noise = np.random.randn(end - i).astype(np.float32) * NOISE_AMOUNT * scale
                processed[i:end] = processed[i:end] + noise

    processed = np.clip(processed, -1.0, 1.0)

    output = processed.reshape(1, -1)
    with AudioFile(output_path, "w", sr, num_channels=1) as f:
        f.write(output)

    print("  완료 ✓")


# ============================================================
# 진입점
# ============================================================
def main():
    parser = argparse.ArgumentParser(description="F1 팀 라디오 풍 보이스 필터")
    parser.add_argument("--list", action="store_true", help="오디오 장치 목록")
    parser.add_argument("--monitor", action="store_true",
                        help="모니터 모드 (마이크 → 기본 스피커)")
    parser.add_argument("--process", nargs=2, metavar=("INPUT", "OUTPUT"),
                        help="오프라인 모드 (input.wav → output.wav)")
    args = parser.parse_args()

    if args.list:
        list_devices()
    elif args.process:
        process_file(args.process[0], args.process[1])
    elif args.monitor:
        run_live(monitor=True)
    else:
        run_live(monitor=False)


if __name__ == "__main__":
    main()