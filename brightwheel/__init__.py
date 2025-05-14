"""API Interface for mybrightwheel."""

import getpass

from fake_useragent import UserAgent

import requests

URL_BASE = 'https://schools.mybrightwheel.com/api/v1/'
AUTH_HEADERS = {
    'Content-Type': 'application/json',
    'X-Client-Version': '106',
    'X-Client-Name': 'web',
    'Origin': 'https://schools.mybrightwheel.com',
    'Referer': 'https://schools.mybrightwheel.com/sign-in',
    'User-Agent': UserAgent().random
}
COOKIE_NAME = '_brightwheel_v2'
COOKIE_DOMAIN = '.mybrightwheel.com'


class Client(object):
    """Session scoped client object."""

    session = requests.Session()
    user_id = None

    def __init__(self, login, auth=None, headless=False, force_login=False):
        """Create new client and init user data."""
        if auth and not force_login:
            self.session.cookies.set(
                COOKIE_NAME,
                auth,
                domain=COOKIE_DOMAIN
            )
        elif headless:
            raise Exception('Non-interactive auth must be used in headless mode!')  # noqa:E501
        else:
            mfa_code = None
            password = getpass.getpass()
            start_response = self.post_sessions_start(login, password)
            if start_response['2fa_required']:
                mfa_code = input('Enter MFA code: ')
            self.post_sessions(login, password, mfa_code)
        response = self.get_users_me()
        self.user_id = response['object_id']

    def session_auth(self):
        """Return current auth cookie value."""
        for c in self.session.cookies:
            if c.name == COOKIE_NAME and c.domain == COOKIE_DOMAIN:
                return c.value

    def get_users_me(self):
        """Get info on currently authenticated user."""
        return self._call('GET', 'users/me')

    def post_sessions_start(self, email, password):
        """Initiate login process."""
        json = {
            'user': {
                'email': email,
                'password': password
            }
        }
        headers = AUTH_HEADERS
        return self._call('POST', 'sessions/start', json=json, headers=headers)

    def post_sessions(self, email, password, mfa_code=None):
        """Complete login process with mfa code."""
        json = {
            'user': {
                'email': email,
                'password': password
            }
        }
        if mfa_code:
            json['2fa_code'] = mfa_code
        headers = AUTH_HEADERS
        return self._call('POST', 'sessions', json=json, headers=headers)

    def get_students_activities(
            self, student_id,
            start_date=None, end_date=None, page=0, page_size=10):
        """Get activity feed by student."""
        params = {
            'page': page,
            'page_size': page_size
        }
        if start_date:
            params['start_date'] = start_date
        if end_date:
            params['end_date'] = end_date
        return self._call('GET', f'students/{student_id}/activities', params=params)  # noqa:E501

    def get_guardians_students(self):
        """Get students according to logged in user."""
        return self._call('GET', f'guardians/{self.user_id}/students')

    def _call(self, verb, url, **kwargs):
        response = self.session.request(
            verb,
            URL_BASE + url,
            **kwargs
        )
        response.raise_for_status()
        return response.json()
