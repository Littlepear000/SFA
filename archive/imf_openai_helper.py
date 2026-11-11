"""
IMF OpenAI Helper Module
Handles authentication, token caching, and client initialization.
Users should not need to modify this file.
"""
import json
import sys
import os
import atexit
import msal
from openai import OpenAI
from dotenv import dotenv_values


def _load_config():
    """Load configuration from .env file."""
    config = dotenv_values(".env")
    required_keys = ["API_KEY", "CLIENT_ID", "TENANT_ID","API_URL"]
    for key in required_keys:
        if key not in config:
            raise ValueError(f"Missing required config key: {key}")
    return config


def _get_access_token(config):
    """Handle MSAL authentication with token caching."""
    client_id = config["CLIENT_ID"]
    tenant_id = config["TENANT_ID"]
    authority = f"https://login.microsoftonline.com/{tenant_id}"
    scope = [".default"]

    # Token cache setup
    cache_filename = os.path.join(
        os.getenv("LOCALAPPDATA"), ".IdentityService", "imf_openai_cache.json"
    )
    os.makedirs(os.path.dirname(cache_filename), exist_ok=True)
    cache = msal.SerializableTokenCache()

    # Load existing cache
    if os.path.exists(cache_filename):
        with open(cache_filename, "r") as f:
            cache.deserialize(f.read())

    def save_cache():
        if cache.has_state_changed:
            with open(cache_filename, "w") as f:
                f.write(cache.serialize())

    atexit.register(save_cache)

    # Create MSAL app
    app = msal.PublicClientApplication(
        client_id=client_id,
        authority=authority,
        token_cache=cache
    )

    # Try silent acquisition first
    access_token = None
    accounts = app.get_accounts()

    if accounts:
        result = app.acquire_token_silent(scopes=scope, account=accounts[0])
        if result and "access_token" in result:
            access_token = result["access_token"]

    # Fall back to interactive login
    if not access_token:
        result = app.acquire_token_interactive(scopes=scope)
        if not result or "access_token" not in result:
            print("Failed to acquire access token:")
            print(json.dumps(result, indent=2))
            sys.exit(1)
        access_token = result["access_token"]
        save_cache()

    return access_token


def get_client():
    """
    Get an authenticated OpenAI client for the IMF API gateway.
    
    Args:
        dept: Department code (default: 'itd')
    
    Returns:
        OpenAI client configured for the IMF gateway
    """
    config = _load_config()
    access_token = _get_access_token(config)

    client = OpenAI(
        api_key="DUMMY",
        base_url=config["API_URL"],
        default_headers={
            "api-key": config["API_KEY"],
            "Authorization": f"Bearer {access_token}",
        },
    )
    
    return client