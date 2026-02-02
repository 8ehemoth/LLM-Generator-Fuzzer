---

# SOME/IP Playground Service 분석 & LLM-Generator Fuzzer

## Phase A 완료 정리 & Phase B 시작 가이드

---

## 1. 프로젝트 개요

본 프로젝트는 **GENIVI / COVESA test-someip-service**의
`Playground Service (Service ID = 0xFF40)`를 대상으로,

* Wireshark 기반 **SOME/IP 패킷 구조 분석**
* 서비스 메서드/이벤트 **의미(semantic) 매핑**
* 정상 트래픽 기반 **LLM-Generator Fuzzer** 구축

을 목표로 한다.

본 문서는 **Phase A(정적 분석 단계)**의 최종 결과와
**Phase B(LLM 기반 테스트케이스 생성 단계)**의 시작점을 정의한다.

---

## 2. 실험 환경

| 항목           | 값                               |
| ------------ | ------------------------------- |
| OS           | Ubuntu 20.04                    |
| SOME/IP 구현   | vsomeip                         |
| Service      | Playground                      |
| Service ID   | `0xFF40`                        |
| Server IP    | `192.168.40.134`                |
| Client IP    | `192.168.40.135`                |
| Server Port  | `31000/udp`                     |
| Capture File | `test-06-100-2026-02-02.pcapng` |

Wireshark 필터:

```text
udp and (port 30490 or port 31000) and
(host 192.168.40.134 or host 192.168.40.135)
```

---

## 3. Phase A의 목적 (정확한 정의)

Phase A는 **퍼징을 “돌리는 단계”가 아니라**,
**LLM이 유효한 SOME/IP 요청을 생성할 수 있도록 스키마를 고정하는 단계**이다.

Phase A에서 확정해야 하는 것:

1. 서비스 ID / 포트
2. 전체 메서드 & 이벤트 목록
3. 각 메서드의 의미 (Getter / Setter / Command / Event)
4. Request / Response 방향 및 msg_type
5. payload 구조 (특히 Setter/Command)
6. 정상 요청 시퀀스(seed)

---

## 4. Playground Service (0xFF40) 전체 메서드 / 이벤트 매핑

### 4.1 기본 Getter 메서드

| Method ID | 의미                        | 분류     |
| --------- | ------------------------- | ------ |
| `0x0001`  | consumption 조회            | Getter |
| `0x0002`  | capacity 조회               | Getter |
| `0x0003`  | volume 조회                 | Getter |
| `0x0004`  | engineSpeed 조회            | Getter |
| `0x0005`  | currentGear 조회            | Getter |
| `0x0006`  | isReverseGearOn 조회        | Getter |
| `0x0007`  | drivePowerTransmission 조회 | Getter |

특징:

* payload 없음
* `msg_type = 0x00 (Request)`
* Response는 `msg_type = 0x80`

---

### 4.2 Door 관련 메서드

| Method ID | 의미                    | 분류      |
| --------- | --------------------- | ------- |
| `0x0008`  | doorsOpeningStatus 조회 | Getter  |
| `0x000E`  | changeDoorsState      | Command |

`0x000E` 특징:

* **Client → Server**
* `msg_type = 0x02 (Request with payload)`
* payload: 도어별 명령 배열 (OPEN / CLOSE 등)

---

### 4.3 Seat Heating 관련 메서드

| Method ID | 의미                   | 분류     |
| --------- | -------------------- | ------ |
| `0x0009`  | seatHeatingStatus 조회 | Getter |
| `0x000A`  | seatHeatingStatus 설정 | Setter |
| `0x000B`  | seatHeatingLevel 조회  | Getter |
| `0x000C`  | seatHeatingLevel 설정  | Setter |

Setter(`0x000A`, `0x000C`) 공통 특징:

* **Client → Server**
* `msg_type = 0x02`
* payload는 **배열 구조**

  * 배열 길이 N (관찰상 N=7)
  * 각 원소는 Boolean 또는 UInt8

---

### 4.4 기타 Command

| Method ID | 의미                          | 분류      |
| --------- | --------------------------- | ------- |
| `0x000D`  | initTirePressureCalibration | Command |

---

### 4.5 이벤트(Event)

| Event ID | 의미                          |
| -------- | --------------------------- |
| `0x8009` | vehiclePosition broadcast   |
| `0x800A` | currentTankVolume broadcast |

※ 이벤트는 **요청 생성 대상이 아님** (관찰/오라클용)

---

## 5. Phase A 패킷 검증 결과 (Wireshark 기준)

### Phase A “패킷 측면” 완료 조건

아래 3개를 **모두 만족하면 Phase A 완료**로 판단한다.

* `0x000E` 클라→서버 `msg_type=0x02` 샘플 확보
* `0x000A` 클라→서버 `msg_type=0x02` 샘플 확보
* `0x000C` 클라→서버 `msg_type=0x02` 샘플 확보
* 각 payload의 **길이 / 배열 구조 / 값 범위** 메모 완료

### 현재 상태 판정

> ✅ **완료**

* 스크린샷 기준:

  * Source = `192.168.40.135`
  * Dest = `192.168.40.134:31000`
  * payload 존재
  * Length 일관성 확인
* `0x000C` client request까지 확보됨

👉 **Wireshark로 더 볼 필요 없음**
이제 Phase B로 이동 가능

---

## 6. Phase A 결과물 요약

Phase A 산출물:

* ✔ 서비스 스키마 고정
* ✔ 메서드 의미 전체 매핑
* ✔ Setter/Command payload 구조 확보
* ✔ 정상 요청 seed 정의 가능

Phase A는 **기술적으로 완료**되었다.

---

## 7. Phase B 개요 (LLM-Generator 단계)

Phase B의 목표:

> **“정상 SOME/IP 요청 스키마를 입력으로 받아,
> 의미 있는 변형 요청(test case)을 자동 생성”**

### Phase B 구성 요소

1. 정상 seed(JSON)
2. OpenAI API (LLM)
3. mutation policy
4. SOME/IP 송신기
5. 오라클 (timeout / error / crash)

---

## 8. Phase B – 기본 코드 구조

### 8.1 디렉터리 구조 예시

```text
phaseB/
 ├─ seeds/
 │   └─ door_open.json
 ├─ schemas/
 │   └─ method_0x000c.json
 ├─ llm/
 │   └─ generator.py
 ├─ sender/
 │   └─ someip_sender.py
 └─ main.py
```

---

### 8.2 OpenAI API 연동 (Python)

#### 1) API 키 설정

```bash
export OPENAI_API_KEY="sk-xxxx"
```

#### 2) LLM Generator 예시 코드

```python
# llm/generator.py
from openai import OpenAI
import json

client = OpenAI()

def generate_testcase(schema, seed):
    prompt = f"""
You are generating SOME/IP test cases.

Schema:
{json.dumps(schema, indent=2)}

Seed:
{json.dumps(seed, indent=2)}

Generate one mutated test case.
Return JSON only.
"""

    resp = client.responses.create(
        model="gpt-4.1-mini",
        input=prompt
    )

    return resp.output_text
```

---

### 8.3 SOME/IP 송신기 (스켈레톤)

```python
# sender/someip_sender.py
import socket

def send_someip(payload_bytes):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.sendto(payload_bytes, ("192.168.40.134", 31000))
```

---

### 8.4 Phase B 메인 루프

```python
# main.py
from llm.generator import generate_testcase
from sender.someip_sender import send_someip
import json

schema = json.load(open("schemas/method_0x000c.json"))
seed = json.load(open("seeds/door_open.json"))

testcase = generate_testcase(schema, seed)
print(testcase)
```

---

## 9. 다음 단계 제안

이제 할 일은 딱 3개다.

1. `0x000A`, `0x000C` payload 스키마 JSON화
2. 정상 seed 2~3개 작성
3. mutation rule 정의 (범위 초과, 길이 변형 등)

