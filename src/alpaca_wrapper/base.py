import configparser
import os
from loguru import logger



class AlpacaConnectionError(Exception):
    """Custom exception for Alpaca connection errors."""
    pass


class AlpacaConnector:
    """
    A base class for Alpaca connectors.

    This class handles the connection to the Alpaca API, including reading the
    API keys from the config file.
    """

    def __init__(self, paper: bool = True):
        """
        Initializes the AlpacaConnector.

        Args:
            paper (bool, optional): Whether to use the paper trading environment.
                Defaults to True.
        
        Raises:
            ValueError: If the API keys are not found in the config file.
        """
        config = configparser.ConfigParser()
        # The path to the config file is relative to the project root
        config_path = os.path.join(os.path.dirname(__file__), '..', '..', 'config.ini')
        config.read(config_path)

        try:
            self.api_key = config['alpaca']['api_key']
            self.secret_key = config['alpaca']['secret_key']
            logger.info("API keys loaded from config.ini")
        except KeyError:
            logger.error("API keys not found in config.ini")
            raise ValueError("API keys not found in config.ini. Please make sure to add your API keys to the "
                             "config.ini file.")

        self.paper = paper

        if self.api_key == 'YOUR_API_KEY' or self.secret_key == 'YOUR_SECRET_KEY':
            logger.error("Please replace 'YOUR_API_KEY' and 'YOUR_SECRET_KEY' in config.ini with your actual "
                         "Alpaca API keys.")
            raise ValueError("Please replace 'YOUR_API_KEY' and 'YOUR_SECRET_KEY' in config.ini with your actual "
                             "Alpaca API keys.")
