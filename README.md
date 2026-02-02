# LLM-Generator Fuzzer for `test-someip-service` (SOME/IP Playground)

> 목표: `test-someip-service`(Playground) 트래픽을 기반으로  
> **LLM을 입력 생성/변이 엔진으로 활용**하고,  
> 실제 전송은 기존 `PlaygroundClient`(고수준 호출)로 수행하는 **LLM-Generator Fuzzer(2번 방식)** 를 구현한다.

---

## 0) 큰 그림 (Phase A → Phase B)

- **Phase A (스키마/시드 고정 단계)**  
  캡처(PCAPNG) + 코드(client.zip) 기반으로
  - Service/Method/Event 식별
  - 요청/응답 방향 및 msg_type 패턴 확인
  - 각 메서드의 의미(semantic) + payload 스키마(파라미터 타입/길이/범위) 고정
  - 정상 시퀀스(seed) 정의
  - LLM이 출력할 테스트케이스 포맷(JSON) 고정  
  → **Phase B에서 LLM이 “무엇을 어떻게 생성/변이해야 하는지”가 흔들리지 않게 만드는 단계**

- **Phase B (생성/변이 + 실행 루프)**  
  - LLM: 테스트케이스(JSON) 생성/변이
  - Runner: JSON을 해석해서 기존 클라이언트(PlaygroundClient)를 호출해 전송
  - Oracle: timeout / error response / server crash / 로그 오류 등을 “흥미(interesting)”로 판정
  - Coverage/흥미 케이스를 다시 LLM에 피드백 → 다음 입력 생성

---

## 1) 실험 환경 / 입력 데이터

### 1.1 환경
- Server: `192.168.40.134`
- Client: `192.168.40.135`
- 포트(관찰): `30490`(SD/기타), `31000`(서비스 통신)

### 1.2 Wireshark 캡처 필터(예시)
- Display filter:
  - `udp and (port 30490 or port 31000) and (host 192.168.40.134 or host 192.168.40.135)`

### 1.3 확보 파일
- PCAPNG: `test-06-100-2026-02-02.pcapng`
- 클라이언트 코드: `client.zip`

---

## 2) Phase A 목표(정확한 완료 조건)

Phase A는 “퍼징 실행”이 아니라, **퍼저가 돌아가기 위한 사전 지식(스키마)을 고정**하는 단계다.

### 2.1 Phase A에서 확정해야 하는 것(체크리스트)
1) 서비스 식별: **Service ID / (가능하면 Instance ID)** / 포트  
2) 전체 메서드/이벤트 목록: **Method ID / Event ID**  
3) 각 메서드 의미(semantic) + 타입: Getter / Setter / Command / Event  
4) 요청/응답 방향 + SOME/IP `msg_type` 패턴  
5) payload 스키마(특히 setter/command 인자 구조)  
6) 정상 시퀀스(seed) 2~3개 정의  
7) LLM 출력 포맷(JSON) 고정  
8) 오라클(흥미 판정 기준) 고정

---

## 3) SOME/IP 헤더 최소 검증 규칙(Phase A에서 가장 중요)

SOME/IP 고정 헤더는 16바이트이며, 실무적으로 Phase A에서는 아래만 확실히 잡으면 된다.

- Service ID (2B)
- Method/Event ID (2B)
- Length (4B)
- Request ID (4B)
- Protocol Ver / Interface Ver / **Message Type** / Return Code (각 1B)

### 3.1 Message Type(msg_type) 기준(자주 쓰는 값)
- `0x00`: Request (payload 없는 getter에서 흔함)
- `0x02`: Request with payload (setter/command에서 흔함)
- `0x80`: Response
- `0x81`: Error Response

> Phase A 완료를 선언하려면, setter/command에 대해 **“클라→서버 + msg_type=0x02 + payload 구조”** 를 샘플로 확정해야 한다.

---

## 4) Playground Service(0xFF40) 메서드/이벤트 의미 매핑표(서비스 전체)

> 아래 표는 “기본 + door + heating”을 포함한 서비스 전체 기준 정리다.  
> (정확한 파라미터 타입/길이/범위는 Phase A에서 샘플 기반으로 최종 고정한다.)

### 4.1 Getter 중심 기본 메서드(0x0001 ~ 0x0007)

| Method ID | 의미(semantic) | 분류 | 요청 payload | 응답 payload |
|---:|---|---|---|---|
| 0x0001 | consumption 조회 | Getter | 없음 | 있음 |
| 0x0002 | capacity 조회 | Getter | 없음 | 있음 |
| 0x0003 | volume 조회 | Getter | 없음 | 있음 |
| 0x0004 | engineSpeed 조회 | Getter | 없음 | 있음 |
| 0x0005 | currentGear 조회 | Getter | 없음 | 있음 |
| 0x0006 | isReverseGearOn 조회 | Getter | 없음 | 있음 |
| 0x0007 | drivePowerTransmission 조회 | Getter | 없음 | 있음 |

### 4.2 Door 관련(0x0008, 0x000E)

| Method ID | 의미(semantic) | 분류 | 요청 payload | 응답 payload |
|---:|---|---|---|---|
| 0x0008 | doorsOpeningStatus 조회 | Getter | 없음 | 있음(문 상태) |
| 0x000E | changeDoorsState(문 상태 변경) | Command | 있음 | ACK/결과 |

### 4.3 Seat Heating 관련(0x0009 ~ 0x000C)

| Method ID | 의미(semantic) | 분류 | 요청 payload | 응답 payload |
|---:|---|---|---|---|
| 0x0009 | seatHeatingStatus 조회 | Getter | 없음 | 있음(Boolean[]) |
| 0x000A | seatHeatingStatus 설정 | Setter | 있음(Boolean[]) | ACK/결과 |
| 0x000B | seatHeatingLevel 조회 | Getter | 없음 | 있음(UInt8[]) |
| 0x000C | seatHeatingLevel 설정 | Setter | 있음(UInt8[]) | ACK/결과 |

### 4.4 Command 성격(0x000D)

| Method ID | 의미(semantic) | 분류 | 요청 payload | 응답 payload |
|---:|---|---|---|---|
| 0x000D | initTirePressureCalibration 트리거 | Command | 없음/단순 | ACK/결과 |

### 4.5 Event(브로드캐스트)

| Event ID | 의미(semantic) | 형태 | 비고 |
|---:|---|---|---|
| 0x8009 | vehiclePosition broadcast | Event | 관찰/오라클 보조 |
| 0x800A | currentTankVolume broadcast | Event | 관찰/오라클 보조 |

---

## 5) Wireshark에서 “무엇까지 보면 Phase A 끝이냐?”

결론부터 말하면:

- **방향(클라 ephemeral → 서버 31000)** 을 찾은 것만으로는 “거의 끝”이지만,
- setter/command에 대해 **msg_type=0x02 + payload 구조까지** 1개 샘플로 확정해야 “완료”라고 말할 수 있다.

### 5.1 지금 캡처에서 “클라 요청” 후보를 찾는 기준
- `Src IP = 192.168.40.135` (Client)
- `Dst IP = 192.168.40.134` (Server)
- `Dst Port = 31000`
- `Src Port = ephemeral(예: 57553 등)`
- SOME/IP 헤더에서:
  - service_id = `0xFF40`
  - method_id = `0x000A` 또는 `0x000C` 또는 `0x000E`
  - **msg_type = 0x02**(Request with payload)

### 5.2 “이제 Wireshark 확인 끝인가?” (판정)
아래를 만족하면 Phase A의 “패킷 측면 확인”은 끝이라고 볼 수 있다.

- [ ] `0x000E`에 대해 클라→서버 `msg_type=0x02` 샘플 1개 확정
- [ ] `0x000A`에 대해 클라→서버 `msg_type=0x02` 샘플 1개 확정
- [ ] `0x000C`에 대해 클라→서버 `msg_type=0x02` 샘플 1개 확정
- [ ] 각 샘플에서 payload 길이/형태(배열 길이 N, 원소 타입/범위)를 간단히 메모

> 질문에서 올려주신 “0x000C 관련 클라 요청” 스크린샷은 **방향/포트 관점에서 매우 유력**합니다.  
> 다만 “완료 선언”은 **msg_type=0x02가 맞는지**를 16B SOME/IP 헤더에서 한 번 더 확인하고 마무리하는 게 안전합니다.

---

## 6) Phase B 설계(추천 방식)

본 프로젝트는 교수님이 말한 “LLM-Generator Fuzzer”에 맞춰 아래 형태를 권장한다.

### 6.1 권장 구조(2번 방식)
- LLM은 **고수준 호출(testcase JSON)** 을 생성/변이
- 실제 전송은 **기존 PlaygroundClient 호출(정상 스택 사용)** 로 수행

**장점**
- raw 패킷 조립보다 구현 난이도 낮음
- serialization/endianness/length/checksum 문제를 기존 스택이 처리
- “유효한 요청” 비율이 올라가 퍼징 효율이 좋아짐

**단점**
- 프로토콜 스택 아래(패킷 레벨) 취약점은 덜 긁을 수 있음
- 클라이언트가 허용하는 범위 밖 입력은 보내기 어려울 수 있음(하지만 이건 우회 가능: 파라미터 변이 폭을 점진적으로 넓히기)

---

## 7) Phase B 코드 (LLM 생성 + 실행 루프)

아래 코드는 “뼈대”이며,
- `client.zip`의 실제 실행 커맨드/인자 규격은 프로젝트에 맞게 연결해야 한다.
- 안전을 위해 **연구실/로컬 VM 환경에서만** 실행한다.

### 7.1 설치
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -U openai
