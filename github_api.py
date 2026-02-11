"""
GitHub API 封装模块
用于获取GitHub PR的状态信息
"""

import re
import requests
from typing import Optional, Dict, Any
from datetime import datetime


class GitHubAPIError(Exception):
    """GitHub API 错误"""
    pass


class PRMonitor:
    """GitHub PR 监控器"""

    BASE_URL = "https://api.github.com"

    def __init__(self, token: Optional[str] = None):
        """
        初始化PR监控器

        Args:
            token: GitHub Personal Access Token (可选)
                   提供token可以提高API速率限制从60次/小时到5000次/小时
        """
        self.session = requests.Session()
        self.session.headers.update({
            'Accept': 'application/vnd.github.v3+json',
            'User-Agent': 'GitHub-PR-Monitor'
        })

        # 如果提供了token，添加到请求头
        if token:
            self.session.headers['Authorization'] = f'token {token}'

    def set_token(self, token: Optional[str]):
        """
        设置或更新GitHub Token

        Args:
            token: GitHub Personal Access Token，None表示移除token
        """
        if token:
            self.session.headers['Authorization'] = f'token {token}'
        elif 'Authorization' in self.session.headers:
            del self.session.headers['Authorization']

    @staticmethod
    def parse_pr_url(url: str) -> Optional[Dict[str, str]]:
        """
        解析GitHub PR URL

        Args:
            url: GitHub PR URL (例如: https://github.com/owner/repo/pull/123)

        Returns:
            包含owner, repo, pull_number的字典，解析失败返回None
        """
        pattern = r'https?://github\.com/([^/]+)/([^/]+)/pull/(\d+)'
        match = re.match(pattern, url.strip())

        if match:
            return {
                'owner': match.group(1),
                'repo': match.group(2),
                'pull_number': match.group(3)
            }
        return None

    def get_pr_info(self, owner: str, repo: str, pull_number: str) -> Dict[str, Any]:
        """
        获取PR基本信息

        Args:
            owner: 仓库所有者
            repo: 仓库名称
            pull_number: PR编号

        Returns:
            PR信息字典

        Raises:
            GitHubAPIError: API调用失败
        """
        url = f"{self.BASE_URL}/repos/{owner}/{repo}/pulls/{pull_number}"

        try:
            response = self.session.get(url, timeout=10)

            if response.status_code == 404:
                raise GitHubAPIError("PR不存在或仓库不可访问")
            elif response.status_code == 403:
                raise GitHubAPIError("API速率限制已达上限，请稍后再试")
            elif response.status_code != 200:
                raise GitHubAPIError(f"API请求失败: {response.status_code}")

            return response.json()

        except requests.exceptions.Timeout:
            raise GitHubAPIError("请求超时，请检查网络连接")
        except requests.exceptions.ConnectionError:
            raise GitHubAPIError("网络连接失败")
        except requests.exceptions.RequestException as e:
            raise GitHubAPIError(f"请求失败: {str(e)}")

    def get_pr_status(self, owner: str, repo: str, pull_number: str) -> Dict[str, Any]:
        """
        获取PR的完整状态信息

        Args:
            owner: 仓库所有者
            repo: 仓库名称
            pull_number: PR编号

        Returns:
            包含PR详细状态的字典
        """
        pr_info = self.get_pr_info(owner, repo, pull_number)

        # 提取关键信息
        result = {
            'title': pr_info.get('title', 'N/A'),
            'state': pr_info.get('state', 'unknown'),
            'merged': pr_info.get('merged', False),
            'author': pr_info.get('user', {}).get('login', 'N/A'),
            'created_at': self._format_time(pr_info.get('created_at')),
            'updated_at': self._format_time(pr_info.get('updated_at')),
            'mergeable': pr_info.get('mergeable'),
            'mergeable_state': pr_info.get('mergeable_state', 'unknown'),
            'draft': pr_info.get('draft', False),
            'url': pr_info.get('html_url', ''),
        }

        # 获取CI状态
        if pr_info.get('head', {}).get('sha'):
            sha = pr_info['head']['sha']
            result['ci_status'] = self._get_commit_status(owner, repo, sha)
        else:
            result['ci_status'] = 'unknown'

        # 获取审查状态
        result['review_status'] = self._get_review_status(owner, repo, pull_number)

        return result

    def _get_commit_status(self, owner: str, repo: str, sha: str) -> str:
        """
        获取commit的CI状态

        Returns:
            'success', 'pending', 'failure', 'error', 'unknown'
        """
        url = f"{self.BASE_URL}/repos/{owner}/{repo}/commits/{sha}/status"

        try:
            response = self.session.get(url, timeout=10)
            if response.status_code == 200:
                data = response.json()
                state = data.get('state', 'unknown')
                return state
        except:
            pass

        return 'unknown'

    def _get_review_status(self, owner: str, repo: str, pull_number: str) -> str:
        """
        获取PR的审查状态

        Returns:
            'approved', 'changes_requested', 'pending', 'unknown'
        """
        url = f"{self.BASE_URL}/repos/{owner}/{repo}/pulls/{pull_number}/reviews"

        try:
            response = self.session.get(url, timeout=10)
            if response.status_code == 200:
                reviews = response.json()

                if not reviews:
                    return 'pending'

                # 获取最新的审查状态
                latest_states = {}
                for review in reviews:
                    user = review.get('user', {}).get('login')
                    state = review.get('state')
                    if user and state:
                        latest_states[user] = state

                # 判断整体状态
                if 'CHANGES_REQUESTED' in latest_states.values():
                    return 'changes_requested'
                elif 'APPROVED' in latest_states.values():
                    return 'approved'
                else:
                    return 'pending'
        except:
            pass

        return 'unknown'

    def get_user_repos(self, owner: str) -> list:
        """
        获取用户或组织的公开仓库列表

        Args:
            owner: 用户名或组织名

        Returns:
            仓库名列表
        """
        try:
            # 先尝试作为组织获取
            url = f"{self.BASE_URL}/orgs/{owner}/repos"
            response = self.session.get(url, timeout=10, params={'per_page': 100, 'sort': 'updated'})

            # 如果不是组织，尝试作为用户获取
            if response.status_code == 404:
                url = f"{self.BASE_URL}/users/{owner}/repos"
                response = self.session.get(url, timeout=10, params={'per_page': 100, 'sort': 'updated'})

            if response.status_code == 200:
                repos = response.json()
                return [repo['name'] for repo in repos]
            else:
                return []
        except Exception as e:
            print(f"获取仓库列表失败: {e}")
            return []

    @staticmethod
    def _format_time(time_str: Optional[str]) -> str:
        """格式化时间字符串"""
        if not time_str:
            return 'N/A'

        try:
            dt = datetime.fromisoformat(time_str.replace('Z', '+00:00'))
            return dt.strftime('%Y-%m-%d %H:%M:%S')
        except:
            return time_str
