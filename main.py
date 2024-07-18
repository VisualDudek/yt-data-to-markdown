import yaml
import logging
import logging.config

from helper import parse_yaml_to_model


YT_CONFIG = "yt_config.yaml"
LOGGING_CONFIG = "logging_config.yaml"

# Load the config file
with open(LOGGING_CONFIG, 'rt') as f:
    config = yaml.safe_load(f.read())

# Configure the logging module with the config file
logging.config.dictConfig(config)

# Get a logger object
logger = logging.getLogger(__name__)

def main():

    pass


# Example usage
if __name__ == "__main__":
    yaml_file_path = YT_CONFIG
    logger.info(f"Reading YAML file: {yaml_file_path}")
    config_model = parse_yaml_to_model(yaml_file_path)
    
    if config_model:
        logger.debug(config_model)
    else:
        logger.error("Failed to parse YAML file into model.")
