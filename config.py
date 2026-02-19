import os
from dotenv import load_dotenv

# 같은 폴더에 있는 .env 파일을 찾아서 환경변수로 로드합니다.
load_dotenv()

config = {
    # 이제 코드 안에 실제 키 값은 없습니다.
    "apiKey": os.environ.get("FIREBASE_API_KEY", ""),
    "authDomain": os.environ.get("FIREBASE_AUTH_DOMAIN", ""),
    "projectId": os.environ.get("FIREBASE_PROJECT_ID", ""),
}
