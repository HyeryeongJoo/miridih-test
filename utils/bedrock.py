# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0
"""Helper utilities for working with Amazon Bedrock from Python notebooks"""
# Python Built-Ins:
import os
from typing import Optional

# External Dependencies:
import json
import boto3
from textwrap import dedent
from botocore.config import Config
from botocore.exceptions import ClientError

# Langchain
# from langchain.callbacks.base import BaseCallbackHandler



def get_bedrock_client(
    assumed_role: Optional[str] = None,
    endpoint_url: Optional[str] = None,
    region: Optional[str] = None,
):
    """Create a boto3 client for Amazon Bedrock, with optional configuration overrides

    Parameters
    ----------
    assumed_role :
        Optional ARN of an AWS IAM role to assume for calling the Bedrock service. If not
        specified, the current active credentials will be used.
    endpoint_url :
        Optional override for the Bedrock service API Endpoint. If setting this, it should usually
        include the protocol i.e. "https://..."
    region :
        Optional name of the AWS Region in which the service should be called (e.g. "us-east-1").
        If not specified, AWS_REGION or AWS_DEFAULT_REGION environment variable will be used.
    """
    if region is None:
        target_region = os.environ.get("AWS_REGION", os.environ.get("AWS_DEFAULT_REGION"))
    else:
        target_region = region

    print(f"Create new client\n  Using region: {target_region}")
    session_kwargs = {"region_name": target_region}
    client_kwargs = {**session_kwargs}

    profile_name = os.environ.get("AWS_PROFILE")
    print(f"  Using profile: {profile_name}")
    if profile_name:
        print(f"  Using profile: {profile_name}")
        session_kwargs["profile_name"] = profile_name

    retry_config = Config(
        region_name=target_region,
        retries={
            "max_attempts": 10,
            "mode": "standard",
        },
    )
    session = boto3.Session(**session_kwargs)

    if assumed_role:
        print(f"  Using role: {assumed_role}", end='')
        sts = session.client("sts")
        response = sts.assume_role(
            RoleArn=str(assumed_role),
            RoleSessionName="langchain-llm-1"
        )
        print(" ... successful!")
        client_kwargs["aws_access_key_id"] = response["Credentials"]["AccessKeyId"]
        client_kwargs["aws_secret_access_key"] = response["Credentials"]["SecretAccessKey"]
        client_kwargs["aws_session_token"] = response["Credentials"]["SessionToken"]

    if endpoint_url:
        client_kwargs["endpoint_url"] = endpoint_url

    bedrock_client = session.client(
        service_name="bedrock-runtime",
        config=retry_config,
        **client_kwargs
    )

    print("boto3 Bedrock client successfully created!")
    print(bedrock_client._endpoint)
    return bedrock_client


class bedrock_info():

    _BEDROCK_MODEL_INFO = {
        "Claude-Instant-V1": "anthropic.claude-instant-v1",
        "Claude-V1": "anthropic.claude-v1",
        "Claude-V2": "anthropic.claude-v2",
        "Claude-V2-1": "anthropic.claude-v2:1",
        "Claude-V3-Sonnet": "anthropic.claude-3-sonnet-20240229-v1:0",
        "Claude-V3-Haiku": "anthropic.claude-3-haiku-20240307-v1:0",
        "Claude-V3-Opus": "anthropic.claude-3-sonnet-20240229-v1:0",
        "Claude-V3-5-Sonnet": "anthropic.claude-3-5-sonnet-20240620-v1:0",
        "Jurassic-2-Mid": "ai21.j2-mid-v1",
        "Jurassic-2-Ultra": "ai21.j2-ultra-v1",
        "Command": "cohere.command-text-v14",
        "Command-Light": "cohere.command-light-text-v14",
        "Cohere-Embeddings-En": "cohere.embed-english-v3",
        "Cohere-Embeddings-Multilingual": "cohere.embed-multilingual-v3",
        "Titan-Embeddings-G1": "amazon.titan-embed-text-v1",
        "Titan-Text-Embeddings-V2": "amazon.titan-embed-text-v2:0",
        "Titan-Text-G1": "amazon.titan-text-express-v1",
        "Titan-Text-G1-Light": "amazon.titan-text-lite-v1",
        "Titan-Text-G1-Premier": "amazon.titan-text-premier-v1:0",
        "Titan-Text-G1-Express": "amazon.titan-text-express-v1",
        "Llama2-13b-Chat": "meta.llama2-13b-chat-v1"
    }

    @classmethod
    def get_list_fm_models(cls, verbose=False):

        if verbose:
            bedrock = boto3.client(service_name='bedrock')
            model_list = bedrock.list_foundation_models()
            return model_list["modelSummaries"]
        else:
            return cls._BEDROCK_MODEL_INFO

    @classmethod
    def get_model_id(cls, model_name):

        assert model_name in cls._BEDROCK_MODEL_INFO.keys(), "Check model name"

        return cls._BEDROCK_MODEL_INFO[model_name]
    

from botocore.exceptions import ClientError

def converse_invoke(bedrock_client,
                          model_id,
                          input_text):
    """
    Sends a message to a model.
    Args:
        bedrock_client: The Boto3 Bedrock runtime client.
        model_id (str): The model ID to use.
        input text : The input message.

    Returns:
        response (JSON): The conversation that the model generated.

    """

    message = {
        "role": "user",
        "content": [
            {
                "text": input_text
            }
        ]
    }

    messages = [message]

    # Send the message.
    response = bedrock_client.converse(
        modelId=model_id,
        messages=messages
    )

    return response

# Implement Exponential Backoff
import time
import botocore.exceptions

def converse_invoke_with_backoff(bedrock_client, model_id, input_text, retries=5):
    delay = 10  # Initial delay in seconds
    for attempt in range(retries):
        try:
            # Attempt to invoke the Converse API
            return converse_invoke(bedrock_client, model_id, input_text)
        except botocore.exceptions.ClientError as e:
            # Check if the exception is a ThrottlingException
            if e.response['Error']['Code'] == 'ThrottlingException':
                print(f"ThrottlingException encountered. Retrying in {delay} seconds...")
                time.sleep(delay)
                delay *= 5  # Exponential backoff
            else:
                # If it's not a ThrottlingException, re-raise the exception
                raise
    raise Exception("Max retries reached")


