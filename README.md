# 하자 처리 관리 대시보드

데이터과학과 의사결정 텀프로젝트. 중간고사 7-2에서 1순위로 나온 '하자 앱 고도화'를 CS 직원용 하자 처리 관리 화면으로 먼저 구현해 본 시제품이다.

## 데이터
- `data/defects_anon.csv`: A사 한 아파트 현장 7개 동의 하자 작업지시서 22,618건(2022-06~2026-11)을 가림 처리한 원자료.
- `data/agg_*.csv`: `src/analysis.py`가 만든 집계표.

가림 처리(`src/prepare.py`): 호수·접수자 이름·접수번호·메모 원문을 지웠다. 메모에서는 맨 앞의 "(요청일-완료일)" 날짜와 '2년차', '중복', '(직)' 표시만 뽑았다. 협력업체명은 건수 순 코드(P01~)로, 회사 직영은 'A사직영'으로 바꿨다. 세대는 비밀값을 섞은 해시(unit_id)로만 남겼다. 원본 파일과 비밀값은 공개하지 않는다.

## 변수
| 열 | 뜻 |
|---|---|
| dong, size, occupied | 동, 평형, 입주 여부 |
| unit_id | 세대 가명 ID |
| place, trade, sub_trade, defect_type, cause | 장소, 공종, 세부공종, 하자유형, 하자원인 |
| partner | 처리 협력업체 코드 |
| sys_open, sys_close | 시스템 접수일·처리일 |
| memo_req, memo_done | 메모에 적힌 고객 요청일·완료일 |
| flag_2nd_year, flag_dup, flag_direct | 메모의 '2년차', '중복', '(직)' 표시 |

처리 기간 = memo_done − memo_req. 0~730일 밖의 값은 기록 오류로 보고 기간 분석에서 뺐다.

## 재현
```
pip install -r requirements.txt
python src/analysis.py      # 집계표 다시 만들기
streamlit run app.py        # 대시보드
```
시나리오 탭의 몬테카를로 시뮬레이션은 난수 시드 42로 고정했다.
