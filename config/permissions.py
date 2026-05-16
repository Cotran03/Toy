# Import Config
from .roles import ROLE_STAFF, ROLE_SYSTEM_ADMIN, ROLE_TOTAL, ROLE_USER_ADMIN

# Role groups used for command authorization.

WARN_ROLES = [ROLE_TOTAL, ROLE_STAFF, ROLE_USER_ADMIN]          # 경고 부여 권한
BALANCER_ROLES = [ROLE_TOTAL, ROLE_STAFF, ROLE_USER_ADMIN]      # 재화 조정 권한
POST_END_ROLES = [ROLE_TOTAL, ROLE_STAFF, ROLE_SYSTEM_ADMIN]    # 포스트 종료 권한
