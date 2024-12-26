import json
import os
from argparse import Namespace
from dataclasses import asdict, dataclass
from typing import Any


@dataclass
class Config:
    username: str = "default_user"
    cookie_path: str = "/default/cookie_path"
    blacklist_dest: str = "/default/blacklist_dest"
    blacklist_src: str = "/default/blacklist_src"
    min_sleep: float = 1.0
    max_sleep: float = 10.0
    min_visit: int = 5
    min_day: int = 1
    friend_num: int = 100
    user_agent: str = "default_user_agent"

    def validate(self) -> None:
        if self.min_sleep > self.max_sleep:
            raise ValueError("min_sleep must not be greater than max_sleep.")


class ConfigLoader:
    def __init__(self, defaults: Config):
        self.defaults = defaults

    def load_config(
        self,
        json_path: str | None = None,
        args: dict[str, Any] | Namespace | None = None,
        env_mapping: dict[str, str] | None = None,
    ) -> Config:
        env_mapping = env_mapping or {}
        json_config = self.load_from_json(json_path)
        cli_config = self.load_from_cli(args)
        env_config = self.load_from_env(env_mapping)
        final_config = self.merge_configs(env_config, json_config, cli_config)
        final_config.validate()
        return final_config

    def load_from_json(self, file_path: str | None) -> dict[str, Any]:
        if file_path and os.path.exists(file_path):
            with open(file_path) as file:
                try:
                    return json.load(file)
                except json.JSONDecodeError as e:
                    raise ValueError(f"Invalid JSON format in {file_path}: {e}")
        return {}

    def load_from_cli(self, args: dict[str, Any] | Namespace | None) -> dict[str, Any]:
        if args is None:
            return {}

        if isinstance(args, Namespace):
            args = vars(args)

        return args

    def load_from_env(self, env_mapping: dict[str, str]) -> dict[str, Any]:
        return {
            key: os.getenv(env_var)
            for key, env_var in env_mapping.items()
            if os.getenv(env_var) is not None
        }

    def merge_configs(self, *configs: dict[str, Any]) -> Config:
        merged = asdict(self.defaults)
        for config in configs:
            for key, value in config.items():
                if key in merged and value is None:
                    continue
                elif key in merged and isinstance(value, type(merged[key])):
                    merged[key] = value
                elif key in merged:
                    raise TypeError(
                        f"Type mismatch for key '{key}': Expected {type(merged[key])}, got {type(value)}"
                    )
        return Config(**merged)
