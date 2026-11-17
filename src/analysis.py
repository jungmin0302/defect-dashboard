"""가림 처리한 데이터로 집계표를 만든다. 실행: python src/analysis.py"""
import numpy as np, pandas as pd

d = pd.read_csv('data/defects_anon.csv', parse_dates=['sys_open', 'sys_close', 'memo_req', 'memo_done'])
d['lead'] = (d['memo_done'] - d['memo_req']).dt.days          # 메모 기준 실제 처리 기간
d['sys_lead'] = (d['sys_close'] - d['sys_open']).dt.days      # 시스템 기준 처리 기간
d['entry_lag'] = (d['sys_open'] - d['memo_req']).dt.days      # 요청일 대비 시스템 입력 지연
d['valid'] = d['lead'].between(0, 730)                        # 음수·2년 초과는 기록 오류로 제외

def q(s, p): return s.quantile(p) if len(s) else np.nan
def lead_table(g):
    s = g.loc[g['valid'], 'lead']
    return pd.Series({'접수건수': len(g), '기간확인건수': len(s), '중앙값': q(s, .5), '상위25%': q(s, .75),
                      '상위10%': q(s, .9), '14일초과비율': (s > 14).mean() if len(s) else np.nan,
                      '30일초과비율': (s > 30).mean() if len(s) else np.nan,
                      '14일초과누적일수': (s - 14).clip(lower=0).sum()})

d.groupby('trade').size().sort_values(ascending=False).rename('건수').to_csv('data/agg_trade_count.csv')
d.groupby('defect_type').size().sort_values(ascending=False).rename('건수').to_csv('data/agg_defect_type.csv')
d.groupby('trade').apply(lead_table).sort_values('접수건수', ascending=False).to_csv('data/agg_lead_by_trade.csv')
d.groupby('partner').apply(lead_table).sort_values('접수건수', ascending=False).to_csv('data/agg_lead_by_partner.csv')
d.groupby('flag_direct').apply(lead_table).to_csv('data/agg_lead_by_direct.csv')
d.groupby('flag_2nd_year').apply(lead_table).to_csv('data/agg_lead_by_2nd_year.csv')
d.assign(month=d['memo_req'].dt.to_period('M')).groupby('month').apply(lead_table).to_csv('data/agg_lead_by_month.csv')

# 시스템 날짜와 메모 날짜 비교
cmp = pd.Series({
    '시스템_처리기간_0일비율': (d['sys_lead'] == 0).mean(),
    '시스템_처리기간_중앙값': d['sys_lead'].median(),
    '메모_처리기간_중앙값': d.loc[d['valid'], 'lead'].median(),
    '메모_처리기간_평균': d.loc[d['valid'], 'lead'].mean(),
    '시스템입력_지연_중앙값': d['entry_lag'].median(),
    '메모날짜_있는비율': d['memo_req'].notna().mean(),
    '기간확인_가능비율': d['valid'].mean(),
})
cmp.rename('값').to_csv('data/agg_system_vs_memo.csv')

# 같은 세대·같은 공종 재접수(30일 이상 간격)
r = d.dropna(subset=['memo_req']).sort_values('memo_req')
r['gap'] = r.groupby(['unit_id', 'trade'])['memo_req'].diff().dt.days
rep = r.groupby('trade').agg(접수건수=('gap', 'size'), 재접수건수=('gap', lambda s: (s >= 30).sum()))
rep['재접수비율'] = rep['재접수건수'] / rep['접수건수']
rep.sort_values('접수건수', ascending=False).to_csv('data/agg_repeat_by_trade.csv')

print(cmp.round(3).to_string())
