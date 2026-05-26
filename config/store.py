# Import Config
from .roles import (
    ROLE_HISTORIAN,
    ROLE_INFO_ADVANCED,
    ROLE_MULTITASKER,
    ROLE_PROMOTER,
    ROLE_PROMOTER_ADVANCED,
    ROLE_SPEAKER,
    ROLE_SUGGESTER,
)

STORE_ITEMS = {
    ROLE_PROMOTER: {
        "label": "홍보자",
        "price": 7000,
        "description": "홍보 기능 이용 권한",
    },
    ROLE_PROMOTER_ADVANCED: {
        "label": "홍보대사",
        "price": 10000,
        "description": "홍보 횟수 증가 변경 5회",
    },
    ROLE_SUGGESTER: {
        "label": "제안자",
        "price": 10000,
        "description": "정기토론 주제 추천 가능",
    },
    ROLE_SPEAKER: {
        "label": "연설자",
        "price": 10000,
        "description": "스테이지 채널에서 연설 가능",
    },
    ROLE_INFO_ADVANCED: {
        "label": "더보기",
        "price": 3000,
        "description": "/info 기능 확장 권한",
    },
    ROLE_MULTITASKER: {
        "label": "멀티태스커",
        "price": 12000,
        "description": "동시 토론 진행 수 증가(3회)",
    },
    ROLE_HISTORIAN: {
        "label": "역사가",
        "price": 7000,
        "description": "아카이브 열람 권한",
    },
}
