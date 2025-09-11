"""Configuration for Inflection Curator.

This module defines the configuration settings for the application, including
the models to use for the different components of the planning pipeline, and
the settings for LiteLLM and logging.

Attributes:
    MODEL_PARSER (str): The name of the model to use for the query parser.
    MODEL_PLANNER (str): The name of the model to use for the planner.
    MODEL_AGENT (str): The name of the model to use for the agent.
    LITELLM_TIMEOUT (float): The timeout for LiteLLM requests.
    LITELLM_RETRIES (int): The number of retries for LiteLLM requests.
    LOG_SINK (str): The sink for the application logs.
"""

import os

# LiteLLM models (OpenAI-compatible JSON mode recommended)
MODEL_PARSER = os.getenv("MODEL_PARSER", "gpt-4o-mini")
MODEL_PLANNER = os.getenv("MODEL_PLANNER", "gpt-4o-mini")
MODEL_AGENT = os.getenv("MODEL_AGENT", "gpt-4o-mini")

# LiteLLM knobs
LITELLM_TIMEOUT = float(os.getenv("LITELLM_TIMEOUT", "30"))
LITELLM_RETRIES = int(os.getenv("LITELLM_RETRIES", "2"))

# Logging sink
# "stdout" | f"file:{path}" | "http(s)://endpoint"
LOG_SINK = os.getenv("APP_LOG_SINK", "stdout")


def load_config() -> dict:
    """Loads the configuration settings.

    Returns:
        A dictionary containing the configuration settings.
    """
    return {
        "MODEL_PARSER": MODEL_PARSER,
        "MODEL_PLANNER": MODEL_PLANNER,
        "MODEL_AGENT": MODEL_AGENT,
        "LITELLM_TIMEOUT": LITELLM_TIMEOUT,
        "LITELLM_RETRIES": LITELLM_RETRIES,
        "LOG_SINK": LOG_SINK,
    }
