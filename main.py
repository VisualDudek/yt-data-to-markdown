import yaml
from pydantic.dataclasses import dataclass
from typing import Dict

YT_CONFIG = "yt_config.yaml"


@dataclass
class Config:
    channels: Dict[str, str]
    results: int


def load_yaml_file(file_path: str) -> dict:
    """
    Loads a YAML file and returns its contents as a dictionary.

    Args:
        file_path (str): The path to the YAML file.

    Returns:
        dict: The contents of the YAML file as a dictionary.
    """
    with open(file_path, 'r') as file:
        data = yaml.safe_load(file)
    return data


def parse_yaml_to_model(file_path: str) -> Config:
    """
    Parses a YAML file and returns a Config object.

    Args:
        file_path (str): The path to the YAML file.

    Returns:
        Config: The parsed Config object.

    """
    data = load_yaml_file(file_path)
    config = Config(**data)
    return config


# Example usage
if __name__ == "__main__":
    yaml_file_path = YT_CONFIG
    config_model = parse_yaml_to_model(yaml_file_path)
    
    if config_model:
        print(config_model)
    else:
        print("Failed to parse YAML file into model.")
