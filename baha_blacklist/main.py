import logging
import sys
import time
from argparse import Namespace
from pathlib import Path

from curl_cffi.requests.exceptions import RequestException

from .config import Config, ConfigLoader
from .gamer_api import GamerAPIExtended
from .logger import setup_logging
from .utils import load_users, write_users

logger = logging.getLogger("baha_blacklist")


def init_app(args: Namespace, config_name: str = "config.json") -> tuple[Config, GamerAPIExtended]:
    loglevel = logging.INFO
    if args.verbose:
        loglevel = logging.DEBUG
    if args.quiet:
        loglevel = logging.WARNING

    setup_logging(loglevel)
    json_path = str(Path(__file__).parents[1] / config_name)
    config_loader = ConfigLoader(Config())
    config = config_loader.load_config(json_path, args)

    api = GamerAPIExtended(config)
    return config, api


def real_main(args: Namespace, config: Config, api: GamerAPIExtended) -> int:
    if not api.login():
        sys.exit(0)

    if "export" in args.mode:
        logger.info("開始匯出黑名單...")
        existing_users = api.export_users()
        write_users(config.blacklist_dest, existing_users)
    else:
        existing_users = api.export_users()

    time.sleep(config.min_sleep)

    if "update" in args.mode:
        logger.info("開始更新黑名單...")
        try:
            uids = load_users(config.blacklist_src, api.session)
        except RequestException as e:
            logger.error(f"黑名單來源讀取失敗: {e}")
            uids = []
        if uids:
            api.add_users(uids, existing_users, category="bad")
        else:
            logger.info("沒有更新黑名單，因為載入失敗或來源黑名單為空")

    if "clean" in args.mode:
        logger.info("開始清理黑名單...")
        if args.force_clean or len(existing_users) > config.friend_num:
            api.auto_remove_users(
                existing_users, min_visits=config.min_visit, min_days=config.min_day
            )
        else:
            logger.info(f"黑名單數量未超過 {config.friend_num} 人, 跳過自動清理功能")

    return 0


def main(args: Namespace, config_name: str = "config.json") -> int:
    try:
        config, api = init_app(args, config_name)
        return real_main(args, config, api)
    except RequestException as e:
        logger.error(f"網路錯誤: {e}")
    except ValueError as e:
        logger.error(f"輸入錯誤: {e}")
    except RuntimeError as e:
        logger.error(f"執行階段錯誤: {e}")
    except Exception as e:
        logger.exception(f"發生未預期的錯誤: {e}")
    return 1
