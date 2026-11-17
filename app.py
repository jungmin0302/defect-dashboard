"""하자 처리 관리 대시보드(CS 직원용 시제품).

데이터: A사 한 현장 7개 동 작업지시서(2022~2026, 22,618건)를 가림 처리한 것.
실행: streamlit run app.py
"""
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

st.set_page_config(page_title='하자 처리 관리 대시보드', layout='wide')

MAX_LEAD = 730  # 음수와 2년 초과는 기록 오류로 보고 기간 분석에서 뺀다


@st.cache_data
def load():
    d = pd.read_csv('data/defects_anon.csv', parse_dates=['sys_open', 'sys_close', 'memo_req', 'memo_done'])
    d['lead'] = (d['memo_done'] - d['memo_req']).dt.days
    d['sys_lead'] = (d['sys_close'] - d['sys_open']).dt.days
    d['entry_lag'] = (d['sys_open'] - d['memo_req']).dt.days
    d['valid'] = d['lead'].between(0, MAX_LEAD)
    d['handler'] = np.where(d['flag_direct'], '직영 방문 표시', '협력사 처리')
    d['round'] = np.where(d['flag_2nd_year'], '2년차 점검', '일반 접수')
    d['size'] = d['size'].fillna('공용부')
    return d


d0 = load()

# ---------- 사이드바 필터 ----------
st.sidebar.header('필터')
dongs = st.sidebar.multiselect('동', sorted(d0['dong'].unique()), default=sorted(d0['dong'].unique()))
trades_all = d0['trade'].value_counts().index.tolist()
trades = st.sidebar.multiselect('공종(비우면 전체)', trades_all)
rounds = st.sidebar.multiselect('접수 구분', ['일반 접수', '2년차 점검'], default=['일반 접수', '2년차 점검'])
d = d0[d0['dong'].isin(dongs) & d0['round'].isin(rounds)]
if trades:
    d = d[d['trade'].isin(trades)]
v = d[d['valid']]
st.sidebar.caption(f'선택된 접수 {len(d):,}건, 처리 기간 확인 {len(v):,}건')

st.title('하자 처리 관리 대시보드')
st.caption('A사 한 현장 7개 동의 하자 작업지시서를 가림 처리해 만든 CS 직원용 시제품입니다. '
           '처리 기간은 작업지시서 메모의 요청일~완료일로 계산했습니다.')

k = st.columns(4)
k[0].metric('접수 건수', f'{len(d):,}')
k[1].metric('처리 기간 중앙값', f'{v["lead"].median():.0f}일' if len(v) else '-')
k[2].metric('14일 초과 비율', f'{(v["lead"] > 14).mean():.1%}' if len(v) else '-')
k[3].metric('30일 초과 비율', f'{(v["lead"] > 30).mean():.1%}' if len(v) else '-')

tabs = st.tabs(['① 하자 집중', '② 처리 기간', '③ 기록 품질', '④ 개선 시나리오', '⑤ 7-2 연계'])

# ---------- ① 하자 집중 ----------
with tabs[0]:
    st.subheader('어느 공종에 하자가 몰리는가')
    tc = d['trade'].value_counts().reset_index()
    tc.columns = ['공종', '건수']
    tc['누적비율'] = tc['건수'].cumsum() / tc['건수'].sum()
    top = tc.head(15)
    fig = go.Figure()
    fig.add_bar(x=top['공종'], y=top['건수'], name='건수')
    fig.add_scatter(x=top['공종'], y=top['누적비율'], yaxis='y2', name='누적비율', mode='lines+markers')
    fig.update_layout(yaxis2=dict(overlaying='y', side='right', tickformat='.0%', range=[0, 1]), height=460,
                      legend=dict(orientation='h', y=1.1), margin=dict(b=120))
    st.plotly_chart(fig, use_container_width=True)
    n80 = int((tc['누적비율'] < 0.8).sum()) + 1
    st.write(f'전체 {len(tc)}개 공종 중 상위 {n80}개 공종이 접수의 80%를 차지합니다.')
    c1, c2 = st.columns(2)
    dt = d['defect_type'].value_counts().head(12).reset_index()
    dt.columns = ['하자유형', '건수']
    c1.plotly_chart(px.bar(dt, x='건수', y='하자유형', orientation='h', title='하자유형 상위 12').update_yaxes(autorange='reversed'),
                    use_container_width=True)
    # 같은 세대·같은 공종이 30일 이상 간격으로 다시 들어온 건을 재접수로 본다
    r = d.dropna(subset=['memo_req']).sort_values('memo_req')
    r = r.assign(gap=r.groupby(['unit_id', 'trade'])['memo_req'].diff().dt.days)
    rp = r.groupby('trade').agg(접수=('gap', 'size'), 재접수=('gap', lambda s: (s >= 30).sum()))
    rp = rp[rp['접수'] >= 100]
    rp['재접수율'] = rp['재접수'] / rp['접수']
    rp = rp.sort_values('재접수율', ascending=False).head(12).reset_index().rename(columns={'trade': '공종'})
    pl = d['place'].value_counts().head(12).reset_index()
    pl.columns = ['장소', '건수']
    c2.plotly_chart(px.bar(pl, x='건수', y='장소', orientation='h', title='장소 상위 12').update_yaxes(autorange='reversed'),
                    use_container_width=True)
    st.plotly_chart(px.bar(rp, x='공종', y='재접수율', hover_data=['접수', '재접수'],
                           title='공종별 재접수율(같은 세대·같은 공종이 30일 이상 지나 다시 접수, 100건 이상 공종)')
                    .update_yaxes(tickformat='.0%'), use_container_width=True)
    st.caption('메모의 "중복" 표시는 전체의 67%에 붙어 있어 재접수 지표로 쓰지 않았습니다.')

# ---------- ② 처리 기간 ----------
with tabs[1]:
    st.subheader('얼마나 오래 걸리고, 어디서 길어지는가')
    if len(v) == 0:
        st.info('선택 조건에 처리 기간을 확인할 수 있는 건이 없습니다.')
    else:
        h = v.assign(구간=pd.cut(v['lead'], [-1, 0, 3, 7, 14, 30, 60, 120, MAX_LEAD],
                                labels=['당일', '1~3일', '4~7일', '8~14일', '15~30일', '31~60일', '61~120일', '121일+']))
        hc = h['구간'].value_counts(sort=False).reset_index()
        hc.columns = ['처리 기간', '건수']
        st.plotly_chart(px.bar(hc, x='처리 기간', y='건수', title='처리 기간 분포'), use_container_width=True)

        g = v.groupby('trade')['lead']
        tb = pd.DataFrame({'건수': g.size(), '중앙값': g.median(), '상위10%': g.quantile(.9),
                           '14일 초과 비율': g.apply(lambda s: (s > 14).mean()),
                           '14일 초과 누적일수': g.apply(lambda s: (s - 14).clip(lower=0).sum())})
        tb = tb[tb['건수'] >= 30].sort_values('14일 초과 누적일수', ascending=False).rename_axis('공종')
        tb['누적일수 비중'] = tb['14일 초과 누적일수'] / tb['14일 초과 누적일수'].sum()
        st.markdown('**공종별 지연 부담**(30건 이상 공종). 14일을 넘긴 일수를 모두 더한 값이 클수록 개선 효과가 큰 공종입니다.')
        st.dataframe(tb.style.format({'중앙값': '{:.0f}', '상위10%': '{:.0f}', '14일 초과 비율': '{:.1%}',
                                      '14일 초과 누적일수': '{:,.0f}', '누적일수 비중': '{:.1%}'}),
                     use_container_width=True)
        c1, c2 = st.columns(2)
        for col, key, title in [(c1, 'round', '접수 구분별'), (c2, 'handler', '처리 방식별(메모 표시 기준)')]:
            s = v.groupby(key)['lead'].agg(['size', 'median', lambda x: (x > 14).mean()])
            s.columns = ['건수', '중앙값', '14일 초과 비율']
            col.markdown(f'**{title}**')
            col.dataframe(s.style.format({'중앙값': '{:.0f}일', '14일 초과 비율': '{:.1%}'}), use_container_width=True)
        st.caption('처리 방식은 메모의 "(직)" 표시로 나눴습니다. 직영 처리 건은 간단한 보수가 많아 공종 구성이 다르므로, '
                   '두 집단의 차이를 처리 방식만의 효과로 볼 수는 없습니다.')
        m = v.assign(월=v['memo_req'].dt.to_period('M').dt.to_timestamp()).groupby('월')['lead']
        mt = pd.DataFrame({'접수': m.size(), '중앙값': m.median()}).reset_index()
        mt = mt[mt['월'] >= '2024-01-01']
        fig = go.Figure()
        fig.add_bar(x=mt['월'], y=mt['접수'], name='요청 건수')
        fig.add_scatter(x=mt['월'], y=mt['중앙값'], yaxis='y2', name='처리 기간 중앙값(일)', mode='lines+markers')
        fig.update_layout(title='요청 월별 건수와 처리 기간', yaxis2=dict(overlaying='y', side='right'), legend=dict(orientation='h', y=1.12))
        st.plotly_chart(fig, use_container_width=True)

# ---------- ③ 기록 품질 ----------
with tabs[2]:
    st.subheader('시스템 날짜는 실제 처리 과정을 보여 주는가')
    both = d[d['valid'] & d['sys_lead'].notna()]
    c1, c2, c3 = st.columns(3)
    c1.metric('시스템 처리 기간 0일 비율', f'{(d["sys_lead"] == 0).mean():.1%}')
    c2.metric('메모 기준 처리 기간 중앙값', f'{v["lead"].median():.0f}일' if len(v) else '-')
    c3.metric('요청일 대비 시스템 입력 지연(중앙값)', f'{d["entry_lag"].median():.0f}일')
    cmp = pd.DataFrame({'기준': ['시스템 날짜'] * len(both) + ['메모 날짜'] * len(both),
                        '처리 기간': pd.concat([both['sys_lead'], both['lead']]).clip(upper=120)})
    st.plotly_chart(px.histogram(cmp, x='처리 기간', color='기준', barmode='overlay', nbins=60,
                                 title='같은 건의 처리 기간: 시스템 날짜 vs 메모 날짜(120일 이상은 120으로 표시)'),
                    use_container_width=True)
    st.write('시스템의 접수일은 고객 요청일보다 늦게, 처리일은 접수일과 같은 날로 입력된 건이 대부분입니다. '
             '처리가 끝난 뒤 기록하는 방식이어서, 지금 시스템 날짜만으로는 처리 지연을 관리할 수 없습니다. '
             '요청·배정·방문·완료 단계를 그때그때 기록하는 기능이 먼저 필요합니다.')

# ---------- ④ 개선 시나리오 ----------
with tabs[3]:
    st.subheader('처리 목표일을 두면 지연이 얼마나 줄어드는가(가정 시뮬레이션)')
    st.caption('실제 처리 기간 분포에서, 목표일을 넘긴 건 중 일부가 목표일 안에 끝난다고 가정해 다시 계산합니다. '
               '측정된 효과가 아니라 가정에 따른 추정입니다.')
    c1, c2, c3 = st.columns(3)
    target = c1.slider('처리 목표일(일)', 3, 60, 14)
    comply = c2.slider('목표일 초과 건 중 목표 안에 끝나는 비율', 0.0, 1.0, 0.5, 0.05)
    scope = c3.multiselect('적용 공종(비우면 전체)', trades_all[:20])
    n_sim = 500
    base = v['lead'].to_numpy()
    in_scope = v['trade'].isin(scope).to_numpy() if scope else np.ones(len(v), bool)
    over = (base > target) & in_scope
    rng = np.random.default_rng(42)
    res = []
    for _ in range(n_sim):
        hit = over & (rng.random(len(base)) < comply)
        new = np.where(hit, rng.integers(max(target - 3, 0), target + 1, len(base)), base)
        res.append([np.mean(new), np.median(new), np.mean(new > 14), np.mean(new > 30), np.clip(new - 14, 0, None).sum()])
    res = np.array(res)
    before = [base.mean(), np.median(base), np.mean(base > 14), np.mean(base > 30), np.clip(base - 14, 0, None).sum()]
    names = ['평균 처리 기간(일)', '중앙값(일)', '14일 초과 비율', '30일 초과 비율', '14일 초과 누적일수']
    out = pd.DataFrame({'지표': names, '현재': before, '시나리오 평균': res.mean(0),
                        '95% 구간 하한': np.percentile(res, 2.5, 0), '95% 구간 상한': np.percentile(res, 97.5, 0)})
    shown = out.copy()
    for c in shown.columns[1:]:
        shown[c] = [f'{x:.1%}' if '비율' in n else f'{x:,.1f}' for x, n in zip(out[c], out['지표'])]
    st.dataframe(shown, use_container_width=True, hide_index=True)
    st.write(f'목표일을 넘긴 건은 현재 {over.sum():,}건입니다. 시뮬레이션 {n_sim}회, 난수 시드 42로 고정했습니다.')
    # 민감도: 목표일과 준수율 격자
    grid_t, grid_c = [7, 14, 21, 30], [0.25, 0.5, 0.75, 1.0]
    sens = pd.DataFrame(index=[f'{t}일' for t in grid_t], columns=[f'{c:.0%}' for c in grid_c], dtype=float)
    for t in grid_t:
        o = (base > t) & in_scope
        for c in grid_c:
            sens.loc[f'{t}일', f'{c:.0%}'] = np.mean(np.where(o, np.minimum(base, t) * c + base * (1 - c), base))
    st.markdown('**민감도: 목표일 × 준수율별 평균 처리 기간(기댓값, 일)**')
    st.dataframe(sens.style.format('{:.1f}').background_gradient(cmap='Greens_r', axis=None), use_container_width=True)

# ---------- ⑤ 7-2 연계 ----------
with tabs[4]:
    st.subheader('왜 처리 관리 기능부터인가: 7-2 다기준 분석')
    st.caption('중간고사 7-2에서 연구자가 정한 기준·점수(1~5점)입니다. 가중치를 바꾸면 순위가 어떻게 달라지는지 볼 수 있습니다.')
    crit = ['C1 고객 문제 적합도', 'C2 효과 근거 강도', 'C3 2년 내 실행 준비도', 'C4 위험(역척도)', 'C5 기반 효과']
    scores = pd.DataFrame({'⓪ 현행 유지': [1, 1, 5, 4, 1], '① 하자 앱 고도화': [4, 4, 4, 2.5, 3],
                           '② 하자 DB·분석': [3, 2.5, 2, 3.5, 4], '③ 상담원 보조 AI': [2.5, 3, 2, 3, 2.5]}, index=crit)
    default = [30.3, 9.1, 21.2, 24.2, 15.2]
    cols = st.columns(5)
    w = np.array([cols[i].slider(c, 0.0, 50.0, default[i], 0.1) for i, c in enumerate(crit)])
    w = w / w.sum() if w.sum() > 0 else np.ones(5) / 5
    total = ((scores - 1) / 4).mul(w, axis=0).sum().sort_values(ascending=False)
    st.plotly_chart(px.bar(total.reset_index(), x='index', y=0, labels={'index': '대안', '0': '가중합(0~1)'},
                           title='가중합 점수'), use_container_width=True)
    st.write('기본 가중치(7-2 Max100)에서는 ① .621 > ② .504 > ⓪ .394 > ③ .390입니다. '
             '이 대시보드는 ①을 CS 직원용 처리 관리 화면으로 먼저 구현해 본 것이고, ③ 기록 품질 탭의 결과는 '
             '7-2에서 "단계별 운영 데이터가 없다"고 적은 한계를 실제 데이터로 확인한 것입니다.')
