import datetime
import os
import re
import requests
from dateutil import relativedelta

USER_NAME = os.environ.get('USER_NAME', 'Dillulu')
TOKEN = os.environ.get('ACCESS_TOKEN') or os.environ.get('GITHUB_TOKEN') or ''
BIRTHDAY = datetime.datetime(2003, 1, 24)


def format_plural(unit):
    return 's' if unit != 1 else ''


def daily_readme(birthday):
    diff = relativedelta.relativedelta(datetime.datetime.today(), birthday)
    return '{} {}, {} {}, {} {}{}'.format(
        diff.years, 'year' + format_plural(diff.years),
        diff.months, 'month' + format_plural(diff.months),
        diff.days, 'day' + format_plural(diff.days),
        ' 🎂' if (diff.months == 0 and diff.days == 0) else ''
    )


def fetch_github_stats():
    headers = {'Accept': 'application/vnd.github+json'}
    if TOKEN:
        headers['Authorization'] = f'Bearer {TOKEN}'

    # Baseline from private repos (Eureka + renovoq) so public GITHUB_TOKEN runs stay accurate
    base_private_repos = 2
    base_private_commits = 31
    base_private_add = 205912
    base_private_del = 2350

    try:
        u_resp = requests.get(f'https://api.github.com/users/{USER_NAME}', headers=headers, timeout=15)
        u_data = u_resp.json() if u_resp.status_code == 200 else {}
        followers = int(u_data.get('followers', 0))

        # Check if authenticated token sees private repos
        r_url = 'https://api.github.com/user/repos?affiliation=owner,collaborator,organization_member&per_page=100' if TOKEN else f'https://api.github.com/users/{USER_NAME}/repos?per_page=100'
        r_resp = requests.get(r_url, headers=headers, timeout=15)
        if r_resp.status_code != 200 or not isinstance(r_resp.json(), list):
            r_resp = requests.get(f'https://api.github.com/users/{USER_NAME}/repos?per_page=100', headers=headers, timeout=15)
        repos = r_resp.json() if r_resp.status_code == 200 and isinstance(r_resp.json(), list) else []

        sees_private = any(r.get('private') for r in repos)
        owned_count = sum(1 for r in repos if r.get('owner', {}).get('login', '').lower() == USER_NAME.lower())
        contrib_count = len(repos)
        stars = sum(int(r.get('stargazers_count', 0)) for r in repos)

        commits_total = 0
        loc_add = 0
        loc_del = 0

        for r in repos:
            full_name = r.get('full_name')
            if not full_name:
                continue
            c_resp = requests.get(f'https://api.github.com/repos/{full_name}/commits?per_page=100', headers=headers, timeout=15)
            if c_resp.status_code == 200 and isinstance(c_resp.json(), list):
                c_list = c_resp.json()
                commits_total += len(c_list)
                for c in c_list:
                    sha = c.get('sha')
                    if not sha:
                        continue
                    d_resp = requests.get(f'https://api.github.com/repos/{full_name}/commits/{sha}', headers=headers, timeout=15)
                    if d_resp.status_code == 200:
                        st = d_resp.json().get('stats', {})
                        loc_add += int(st.get('additions', 0))
                        loc_del += int(st.get('deletions', 0))

        if not sees_private:
            owned_count += base_private_repos
            contrib_count += base_private_repos
            commits_total += base_private_commits
            loc_add += base_private_add
            loc_del += base_private_del

        return {
            'repos': owned_count,
            'contrib': contrib_count,
            'stars': stars,
            'followers': followers,
            'commits': commits_total,
            'loc_net': loc_add - loc_del,
            'loc_add': loc_add,
            'loc_del': loc_del,
        }
    except Exception as e:
        print('Fallback stats used due to:', e)
        return {
            'repos': 4,
            'contrib': 4,
            'stars': 0,
            'followers': 0,
            'commits': 43,
            'loc_net': 221446,
            'loc_add': 223800,
            'loc_del': 2354,
        }


def replace_id_val(svg_text, elem_id, new_val):
    pattern = rf'(<tspan[^>]*id="{re.escape(elem_id)}"[^>]*>)(.*?)(</tspan>)'
    return re.sub(pattern, lambda m: f"{m.group(1)}{new_val}{m.group(3)}", svg_text)


def update_svg_file(filename, age_data, stats):
    if not os.path.exists(filename):
        return
    with open(filename, 'r', encoding='utf-8') as f:
        svg = f.read()

    age_dots = ' ' + ('.' * max(2, 52 - len('Uptime') - len(age_data) - 2)) + ' '
    svg = replace_id_val(svg, 'age_data_dots', age_dots)
    svg = replace_id_val(svg, 'age_data', age_data)

    repo_str = f"{stats['repos']:,}"
    contrib_str = f"{stats['contrib']:,}"
    star_str = f"{stats['stars']:,}"
    commit_str = f"{stats['commits']:,}"
    follower_str = f"{stats['followers']:,}"
    loc_net_str = f"{stats['loc_net']:,}"
    loc_add_str = f"{stats['loc_add']:,}"
    loc_del_str = f"{stats['loc_del']:,}"

    svg = replace_id_val(svg, 'repo_data', repo_str)
    svg = replace_id_val(svg, 'contrib_data', contrib_str)
    svg = replace_id_val(svg, 'star_data', star_str)
    svg = replace_id_val(svg, 'commit_data', commit_str)
    svg = replace_id_val(svg, 'follower_data', follower_str)
    svg = replace_id_val(svg, 'loc_data', loc_net_str)
    svg = replace_id_val(svg, 'loc_add', loc_add_str)
    svg = replace_id_val(svg, 'loc_del', loc_del_str)

    with open(filename, 'w', encoding='utf-8') as f:
        f.write(svg)


if __name__ == '__main__':
    age_str = daily_readme(BIRTHDAY)
    stats = fetch_github_stats()
    print('Updated Uptime:', age_str)
    print('Updated Stats:', stats)
    for svg_name in ['dark_mode.svg', 'light_mode.svg', 'profile-card.svg']:
        update_svg_file(svg_name, age_str, stats)
