import os
from unittest.mock import patch

import pytest
from dotenv import load_dotenv

from baha_blacklist.config import Config
from baha_blacklist.gamer_api import GamerAPIExtended

load_dotenv()


@pytest.fixture
def mock_config():
    config = Config()
    config.browser = "chrome131"
    config.account = os.environ["BAHA_ACCOUNT"]
    config.password = os.environ["BAHA_PASSWORD"]
    config.cookies_first = True
    return config


@pytest.fixture
def mock_api(mock_config) -> GamerAPIExtended:
    return GamerAPIExtended(mock_config)


def test_api(mock_api, mock_config):
    # 常數設定
    remove_success_msg = "D-ONE"
    add_success_msg = "成功"
    uids_env = os.environ.get("UIDS", "")
    uids = uids_env.split(",")

    # 測試登入
    with patch(
        "baha_blacklist.gamer_api.GamerLogin.login_success", return_value=True
    ) as mock_login_success:
        assert mock_api.login() is True
        assert 1 <= mock_login_success.call_count <= 2, "login_success 呼叫次數應在兩次內"

    # 測試移除
    results = mock_api.remove_users(uids)
    for uid in uids:
        assert remove_success_msg in results[uid]

    # 測試新增
    skipped_users = []
    results = mock_api.add_users(uids, skipped_users)
    for uid in uids:
        assert add_success_msg in results[uid]
