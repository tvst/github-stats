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

set_page_icon(':twisted_rightwards_arrows:')

'''
# Github contributor stats
'''

''

repo = st.text_input('Repo', 'streamlit/streamlit')

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

def show_relative_date_picker():
    TIME_PERIODS = {
        'Last week': 7,
        'Last 30 days': 30,
        'Last 90 days': 90,
        'Last 6 months': 30 * 6,
        'Last year': 365,
    }

    period = st.selectbox('Time period', TIME_PERIODS)

    to_date = datetime.date.today()
    delta = datetime.timedelta(days=TIME_PERIODS[period])
    st.session_state.delta = delta

    from_date = to_date - delta

    return str(from_date), str(to_date)

def show_absolute_date_picker():
    a, b = st.columns(2)

    today = datetime.date.today()

    if 'delta' in st.session_state:
        delta = st.session_state.delta
    else:
        delta = datetime.timedelta(days=7)

    from_date = a.date_input('From', today - delta)

    to_date = b.date_input('To', today)

    return str(from_date), str(to_date)


date_picker_container = st.container()

if st.toggle('Enter specific dates'):
    with date_picker_container:
        from_date, to_date = show_absolute_date_picker()
else:
    with date_picker_container:
        from_date, to_date = show_relative_date_picker()

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
commits = fetch_commits_cached(token, repo, from_date, to_date)
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
                x=alt.X('numPRs'),
                y=alt.Y('authorName', sort='-x'),
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
                x=alt.X('value:Q', stack=False),
                y=alt.Y('authorName', sort='-x'),
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
