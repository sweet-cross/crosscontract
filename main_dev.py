import os

from dotenv import load_dotenv

from crosscontract import CrossClient


def get_user_credentials(env_file="notebooks/.env"):
    load_dotenv(env_file)
    username = os.getenv("CROSSUSER")
    password = os.getenv("PASSWORD")
    return username, password


if __name__ == "__main__":
    user, pwd = get_user_credentials()
    my_client = CrossClient(
        username=user, password=pwd, base_url="https://backstage.sweetcross.link"
    )
    df_overview = my_client.contracts.overview()
    print(df_overview)
    print(f"Username: {user}, Password: {'*' * len(pwd)}")
