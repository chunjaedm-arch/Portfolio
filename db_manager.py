import requests
from urllib.parse import quote

class DBManager:
    def __init__(self, project_id, api_key):
        self.project_id = project_id
        self.api_key = api_key
        self.base_url = f"https://firestore.googleapis.com/v1/projects/{self.project_id}/databases/(default)/documents"
        self.auth_url = f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={self.api_key}"

    def _handle_response(self, response):
        try:
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as e:
            try:
                error_data = response.json()
                if 'error' in error_data:
                    error_info = error_data['error']
                    raise Exception(error_info.get('message', str(error_info)))
            except ValueError:
                pass
            raise e

    def login(self, email, password):
        payload = {"email": email, "password": password, "returnSecureToken": True}
        res = requests.post(self.auth_url, json=payload)
        return self._handle_response(res)

    def refresh_token(self, refresh_token):
        url = f"https://securetoken.googleapis.com/v1/token?key={self.api_key}"
        payload = {"grant_type": "refresh_token", "refresh_token": refresh_token}
        res = requests.post(url, json=payload)
        return self._handle_response(res)

    def refresh_auth_token(self, refresh_token):
        """Refresh Token을 사용하여 ID Token을 갱신하고 파싱 된 결과를 반환"""
        res = self.refresh_token(refresh_token)
        new_id_token = res.get('id_token') or res.get('idToken')
        new_refresh_token = res.get('refresh_token') or res.get('refreshToken')
        return new_id_token, new_refresh_token

    def get_friendly_error_message(self, error_msg):
        """Firebase 에러 메시지를 사용자 친화적인 메시지로 변환"""
        error_map = {
            "EMAIL_NOT_FOUND": "존재하지 않는 이메일입니다.",
            "INVALID_PASSWORD": "비밀번호가 틀렸습니다.",
            "USER_DISABLED": "차단된 사용자입니다.",
            "INVALID_EMAIL": "올바른 이메일 형식이 아닙니다.",
            "MISSING_PASSWORD": "비밀번호를 입력해주세요."
        }
        for key, msg in error_map.items():
            if key in str(error_msg):
                return msg
        return f"오류: {error_msg}"

    def fetch_portfolio(self, id_token):
        url = f"{self.base_url}/portfolio"
        headers = {"Authorization": f"Bearer {id_token}"}
        res = requests.get(url, headers=headers)
        return self._handle_response(res)

    def save_asset(self, id_token, name, data):
        safe_name = quote(name, safe='')
        url = f"{self.base_url}/portfolio/{safe_name}"
        headers = {"Authorization": f"Bearer {id_token}"}
        res = requests.patch(url, headers=headers, json=data)
        return self._handle_response(res)

    def delete_asset(self, id_token, name):
        safe_name = quote(name, safe='')
        url = f"{self.base_url}/portfolio/{safe_name}"
        headers = {"Authorization": f"Bearer {id_token}"}
        res = requests.delete(url, headers=headers)
        return self._handle_response(res)

    def fetch_history(self, id_token):
        url = f"{self.base_url}/history"
        headers = {"Authorization": f"Bearer {id_token}"}
        res = requests.get(url, headers=headers)
        return self._handle_response(res)

    def save_history(self, id_token, date_id, data):
        url = f"{self.base_url}/history/{date_id}"
        headers = {"Authorization": f"Bearer {id_token}"}
        res = requests.patch(url, headers=headers, json=data)
        return self._handle_response(res)

    def delete_history(self, id_token, date_id):
        url = f"{self.base_url}/history/{date_id}"
        headers = {"Authorization": f"Bearer {id_token}"}
        res = requests.delete(url, headers=headers)
        return self._handle_response(res)

    def get_stats(self, id_token):
        url = f"{self.base_url}/config/stats"
        headers = {"Authorization": f"Bearer {id_token}"}
        res = requests.get(url, headers=headers)
        return self._handle_response(res)

    def update_stats(self, id_token, data):
        url = f"{self.base_url}/config/stats"
        headers = {"Authorization": f"Bearer {id_token}"}
        res = requests.patch(url, headers=headers, json=data)
        return self._handle_response(res)