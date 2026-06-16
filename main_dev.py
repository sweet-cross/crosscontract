import os

from dotenv import load_dotenv

from crosscontract import CrossClient, CrossRegistry
from crosscontract.release import create_data_package


def get_client(environment: str = "local", allow_prod: bool = False) -> CrossClient:
    """Initialize the client for the legacy server.

    Username and password are loaded from environment variables for
    stage and prod, and hardcoded for debug and local.

    Environment variables:
    - For stage: SUPERUSER, SUPERUSER_PASSWORD
    - For prod: ADMIN_USER, ADMIN_PASSWORD

    Args:
        environment: The environment to connect to.
            One of "debug", "local", "stage", "prod".
            Default is "local".
        allow_prod: Whether to allow connecting to the production environment.
            Defaults to False.
            If False, an error will be raised if the environment is "prod".

    Returns:
        CrossClient initialized with the appropriate credentials.
    """
    match environment:
        case "debug":
            username = "jabmin"
            password = "jabmin_password"
            domain = "http://localhost:8000"
            verify = False
        case "local":
            username = "jabmin"
            password = "jabmin_password"
            domain = "https://localhost"
            verify = False
        case "stage":
            username = os.getenv(f"USER_{environment.upper()}")
            password = os.getenv(f"PASSWORD_{environment.upper()}")
            domain = "https://backstage.sweetcross.link"
            verify = True
        case "prod":
            if not allow_prod:
                raise ValueError(
                    "Connecting to production environment is not allowed. "
                    "Set allow_prod=True to override this."
                )
            username = os.getenv(f"USER_{environment.upper()}")
            password = os.getenv(f"PASSWORD_{environment.upper()}")
            domain = "https://backend.sweet-cross.ch"
            verify = True
        case _:
            raise ValueError(f"Unknown environment: {environment}")
    client = CrossClient(username, password, base_url=domain, verify=verify)
    return client


if __name__ == "__main__":
    load_dotenv(".env")
    environment = "local"
    client = get_client(environment=environment, allow_prod=False)
    registry = CrossRegistry(client=client)

    create_data_package(
        registry=registry,
        release_spec="_jab_example_package.yaml",
        fn_out="_jab_example_data_package.zip",
    )

    print("here")
