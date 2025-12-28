from loguru import logger


class AlpacaConnectionError(Exception):
    """Custom exception for Alpaca connection errors."""
    pass


class AlpacaConnector:
    """
    A base class for Alpaca connectors.
    This class handles the connection to the Alpaca API.
    Credentials can be passed in directly or will be picked up
    from environment variables (APCA_API_KEY_ID, APCA_API_SECRET_KEY)
    by the underlying alpaca-py library.
    """

    def __init__(self, api_key: str = None, secret_key: str = None, paper: bool = True):
        """
        Initializes the AlpacaConnector.
        Args:
            api_key (str, optional): Alpaca API key. Defaults to None.
            secret_key (str, optional): Alpaca secret key. Defaults to None.
            paper (bool, optional): Whether to use the paper trading environment.
                Defaults to True.
        """
        self.api_key = api_key
        self.secret_key = secret_key
        self.paper = paper
        logger.info("AlpacaConnector initialized. Paper trading: {}", paper)
