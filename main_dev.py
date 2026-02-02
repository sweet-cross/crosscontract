import os

from dotenv import load_dotenv

from crosscontract import CrossClient, CrossContract


def get_user_credentials(env_file="notebooks/.env"):
    load_dotenv(env_file)
    username = os.getenv("CROSSUSER")
    password = os.getenv("PASSWORD")
    return username, password


# if __name__ == "__main__":
#     user, pwd = get_user_credentials()
#     my_client = CrossClient(
#         username=user, password=pwd, base_url="https://backstage.sweetcross.link"
#     )
#     df_overview = my_client.contracts.overview()
#     print(df_overview)
#     print(f"Username: {user}, Password: {'*' * len(pwd)}")

if __name__ == "__main__":
    contract_data = {
        "name": "contract_gdp",
        "title": "Gross Domestic Product (GDP)",
        "description": "Gross Domestic Product (GDP) by country and years.\n",
        "tableschema": {
            "fields": [
                {
                    "name": "country",
                    "type": "string",
                    "title": "Country Name",
                    "description": "Name of the country",
                    "constraints": {"required": True, "maxLength": 100},
                },
                {
                    "name": "year",
                    "type": "integer",
                    "title": "Year",
                    "description": "Year of the GDP data",
                    "constraints": {"required": True, "minimum": 2000, "maximum": 2050},
                },
                {
                    "name": "gdp",
                    "type": "number",
                    "title": "GDP Value",
                    "description": "Gross Domestic Product value in USD",
                    "constraints": {"required": True, "minimum": 0},
                },
            ]
        },
    }
    gdp_contract = CrossContract(**contract_data)
    df_valid = {
        "country": ["CountryA", "CountryB", "CountryC"],
        "year": [2020, 2021, 2022],
        "gdp": [500, 600, 700],
    }
    gdp_contract.tableschema.validate_dataframe(df=df_valid)
