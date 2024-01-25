import requests
import polars as pl

def make_request(token, query, variables=None):
    response = requests.post(
        'https://api.github.com/graphql',
        json={
            'query': query,
            'variables': variables,
        },
        headers={
            'Authorization': f'token {token}',
        }
    )

    if response.status_code == 200:
        return response.json()

    raise Exception("Query failed to run by returning code of {}. {}".format(response.status_code, query))

def fetch_commits(token, repo_owner, repo_name, from_date, to_date):
    if not repo_owner or not repo_name:
        return pl.DataFrame()

    coalesced_commits = []
    has_next_page = True
    cursor = None

    while has_next_page:
        response = make_request(token,
            """
            query ($owner: String!, $repo: String!, $cursor: String, $since: GitTimestamp!, $until: GitTimestamp!) {
              repository(owner: $owner, name: $repo) {
                defaultBranchRef {
                  target {
                    ... on Commit {
                      history(first: 100, after: $cursor, since: $since, until: $until) {
                        nodes {
                          oid
                          url
                          messageHeadline
                          committedDate
                          additions
                          deletions
                          author {
                            name
                            email
                          }
                        }
                        pageInfo {
                          hasNextPage
                          endCursor
                        }
                      }
                    }
                  }
                }
              }
            }""",
            variables={
              'owner': repo_owner,
              'repo': repo_name,
              'since': f'{from_date}T00:00:00Z',
              'until': f'{to_date}T00:00:00Z',
              'cursor': cursor,
            },
        )

        history_dict = response['data']['repository']['defaultBranchRef']['target']['history']
        commits = history_dict['nodes']
        coalesced_commits.extend(commits)

        has_next_page = history_dict['pageInfo']['hasNextPage']
        cursor = history_dict['pageInfo']['endCursor']

    commits_df = pl.DataFrame(coalesced_commits)

    if commits_df.is_empty():
        return commits_df

    return (commits_df
        .lazy()
        .with_columns([
            pl.col('author').struct.field('email').alias('authorEmail'),
            pl.col('author').struct.field('name').alias('authorName'),
            (pl.col('additions') + pl.col('deletions')).alias('changes'),
        ])
        .select(pl.col('*').exclude('author'))
        .collect()
    )
