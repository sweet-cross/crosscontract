import os

from dotenv import load_dotenv

from crosscontract import CrossClient


def get_user_credentials(env_file="notebooks/.env"):
    load_dotenv(env_file)
    username = os.getenv("CROSSUSER")
    password = os.getenv("PASSWORD")
    return username, password


if __name__ == "__main__":
    username, password = get_user_credentials()
    client = CrossClient(username=username, password=password)
    print(client.contracts.overview())
