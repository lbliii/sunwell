from typing import Any
import requests

class PostService:

    def __init__(self, base_url: str):
        self.base_url = base_url

    def post(self, endpoint: str, data: dict[str, Any]]) -> requests.Response:
        """
        Perform a POST operation to the specified endpoint of the service.

        Args:
            endpoint (str): The endpoint path for the POST request.
            data (dict[str, Any]]): The data payload to be sent in the POST request.

        Returns:
            requests.Response: The response object containing the server's response to the POST request.
        """
        url = f"{self.base_url}/{endpoint}"
        response = requests.post(url, json=data))
        return response