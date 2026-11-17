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

MAX_LEAD = 730   # 음수와 2년 초과는 기록 오류로 보고 기간 분석에서 뺀다
TARGET = 14      # 기준 처리 목표일
BLUE, RED, GREY, INK, MUTED = '#3A6EA5', '#C0583F', '#C9CED2', '#1F2A30', '#6B7378'


@st.cache_data
def load():
    d = pd.read_csv('data/defects_anon.csv', parse_dates=['sys_open', 'sys_close', 'memo_req', 'memo_done'])
    d['lead'] = (d['memo_done'] - d['memo_req']).dt.days
    d['sys_lead'] = (d['sys_close'] - d['sys_open']).dt.days
    d['entry_lag'] = (d['sys_open'] - d['memo_req']).dt.days
    d['valid'] = d['lead'].between(0, MAX_LEAD)
    d['handler'] = np.where(d['flag_direct'], '직영 방문 표시', '협력사 처리')
    d['round'] = np.where(d['flag_2nd_year'], '2년차 점검', '일반 접수')
    return d


def style(fig, height=420):
    """모든 차트에 같은 축·글자·여백을 적용한다."""
    fig.update_layout(height=height, plot_bgcolor='white', paper_bgcolor='white', font=dict(color=INK, size=13),
                      margin=dict(l=10, r=30, t=40, b=10), bargap=0.45, showlegend=fig.layout.showlegend,
                      legend=dict(orientation='h', y=1.08, x=0, title=None))
    fig.update_xaxes(showgrid=False, linecolor=GREY, tickfont=dict(color=MUTED))
    fig.update_yaxes(gridcolor='#EEF0F1', zeroline=False, tickfont=dict(color=MUTED))
    fig.update_traces(selector=dict(type='bar'), marker_line_width=0, marker_cornerradius=4)
    return fig


def hbar(df, x, y, colors, fmt, height=None, hover=None):
    """가로 막대(긴 공종 이름용). 위에서부터 큰 순."""
    fig = go.Figure(go.Bar(x=df[x], y=df[y], orientation='h', marker_color=colors, text=df[x].map(fmt.format),
                           textposition='outside', textfont=dict(color=INK), cliponaxis=False,
                           customdata=df[hover] if hover else None,
                           hovertemplate=(f'%{{y}}<br>{x}: %{{x}}' + ('<br>' + '<br>'.join(f'{h}: %{{customdata[{i}]}}' for i, h in enumerate(hover)) if hover else '') + '<extra></extra>')))
    fig.update_yaxes(autorange='reversed', gridcolor='rgba(0,0,0,0)')
    fig.update_xaxes(visible=False)
    return style(fig, height or 34 * len(df) + 60)


def takeaway(text):
    st.markdown(f'<div style="background:#F3F5F6;border-radius:10px;padding:14px 18px;margin:4px 0 14px 0;'
                f'color:{INK};font-size:1.02rem"><b>이 화면의 결론</b><br>{text}</div>', unsafe_allow_html=True)


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
st.sidebar.caption(f'선택된 접수 {len(d):,}건 · 처리 기간 확인 {len(v):,}건')
st.sidebar.caption('처리 기간 = 작업지시서 메모의 고객 요청일부터 완료일까지')

if len(v) == 0:
    st.warning('선택한 조건에 처리 기간을 확인할 수 있는 건이 없습니다. 필터를 넓혀 주세요.')
    st.stop()

# 공종별 지연 부담(여러 탭에서 쓴다)
g = v.groupby('trade')['lead']
burden = pd.DataFrame({'건수': g.size(), '중앙값(일)': g.median(), f'{TARGET}일 초과 비율': g.apply(lambda s: (s > TARGET).mean()),
                       '초과 일수 합': g.apply(lambda s: (s - TARGET).clip(lower=0).sum())})
burden = burden[burden['건수'] >= 30].sort_values('초과 일수 합', ascending=False)
burden['지연 부담 비중'] = burden['초과 일수 합'] / burden['초과 일수 합'].sum()
top6 = burden.head(6)

# ---------- 머리말 ----------
st.title('하자 처리 관리 대시보드')
st.markdown('**이 대시보드가 답하는 질문:** CS 직원용 하자 처리 관리 화면에 무엇부터 넣어야 하는가? '
            'A사 한 현장의 하자 작업지시서 22,618건을 가림 처리해 분석했습니다.')
k = st.columns(4)
k[0].metric('접수 건수', f'{len(d):,}건')
k[1].metric('처리 기간 중앙값', f'{v["lead"].median():.0f}일')
k[2].metric(f'{TARGET}일 넘긴 비율', f'{(v["lead"] > TARGET).mean():.1%}')
k[3].metric('시스템상 처리 0일 비율', f'{(d["sys_lead"] == 0).mean():.1%}', help='시스템의 접수일과 처리일이 같은 날인 건. 처리 후 일괄 입력된 흔적입니다. 전체 접수 기준이며, 탭 3은 메모 날짜가 있는 건만 비교합니다.')

tabs = st.tabs(['요약', '1. 어디에 몰리나', '2. 얼마나 걸리나', '3. 왜 지금은 안 보이나', '4. 목표일을 두면', '5. 왜 이 기능부터(7-2)', '6. 처리 화면 시안'])

# ---------- 요약 ----------
with tabs[0]:
    st.subheader('세 가지 발견과 처리 관리 화면에 넣을 기능')
    c = st.columns(3)
    c[0].markdown(f'#### 처리는 대부분 빠르지만 꼬리가 길다\n중앙값은 {v["lead"].median():.0f}일이지만 '
                  f'{(v["lead"] > TARGET).mean():.0%}가 {TARGET}일을, {(v["lead"] > 30).mean():.0%}가 30일을 넘깁니다.')
    c[1].markdown(f'#### 지연은 몇 개 공종에 몰려 있다\n{TARGET}일을 넘긴 일수의 {top6["지연 부담 비중"].sum():.0%}가 '
                  f'{", ".join(top6.index[:3])} 등 6개 공종에서 나옵니다.')
    c[2].markdown(f'#### 시스템은 지연을 기록하지 못한다\n시스템상 처리 기간은 {(d["sys_lead"] == 0).mean():.0%}가 0일입니다. '
                  f'고객 요청일보다 중앙값 {d["entry_lag"].median():.0f}일 늦게, 처리 후에 입력됩니다.')
    st.markdown('---')
    st.markdown('#### 그래서 처리 관리 화면에는')
    a = st.columns(4)
    for col, (h, b) in zip(a, [('① 단계별 기록', '요청·배정·방문·완료를 그때그때 입력'),
                               ('② 목표일 초과 알림', f'공종별 목표일(예: {TARGET}일)을 넘기기 전에 담당자에게 알림'),
                               ('③ 지연 공종 집중 관리', '지연 부담 상위 6개 공종은 협력사와 목표일 합의'),
                               ('④ 2년차 점검 일정 관리', '여러 하자를 한 번에 방문하는 일정으로 묶기')]):
        col.markdown(f'<div style="border:1px solid {GREY};border-radius:10px;padding:12px 14px;height:120px">'
                     f'<b style="color:{RED}">{h}</b><br><span style="color:{INK}">{b}</span></div>', unsafe_allow_html=True)
    st.caption('각 발견의 근거는 위 탭 1–3에, 목표일 효과 추정은 탭 4에, 이 기능을 먼저 만드는 이유는 탭 5(중간고사 7-2 분석)에, 이 기능을 넣은 화면 시안은 탭 6에 있습니다.')

# ---------- 1. 어디에 몰리나 ----------
with tabs[1]:
    tc = d['trade'].value_counts().rename_axis('공종').reset_index(name='건수')
    n80 = int((tc['건수'].cumsum() / tc['건수'].sum() < 0.8).sum()) + 1
    top3 = '·'.join(tc['공종'].head(3))  # 공종 필터로 1~2개만 고르면 3개보다 적다
    takeaway(f'접수는 {top3} 순으로 많고, '
             f'전체 {len(tc)}개 공종 중 상위 {n80}개가 접수의 80%를 차지합니다. '
             '빨간 막대는 지연 부담 상위 6개 공종(탭 2)으로, 건수가 많은 공종과 대부분 겹칩니다.')
    t15 = tc.head(15)
    cols = [RED if t in top6.index else BLUE for t in t15['공종']]
    st.markdown('**공종별 접수 건수(상위 15)**')
    st.plotly_chart(hbar(t15, '건수', '공종', cols, '{:,}'), width='stretch')
    c1, c2 = st.columns(2)
    dt = d['defect_type'].value_counts().head(10).rename_axis('하자유형').reset_index(name='건수')
    c1.markdown('**하자유형 상위 10**')
    c1.plotly_chart(hbar(dt, '건수', '하자유형', BLUE, '{:,}'), width='stretch')
    r = d.dropna(subset=['memo_req']).sort_values('memo_req')
    r = r.assign(gap=r.groupby(['unit_id', 'trade'])['memo_req'].diff().dt.days)
    rp = r.groupby('trade').agg(접수=('gap', 'size'), 재접수=('gap', lambda s: (s >= 30).sum()))
    rp = rp[(rp['접수'] >= 100) & ~rp.index.str.contains('미사용')]
    rp['재접수율'] = rp['재접수'] / rp['접수']
    rp = rp.sort_values('재접수율', ascending=False).head(10).rename_axis('공종').reset_index()
    c2.markdown('**재접수율 상위 10**(같은 세대·공종이 30일 이상 지나 다시 접수, 100건 이상 공종)')
    c2.plotly_chart(hbar(rp, '재접수율', '공종', BLUE, '{:.1%}', hover=['접수', '재접수']), width='stretch')
    st.caption('메모의 "중복" 표시는 전체의 67%에 붙어 있어 재접수 지표로 쓰지 않았습니다.')

# ---------- 2. 얼마나 걸리나 ----------
with tabs[2]:
    takeaway(f'절반은 {v["lead"].median():.0f}일 안에 끝나지만 {(v["lead"] > TARGET).mean():.0%}는 {TARGET}일을 넘깁니다. '
             f'넘긴 일수를 모두 더하면 {", ".join(top6.index[:3])} 등 6개 공종이 {top6["지연 부담 비중"].sum():.0%}를 차지해, '
             '이 공종들의 처리 목표일 관리가 가장 효과가 큽니다.')
    labels = ['당일', '1~3일', '4~7일', '8~14일', '15~30일', '31~60일', '61~120일', '121일 이상']
    hb = pd.cut(v['lead'], [-1, 0, 3, 7, 14, 30, 60, 120, MAX_LEAD], labels=labels).value_counts(sort=False)
    fig = go.Figure(go.Bar(x=labels, y=hb.values, marker_color=[BLUE] * 4 + [RED] * 4,
                           text=[f'{x:,}' for x in hb.values], textposition='outside', cliponaxis=False,
                           hovertemplate='%{x}: %{y:,}건<extra></extra>'))
    fig.update_yaxes(visible=False)
    st.markdown(f'**처리 기간 분포**(빨강 = {TARGET}일 초과)')
    st.plotly_chart(style(fig, 360), width='stretch')
    c1, c2 = st.columns([3, 2])
    bt = burden.head(10).rename_axis('공종').reset_index()
    c1.markdown(f'**공종별 지연 부담**({TARGET}일을 넘긴 일수의 합에서 차지하는 비중, 30건 이상 공종)')
    c1.plotly_chart(hbar(bt, '지연 부담 비중', '공종', [RED] * 6 + [GREY] * 4, '{:.1%}', hover=['건수', '중앙값(일)']),
                    width='stretch')
    c2.markdown('**어떤 건이 오래 걸리나**')
    for key, title in [('round', '접수 구분'), ('handler', '처리 방식(메모 표시)')]:
        s = v.groupby(key)['lead'].agg(건수='size', 중앙값='median', 초과=lambda x: (x > TARGET).mean())
        s.columns = ['건수', '중앙값(일)', f'{TARGET}일 초과']
        s.index.name = title.split('(')[0]
        c2.markdown(f'*{title}*')
        c2.dataframe(s.style.format({'건수': '{:,}', '중앙값(일)': '{:.0f}', f'{TARGET}일 초과': '{:.1%}'}), width='stretch')
    c2.caption('2년차 점검은 여러 하자가 한 번에 들어와 일정 조율이 필요합니다. 직영 처리 건은 간단한 보수가 많아 '
               '공종 구성이 다르므로, 처리 방식만의 효과로 볼 수는 없습니다.')
    with st.expander('공종별 상세 표'):
        st.dataframe(burden.rename_axis('공종').style.format({'건수': '{:,}', '중앙값(일)': '{:.0f}', f'{TARGET}일 초과 비율': '{:.1%}',
                                                            '초과 일수 합': '{:,.0f}', '지연 부담 비중': '{:.1%}'}), width='stretch')

# ---------- 3. 왜 지금은 안 보이나 ----------
with tabs[3]:
    both = d[d['valid'] & d['sys_lead'].notna()]
    takeaway(f'같은 건을 두 날짜로 재면 결과가 전혀 다릅니다. 시스템 날짜로는 {(both["sys_lead"] <= 0).mean():.0%}가 "당일 처리"지만, '
             f'메모의 실제 요청일·완료일로는 당일 처리가 {(both["lead"] == 0).mean():.0%}뿐입니다. '
             '처리를 마친 뒤 입력하는 지금 방식으로는 진행 중인 지연을 볼 수 없어, 단계별 기록이 첫 번째 기능이어야 합니다.')
    labels = ['당일', '1~7일', '8~14일', '15~30일', '31일 이상']
    cut = lambda s: pd.cut(s, [-1, 0, 7, 14, 30, 10_000], labels=labels).value_counts(sort=False, normalize=True)
    fig = go.Figure()
    fig.add_bar(name='시스템 날짜', x=labels, y=cut(both['sys_lead'].clip(lower=0)).values, marker_color=GREY,
                text=[f'{x:.0%}' for x in cut(both['sys_lead'].clip(lower=0)).values], textposition='outside')
    fig.add_bar(name='메모의 실제 날짜', x=labels, y=cut(both['lead']).values, marker_color=BLUE,
                text=[f'{x:.0%}' for x in cut(both['lead']).values], textposition='outside')
    fig.update_layout(barmode='group', bargroupgap=0.12, showlegend=True)
    fig.update_yaxes(visible=False)
    fig.update_traces(cliponaxis=False, hovertemplate='%{x}: %{y:.1%}<extra></extra>')
    st.markdown(f'**같은 {len(both):,}건의 처리 기간 분포: 시스템 날짜 vs 메모의 실제 날짜**')
    st.plotly_chart(style(fig, 380), width='stretch')
    c = st.columns(3)
    c[0].metric('시스템 입력이 요청보다 늦은 기간(중앙값)', f'{d["entry_lag"].median():.0f}일')
    c[1].metric('메모에 요청·완료일이 모두 있는 비율', f'{d["valid"].mean():.0%}')
    c[2].metric('기간 계산에서 뺀 기록 오류', f'{(d["lead"].notna() & ~d["valid"]).sum():,}건')

# ---------- 4. 목표일을 두면 ----------
with tabs[4]:
    c1, c2, c3 = st.columns(3)
    target = c1.slider('처리 목표일(일)', 3, 60, TARGET)
    comply = c2.slider('목표일을 넘길 건 중 목표 안에 끝내는 비율', 0.0, 1.0, 0.5, 0.05)
    scope = c3.multiselect('적용 공종(비우면 전체)', burden.index.tolist(), help='지연 부담 상위 공종만 골라 효과를 비교해 보세요.')
    base = v['lead'].to_numpy()
    in_scope = v['trade'].isin(scope).to_numpy() if scope else np.ones(len(v), bool)
    over = (base > target) & in_scope
    rng = np.random.default_rng(42)
    n_sim = 500
    res = []
    for _ in range(n_sim):
        hit = over & (rng.random(len(base)) < comply)
        new = np.where(hit, rng.integers(max(target - 3, 0), target + 1, len(base)), base)
        res.append([new.mean(), np.mean(new > 30), np.clip(new - TARGET, 0, None).sum()])
    res = np.array(res)
    before = [base.mean(), np.mean(base > 30), np.clip(base - TARGET, 0, None).sum()]
    takeaway(f'목표일 {target}일, 준수율 {comply:.0%}를 가정하면 평균 처리 기간이 {before[0]:.1f}일에서 '
             f'{res[:, 0].mean():.1f}일로, 30일을 넘기는 건이 {before[1]:.1%}에서 {res[:, 1].mean():.1%}로 줄어듭니다. '
             '목표일을 짧게 잡는 것보다 실제로 지키는 비율이 결과를 더 크게 바꿉니다(아래 민감도 표). '
             '측정한 효과가 아니라 실제 분포에 가정을 얹은 추정입니다.')
    c = st.columns(3)
    c[0].metric('평균 처리 기간', f'{res[:, 0].mean():.1f}일', f'{res[:, 0].mean() - before[0]:+.1f}일', delta_color='inverse')
    c[1].metric('30일 초과 비율', f'{res[:, 1].mean():.1%}', f'{(res[:, 1].mean() - before[1]) * 100:+.1f}%p', delta_color='inverse')
    c[2].metric(f'{TARGET}일 초과 일수 합', f'{res[:, 2].mean():,.0f}일', f'{res[:, 2].mean() / before[2] - 1:+.0%}', delta_color='inverse')
    st.caption(f'목표일을 넘긴 건 {over.sum():,}건 중 준수율만큼을 무작위로 골라 목표일 직전(목표일 3일 전부터 목표일 사이)에 끝난 것으로 바꿉니다. '
               f'{n_sim}회 반복 평균, 95% 구간 평균 처리 기간 {np.percentile(res[:, 0], 2.5):.1f}–{np.percentile(res[:, 0], 97.5):.1f}일. 난수 시드 42.')
    grid_t, grid_c = [7, 14, 21, 30], [0.25, 0.5, 0.75, 1.0]
    sens = pd.DataFrame(index=[f'목표 {t}일' for t in grid_t], columns=[f'준수 {c:.0%}' for c in grid_c], dtype=float)
    for t in grid_t:
        o = (base > t) & in_scope
        for cc in grid_c:
            sens.loc[f'목표 {t}일', f'준수 {cc:.0%}'] = np.mean(np.where(o, np.minimum(base, t) * cc + base * (1 - cc), base))
    st.markdown(f'**민감도: 목표일 × 준수율별 평균 처리 기간(일, 현재 {before[0]:.1f}일)**')
    st.dataframe(sens.style.format('{:.1f}').background_gradient(cmap='Blues_r', axis=None), width='stretch')

# ---------- 5. 왜 이 기능부터(7-2) ----------
with tabs[5]:
    takeaway('중간고사 7-2의 다기준 분석에서 하자 앱 고도화가 1순위였습니다. 다만 그때는 처리 단계별 운영 데이터가 없어 '
             '목표일과 우선 공종을 정하지 못했습니다. 이 대시보드가 그 빈칸을 실제 데이터로 채웁니다. '
             '아래 가중치를 바꿔 보면 어떤 조건에서 순위가 바뀌는지 확인할 수 있습니다.')
    crit = ['C1 고객 문제 적합도', 'C2 효과 근거 강도', 'C3 2년 내 실행 준비도', 'C4 위험(역척도)', 'C5 기반 효과']
    scores = pd.DataFrame({'⓪ 현행 유지': [1, 1, 5, 4, 1], '① 하자 앱 고도화': [4, 4, 4, 2.5, 3],
                           '② 하자 DB·분석': [3, 2.5, 2, 3.5, 4], '③ 상담원 보조 AI': [2.5, 3, 2, 3, 2.5]}, index=crit)
    default = [30.3, 9.1, 21.2, 24.2, 15.2]
    cols = st.columns(5)
    w = np.array([cols[i].slider(cname, 0.0, 50.0, default[i], 0.1) for i, cname in enumerate(crit)])
    w = w / w.sum() if w.sum() > 0 else np.ones(5) / 5
    total = ((scores - 1) / 4).mul(w, axis=0).sum().sort_values(ascending=False).rename_axis('대안').reset_index(name='가중합')
    colors = [RED if a.startswith('①') else GREY for a in total['대안']]
    st.markdown('**대안별 가중합 점수(0–1)**')
    st.plotly_chart(hbar(total, '가중합', '대안', colors, '{:.3f}'), width='stretch')
    st.caption('기본 가중치(7-2 Max100): ① .621 > ② .504 > ⓪ .394 > ③ .390. 점수(1–5점)는 7-2에서 연구자가 확정한 값입니다.')


# ---------- 6. 처리 화면 시안 ----------
AMBER = '#B7791F'
STATUS_BG = {'초과': '#F6DDD6', '임박': '#F7EBD3', '정상': '#FFFFFF'}


@st.cache_data
def open_trend(req, done, target):
    """주 단위로 '그날 처리 중이던 건'과 그중 목표일을 넘긴 건을 센다."""
    days = pd.date_range('2023-01-02', '2025-12-29', freq='W-MON')
    req, done = req.values, done.values
    rows = []
    for t in days.values:
        is_open = (req <= t) & (done > t)
        over = is_open & ((t - req) > np.timedelta64(target, 'D'))
        rows.append((t, is_open.sum(), over.sum()))
    return pd.DataFrame(rows, columns=['기준일', '처리 중', '목표일 초과'])


with tabs[6]:
    st.markdown('CS 직원이 매일 아침 여는 **처리 관리 화면**을 실제 데이터로 재현한 시안입니다. '
                '기준일을 고르면 그날 처리 중이던 건(요청일은 지났고 완료일은 아직 오지 않은 건)을 경과일 순으로 보여 줍니다.')
    c1, c2, c3 = st.columns([1, 1, 2])
    asof = pd.Timestamp(c1.date_input('기준일', value=pd.Timestamp('2024-10-01'),
                                      min_value=pd.Timestamp('2023-01-01'), max_value=pd.Timestamp('2025-12-31')))
    tgt = c2.number_input('목표일(일)', min_value=3, max_value=60, value=TARGET, step=1)
    near = 3
    op = v[(v['memo_req'] <= asof) & (v['memo_done'] > asof)].copy()
    op['경과일'] = (asof - op['memo_req']).dt.days
    op['남은 일수'] = tgt - op['경과일']
    op['상태'] = np.select([op['경과일'] > tgt, op['경과일'] > tgt - near], ['초과', '임박'], '정상')
    n_over, n_near = (op['상태'] == '초과').sum(), (op['상태'] == '임박').sum()

    if len(op):
        worst = op.groupby('trade').size().sort_values(ascending=False)
        takeaway(f'{asof:%Y-%m-%d} 아침에 처리 중인 건은 {len(op):,}건이고, 그중 {n_over:,}건({n_over / len(op):.0%})이 목표일 {tgt}일을 넘겼습니다. '
                 f'가장 많이 쌓인 공종은 {", ".join(worst.index[:3])}입니다. '
                 '지금 시스템은 처리를 마친 뒤 날짜를 입력하므로 이 목록을 그날 만들 수 없습니다. 단계별 기록(기능 ①)이 있어야 이 화면이 가능합니다.')
    else:
        takeaway(f'{asof:%Y-%m-%d}에는 선택한 조건에서 처리 중인 건이 없습니다. 기준일이나 필터를 바꿔 보세요.')

    k = st.columns(4)
    k[0].metric('처리 중', f'{len(op):,}건')
    k[1].metric(f'목표일 초과 ({tgt}일 넘음)', f'{n_over:,}건')
    k[2].metric(f'임박 (남은 {near}일 이내)', f'{n_near:,}건')
    k[3].metric('가장 오래된 건', f'{op["경과일"].max() if len(op) else 0:,}일째')

    tr = open_trend(v['memo_req'], v['memo_done'], int(tgt))
    fig = go.Figure()
    fig.add_scatter(x=tr['기준일'], y=tr['처리 중'], name='처리 중', mode='lines', line=dict(color=BLUE, width=2),
                    hovertemplate='%{x|%Y-%m-%d}<br>처리 중 %{y:,}건<extra></extra>')
    fig.add_scatter(x=tr['기준일'], y=tr['목표일 초과'], name=f'그중 목표일 초과', mode='lines', line=dict(color=RED, width=2),
                    hovertemplate='%{x|%Y-%m-%d}<br>목표일 초과 %{y:,}건<extra></extra>')
    fig.add_vline(x=asof, line_width=1, line_dash='dot', line_color=INK)
    fig.update_layout(showlegend=True, hovermode='x unified')
    st.markdown('**주별 처리 중 건수**(점선 = 선택한 기준일)')
    st.plotly_chart(style(fig, 260), width='stretch')

    if len(op):
        f1, f2 = st.columns(2)
        stat_sel = f1.multiselect('상태', ['초과', '임박', '정상'], default=['초과', '임박', '정상'])
        partners = f2.multiselect('협력사(비우면 전체)', op['partner'].value_counts().index.tolist())
        w = op[op['상태'].isin(stat_sel)]
        if partners:
            w = w[w['partner'].isin(partners)]
        w = w.sort_values('경과일', ascending=False)
        table = pd.DataFrame({'상태': w['상태'], '동': w['dong'], '세대': w['unit_id'], '공종': w['trade'],
                              '세부 공종': w['sub_trade'], '하자 유형': w['defect_type'], '위치': w['place'],
                              '협력사': w['partner'], '요청일': w['memo_req'].dt.strftime('%Y-%m-%d'),
                              '경과일': w['경과일'], '남은 일수(음수=초과)': w['남은 일수']})
        st.markdown(f'**처리 대기 목록** {len(table):,}건 · 경과일이 긴 순')
        st.dataframe(table.style.apply(lambda r: [f'background-color:{STATUS_BG[r["상태"]]}'] * len(r), axis=1),
                     width='stretch', height=420, hide_index=True)

        by = op.pivot_table(index='trade', columns='상태', values='경과일', aggfunc='size', fill_value=0)
        for col in ['초과', '임박', '정상']:
            if col not in by:
                by[col] = 0
        by = by[['초과', '임박', '정상']].sort_values('초과', ascending=False).head(10)
        fig = go.Figure()
        for col, color in [('초과', RED), ('임박', AMBER), ('정상', GREY)]:
            fig.add_bar(y=by.index, x=by[col], name=col, orientation='h', marker_color=color,
                        hovertemplate='%{y}<br>' + col + ' %{x:,}건<extra></extra>')
        fig.update_layout(barmode='stack', showlegend=True, legend_traceorder='normal')
        fig.update_yaxes(autorange='reversed', gridcolor='rgba(0,0,0,0)')
        fig.update_xaxes(gridcolor='#EEF0F1')
        st.markdown('**공종별 처리 중 건수**(초과가 많은 10개 공종)')
        st.plotly_chart(style(fig, 34 * len(by) + 90), width='stretch')
    st.caption('이 화면은 완료된 기록을 거꾸로 돌려 "그날 보였어야 할 목록"을 재구성한 것입니다. 실제 운영에서는 배정·방문 단계 날짜가 더해져 '
               '"누가 붙잡고 있는지"까지 보여야 합니다. 세대는 동·호수를 비공개 키로 해시한 값입니다.')


