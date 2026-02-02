# LLM-Generator-Fuzzer

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
| 0x000C | seatHeatingLev
