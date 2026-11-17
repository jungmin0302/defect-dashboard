"""원본 작업지시서(동별 xlsx 7개)를 가림 처리해 분석용 데이터로 만든다.

원본과 협력사 코드표는 공개하지 않는다(private/). 공개 데이터에는
호수·접수자·접수번호·메모 원문이 없고, 협력업체명은 코드로 바뀐다.
실행: python src/prepare.py <원본 xlsx 폴더>
"""
import os, sys, glob, hashlib, warnings
warnings.filterwarnings("ignore")
import numpy as np, pandas as pd

SRC = sys.argv[1] if len(sys.argv) > 1 else 'raw'
OUT = 'data/defects_anon.csv'
SELF = '롯데건설(주)'  # 회사 직영 처리 건

frames = [pd.read_excel(f) for f in sorted(glob.glob(f'{SRC}/*.xlsx'))]
df = pd.concat(frames, ignore_index=True)

# 1) 날짜: 시스템 날짜와 메모 맨 앞 "(요청일-완료일)"
df['sys_open'] = pd.to_datetime(df['접수일자'], errors='coerce')
df['sys_close'] = pd.to_datetime(df['처리일자'], errors='coerce')
memo = df['기타사유'].fillna('')
m = memo.str.extract(r'^\((\d{6})-(\d{6})?\)')
df['memo_req'] = pd.to_datetime(m[0], format='%y%m%d', errors='coerce')
df['memo_done'] = pd.to_datetime(m[1], format='%y%m%d', errors='coerce')

# 2) 메모에서 표시만 뽑고 원문은 버린다
df['flag_2nd_year'] = memo.str.contains('2년차')
df['flag_dup'] = memo.str.contains('중복')
df['flag_direct'] = memo.str.contains(r'\(직\)')

# 3) 가림: 협력업체 코드화(건수 많은 순), 세대 ID는 무작위 해시
vc = df.loc[df['업체명'] != SELF, '업체명'].value_counts()
code = {n: f'P{i+1:02d}' for i, n in enumerate(vc.index)}
code[SELF] = 'A사직영'
df['partner'] = df['업체명'].map(code)
pd.Series(code, name='code').rename_axis('업체명').to_csv('private/partner_codes.csv')

salt = os.environ['UNIT_SALT']  # 비밀값. 공개하면 세대 ID에서 호수를 역산할 수 있다
unit = (df['동'].astype(str) + '-' + df['호수'].astype('Int64').astype(str)).fillna(df['동'].astype(str) + '-공용')
df['unit_id'] = unit.map(lambda s: 'U' + hashlib.sha256((salt + s).encode()).hexdigest()[:8])

out = pd.DataFrame({
    'dong': df['동'], 'unit_id': df['unit_id'], 'size': df['평형'].astype(str).str.replace('.0', '', regex=False),
    'occupied': df['입주여부'].eq('입주'), 'status': df['처리상태'],
    'place': df['장소'], 'trade': df['공종'], 'sub_trade': df['세부공종'],
    'defect_type': df['하자유형'], 'cause': df['하자원인'], 'partner': df['partner'],
    'sys_open': df['sys_open'].dt.date, 'sys_close': df['sys_close'].dt.date,
    'memo_req': df['memo_req'].dt.date, 'memo_done': df['memo_done'].dt.date,
    'flag_2nd_year': df['flag_2nd_year'], 'flag_dup': df['flag_dup'], 'flag_direct': df['flag_direct'],
})
out.to_csv(OUT, index=False, encoding='utf-8-sig')
print(OUT, out.shape)
