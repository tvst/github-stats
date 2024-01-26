import streamlit as st
import github_util as gh
import polars as pl
import datetime
import altair as alt

def set_page_icon(emoji):
    st.set_page_config(page_icon=emoji)

    st.markdown(
        f'<b style="display: block; font-size: 4rem; line-height: 1; margin-bottom: -2rem">{emoji}</b>',
        unsafe_allow_html=True)

class MetaParam(type):
    def __getattr__(cls, k):
        return Param(k)

class Param(metaclass=MetaParam):
    def __init__(self, k):
        self.key = k

    def int(self, fallback=0):
        return int(float(self.get(fallback)))

    def float(self, fallback=0.0):
        return float(self.get(fallback))

    def bool(self, fallback=False):
        return bool(self.get(fallback) == 'True')

    def date(self, fallback=False):
        param = self.get()

        if param is None:
            return fallback

        return datetime.date.fromisoformat(param)

    def str(self, fallback=''):
        return self.get(fallback)

    def get(self, fallback=None):
        return getattr(st.query_params, self.key, fallback)

    def set(self, v):
        v_typed = v

        if isinstance(v, datetime.date):
            v_typed = v.isoformat()

        st.query_params[self.key] = v_typed
        return v


set_page_icon(':twisted_rightwards_arrows:')

'''
# Github contributor stats
'''

''

repo = Param.repo.set(
    st.text_input('Repo', Param.repo.str('streamlit/streamlit')))

user_key = st.text_input(
    'GitHub API key (required for private repos)',
    help='''
        You may be asking whether you can trust this app not to steal your key.
        Fair question!

        Here's my response:
        1. I have better things to do with my life :smile:
        1. You can always read the source code and see that I'm not doing anything nefarious!
        '''
)

date_picker_container = st.container()


if Param.abs_dates.set(
    st.toggle('Enter specific dates', Param.abs_dates.bool())):

    with date_picker_container:
        a, b = st.columns(2)

        today = datetime.date.today()

        if 'delta' in st.session_state:
            delta = st.session_state.delta
        else:
            delta = datetime.timedelta(days=7)

        from_date = Param.from_date.set(
            a.date_input('From', Param.from_date.date(today - delta)))

        to_date = Param.to_date.set(
            b.date_input('To', Param.to_date.date(today)))

else:
    with date_picker_container:
        TIME_PERIODS = {
            'Last week': 7,
            'Last 30 days': 30,
            'Last 90 days': 90,
            'Last 6 months': 30 * 6,
            'Last year': 365,
        }

        period_index = next((
            i for i, v in enumerate(TIME_PERIODS.values())
            if v == Param.time_period.int()), 0)

        period = st.selectbox('Time period', TIME_PERIODS, period_index)

        to_date = datetime.date.today()

        days = Param.time_period.set(TIME_PERIODS[period])
        delta = datetime.timedelta(days=days)

        st.session_state.delta = delta

        from_date = to_date - delta

@st.cache_data(ttl='1d', show_spinner='Fetching data')
def fetch_commits_cached(token, repo, from_date, to_date):
    repo_owner, _, repo_name = repo.partition('/')

    return gh.fetch_commits(
        token,
        repo_owner,
        repo_name,
        from_date,
        to_date,
    )

if user_key:
    token = user_key
else:
    token = st.secrets.github_token

''
''
commits = fetch_commits_cached(token, repo, str(from_date), str(to_date))
''
''


'''
### Users with most PRs
'''

if commits.is_empty():
    data = commits

else:
    data = (commits.lazy()
        .group_by('authorEmail')
        .agg(
            pl.first('authorName'),
            pl.len().alias('numPRs'),
        )
        .sort('numPRs', descending=True)
        .collect()
    )

    st.altair_chart(
        alt.Chart(data)
            .mark_bar(orient='horizontal')
            .encode(
                x=alt.X('numPRs', title=None),
                y=alt.Y('authorName', sort='-x', title=None),
            ),
            use_container_width=True
    )

with st.expander('Raw data'):
    st.dataframe(data)

''
''
''
''
''
''

'''
### Users with most changed lines
'''

if commits.is_empty():
    data = commits

else:
    data = (commits.lazy()
        .group_by('authorEmail')
        .agg(
            pl.first('authorName'),
            pl.sum('additions'),
            pl.sum('deletions'),
            pl.sum('changes'),
        )
        .sort('changes', descending=True)
        .collect()
    )

    st.altair_chart(
        alt.Chart(data)
            .transform_fold(['changes', 'additions', 'deletions'])
            .mark_bar(orient='horizontal')
            .encode(
                x=alt.X('value:Q', stack=False, title=None),
                y=alt.Y('authorName', sort='-x', title=None),
                color='key:N',
                yOffset=alt.YOffset('key:N').sort(['changes', 'additions', 'deletions']),
            ),
            use_container_width=True
    )

with st.expander('Raw data'):
    st.dataframe(data)


''
''
''
''
''
''

'''
### Timeline of commits
'''

if not commits.is_empty():
    st.altair_chart(
        alt.Chart(commits)
            .mark_point(orient='horizontal', filled=True, opacity=0.75)
            .encode(
                x=alt.X('committedDate:T', title=None),
                y=alt.Y(
                    'authorName:N',
                    sort='ascending',
                    title=None,
                    axis=alt.Axis(grid=True),
                ),
                color=alt.Color(
                    'authorName',
                    legend=None,
                    # scale=alt.Scale(scheme='tableau20'),
                ),
                size=alt.Size(
                    'changes',
                    legend=None,
                    scale=alt.Scale(range=[25, 1000], type='sqrt'),
                ),
                href='url',
            )
        ,
        use_container_width=True
    )

st.dataframe(
    commits,
    column_order=[
        'messageHeadline',
        'authorEmail',
        'authorName',
        'committedDate',
        'changes',
        'oid',
        'url',
    ],
    column_config={
        'url': st.column_config.LinkColumn(),
    }
)
