# test-someip-service LLM-Generator Fuzzer (Phase A)

본 프로젝트는 `test-someip-service`(SOME/IP) 트래픽을 캡처(pcapng)하고,
소스코드/IDL(Franca) 기반으로 **Service ID / Method ID / 의미(semantic)**를 매핑한 뒤,
LLM이 생성하는 테스트케이스(JSON)를 기존 클라이언트 호출로 실행하는
**LLM-Generator Fuzzer(고수준 호출 생성/변이)**를 구현하는 것을 목표로 한다.

---

## 1. 환경 / 캡처 조건

- Topology: Client VM (192.168.40.135) ↔ Server VM (192.168.40.134)
- Ports:
  - 30490/UDP: SOME/IP Service Discovery(SD)
  - 31000/UDP: SOME/IP Service traffic
- Wireshark Display Filter 예시:
  - `udp and (port 30490 or port 31000) and (host 192.168.40.134 or host 192.168.40.135)`

---

## 2. Phase A 목표

Phase A는 LLM이 “무작정 hex 생성”을 하는 것이 아니라,
**의미 단위(semantic)**로 테스트를 생성/변이할 수 있도록 아래를 확정하는 단계이다.

1) Service ID 확정  
2) Method ID ↔ 의미 매핑  
3) 정상 시퀀스(seed) 추출  
4) LLM 출력 포맷(JSON) 고정  
5) 변이 전략 정의  
6) 오라클(흥미 판정 기준) 정의

---

## 3. Service ID 확정

- Playground Service ID: `0xFF40`
  - Franca deployment 및 생성 코드에서 `SomeIpServiceID=65344` 확인
  - 65344(decimal) = 0xFF40(hex)

---

## 4. Method 의미 매핑표 (Playground: 0xFF40)

### 4.1 공통: SOME/IP MsgType(헤더의 Message Type) 참고

- 0x00: Request
- 0x02: Request (with payload)
- 0x80: Response
- 0x81: Error Response

Method ID만으로 Request/Response를 단정하지 말고 MsgType으로 방향/성격을 함께 판정한다.

---

### 4.2 Door(문) 관련

| Method ID | 의미(semantic) | 구분 | 요청 payload | 설명 |
|---:|---|---|---|---|
| 0x0008 | doorsOpeningStatus | Getter | 없음 | 각 문(예: FL/FR/RL/RR)의 열림 상태 조회 |
| 0x000E | changeDoorsState(commands) | Command/Setter | 있음 | 각 문에 대해 OPEN/CLOSE 같은 커맨드를 내려 상태 변경 |

캡처에서 확인:
- 0x0008: 헤더-only Request 패턴(일반적인 getter)
- 0x000E: Request(with payload) 패턴(문 제어 커맨드)

---

### 4.3 Seat Heating(좌석 히팅) 관련

| Method ID | 의미(semantic) | 구분 | 요청 payload | 설명 |
|---:|---|---|---|---|
| 0x0009 | seatHeatingStatus | Getter | 없음 | 히팅 ON/OFF 상태 배열(Boolean[]) 조회 |
| 0x000A | seatHeatingStatus(values) | Setter | 있음 | 히팅 ON/OFF 배열(Boolean[]) 설정 |
| 0x000B | seatHeatingLevel | Getter | 없음 | 히팅 레벨 배열(UInt8[]) 조회 |
| 0x000C | seatHeatingLevel(values) | Setter | 있음 | 히팅 레벨 배열(UInt8[]) 설정 |

배열 payload 직렬화(전형):
- `[4바이트 길이 N] + [원소 N개]`
- 예: N=7이면 payload가 대개 11 bytes 형태로 관측됨

주의:
- 서버(31000)→클라(ephemeral port) 방향의 프레임은 Response일 가능성이 높다.
- Setter “요청” 샘플은 클라(ephemeral port)→서버(31000) 방향에서 찾아야 한다.

---

### 4.4 기타(자주 등장 가능) Getter/Command

| Method ID | 의미(semantic) | 구분 | 설명 |
|---:|---|---|---|
| 0x0001 | consumption | Getter | 소비/연비/전력 소비 관련 값 조회 |
| 0x0002 | capacity | Getter | 용량 관련 값 조회 |
| 0x0003 | volume | Getter | 부피/용량 관련 값 조회 |
| 0x0004 | engineSpeed | Getter | 엔진/모터 회전수 조회 |
| 0x0005 | currentGear | Getter | 현재 기어 상태 조회 |
| 0x0006 | isReverseGearOn | Getter | 후진 여부 조회 |
| 0x0007 | drivePowerTransmission | Getter | 구동 전달 방식 조회 |
| 0x000D | initTirePressureCalibration() | Command | 타이어 공기압 캘리브레이션 트리거 |

---

## 5. Event 매핑(혼동 방지)

| Event ID | 의미(semantic) | 비고 |
|---:|---|---|
| 0x8009 | vehiclePosition broadcast | 이벤트(브로드캐스트) |
| 0x800A | currentTankVolume broadcast | door/heating 이벤트가 아님 |

---

## 6. Phase A 산출물(LLM 입력 스키마 / 출력 포맷)

### 6.1 LLM에 제공할 스키마(요약)

- service_id: 0xFF40
- methods:
  - 0x0008 doorsOpeningStatus_get
  - 0x000E changeDoorsState
  - 0x0009 seatHeatingStatus_get
  - 0x000A seatHeatingStatus_set
  - 0x000B seatHeatingLevel_get
  - 0x000C seatHeatingLevel_set

### 6.2 LLM이 생성할 테스트케이스(JSON) 예시

```json
{
  "testcase_id": "tc_0001",
  "service_id_hex": "0xFF40",
  "sequence": [
    {"method_id_hex": "0x000E", "params": {"door_cmd": ["OPEN","CLOSE","CLOSE","OPEN"]}},
    {"method_id_hex": "0x000A", "params": {"heating_status": [1,0,1,0,1,0,1]}},
    {"method_id_hex": "0x000C", "params": {"heating_level": [3,0,2,1,3,0,1]}}
  ],
  "timing": {"inter_call_delay_ms": [0,5,10,50]},
  "mutation_tags": ["boundary","repeat","reorder"]
}
