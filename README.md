# K-ETF Trend Rotation Agent

## 프로젝트 소개

K-ETF Trend Rotation Agent는 국내 상장 KOSPI·NASDAQ ETF의 기술적 지표를 분석하여 매수/매도 시그널을 콘솔에 출력하는 자동화 도구입니다. 본 프로그램은 투자 의사결정을 보조하기 위한 참고 도구이며, 투자 조언을 제공하지 않습니다.

## 요구사항

- Python 3.12
- Intel Mac macOS

## 설치 방법

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## 사용법

### 기본 실행

```bash
python main.py
```

시그널 결과만 출력합니다.

### 지표 상세

```bash
python main.py --detail
```

시그널 결과와 함께 일봉·주봉 지표 테이블을 출력합니다.

### 디버그

```bash
python main.py --verbose
```

시그널 결과와 함께 데이터 수신 상태 및 억제된 시그널의 상세 내역을 출력합니다.

옵션은 함께 사용할 수 있습니다.

```bash
python main.py --detail --verbose
```

## 포지션 상태 관리 (state.json)

현재 보유 중인 ETF 포지션은 `config/state.json`을 직접 편집하여 반영해야 합니다. 프로그램이 자동으로 포지션을 변경하지 않으므로, 실제 거래 후 수동으로 업데이트하십시오.

```json
{
  "KODEX200": false,
  "KODEX_LEVERAGE": false,
  "KODEX_INVERSE": false,
  "KODEX_INVERSE_2X": false,
  "KODEX_NASDAQ100": false,
  "KODEX_NASDAQ100_LEVERAGE": false,
  "KODEX_NASDAQ100_INVERSE": false
}
```

| 키 | 해당 ETF |
|----|----------|
| `KODEX200` | KODEX 200 |
| `KODEX_LEVERAGE` | KODEX 레버리지 |
| `KODEX_INVERSE` | KODEX 인버스 |
| `KODEX_INVERSE_2X` | KODEX 200선물인버스2X |
| `KODEX_NASDAQ100` | KODEX 미국나스닥100 |
| `KODEX_NASDAQ100_LEVERAGE` | KODEX 미국나스닥100레버리지(합성 H) |
| `KODEX_NASDAQ100_INVERSE` | KODEX 미국나스닥100선물인버스(H) |

`true`는 현재 보유 중, `false`는 미보유를 의미합니다.

동일 시장 내에서 강세 ETF와 인버스 ETF를 동시에 `true`로 설정하면 충돌 경고가 표시됩니다.

## 전략 요약

- 일치모쿠 구름(9, 26, 52) + 60일 이동평균 + ADX를 조합하여 추세 강도와 방향을 판단합니다.
- 일봉 조건은 BUY/SELL 시그널 생성에 사용하고, 주봉 조건은 1x ETF에서 2x ETF로 전환하는 UPGRADE 시그널 생성에 사용합니다.
- KOSPI 인버스 시그널은 KODEX 인버스 자체 지표를 기준으로 판단합니다.
- NASDAQ 인버스 시그널은 KODEX 미국나스닥100 지표의 반대 방향으로 판단합니다.
- 강세/인버스 시그널 충돌 시 ADX ≥ 25를 기준으로 우세한 방향을 채택하며, 판단 불가 시 STAY 시그널을 출력합니다.

## 감시 ETF 목록

| ETF명 | 역할 | 종목코드 |
|-------|------|----------|
| KODEX 200 | KOSPI 강세 1x | 069500 |
| KODEX 레버리지 | KOSPI 강세 2x | 122630 |
| KODEX 인버스 | KOSPI 인버스 1x | 114800 |
| KODEX 200선물인버스2X | KOSPI 인버스 2x | 252670 |
| KODEX 미국나스닥100 | NASDAQ 강세 1x | 379800 |
| KODEX 미국나스닥100레버리지(합성 H) | NASDAQ 강세 2x | 409820 |
| KODEX 미국나스닥100선물인버스(H) | NASDAQ 인버스 2x | 251340 |

## 시그널 종류

| 시그널 | 의미 | 색상 |
|--------|------|------|
| BUY | 매수 신호 | 초록 |
| SELL | 매도 신호 | 빨강 |
| STAY | 충돌 시 기존 포지션 유지 | 노랑 |
| UPGRADE | 1x ETF → 2x ETF 전환 | 청록 |
| None | 시그널 없음 | - |

## 주의사항

- 본 프로그램은 투자 조언이 아니며, 어떠한 수익도 보장하지 않습니다.
- 수동 매매 보조 도구로만 활용하며, 자동 주문 기능은 제공하지 않습니다.
- 모든 투자 결정과 그에 따른 결과는 전적으로 사용자 본인의 책임입니다.
- 데이터 정확성은 pykrx(KRX 공개 API)에 의존하며, 데이터 오류나 지연이 발생할 수 있습니다.
