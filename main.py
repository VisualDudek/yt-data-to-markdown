import yaml
from helper import parse_yaml_to_model


YT_CONFIG = "yt_config.yaml"


# Example usage
if __name__ == "__main__":
    yaml_file_path = YT_CONFIG
    config_model = parse_yaml_to_model(yaml_file_path)
    
    if config_model:
        print(config_model)
    else:
        print("Failed to parse YAML file into model.")
