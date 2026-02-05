#!/usr/bin/env python3
"""Example of using streaming with Doubleword API for real-time chat completions.

STREAMING vs BATCH:
- STREAMING: Real-time API calls where tokens are generated incrementally (like ChatGPT)
- BATCH: Async jobs where you submit requests and poll for complete results later

USE STREAMING WHEN:
  ✓ Interactive applications (chatbots, UI streaming)
  ✓ Need immediate token-by-token response
  ✓ Want to show progress to users in real-time

USE BATCH WHEN:
  ✓ Processing many documents (bulk operations)
  ✓ Non-interactive/async workloads
  ✓ Cost savings (batch is ~50% cheaper)

KEY CHANGE FOR STREAMING:
  Add `stream=True` parameter to the chat completions request
"""

from openai import OpenAI
from dotenv import load_dotenv
import os

# Load environment variables
load_dotenv()

# Initialize client with Doubleword API
# Doubleword uses OpenAI-compatible API, so we use the OpenAI SDK
client = OpenAI(
    api_key=os.getenv('DOUBLEWORD_AUTH_TOKEN'),
    base_url=os.getenv('DOUBLEWORD_BASE_URL', 'https://api.doubleword.ai/v1')
)

def streaming_chat_completion(prompt: str, model: str = None):
    """Send a chat completion request with streaming enabled.

    Args:
        prompt: User message to send
        model: Model to use (defaults to DOUBLEWORD_MODEL from .env.dw)

    Yields:
        str: Token chunks as they're generated
    """
    if model is None:
        model = os.getenv('DOUBLEWORD_MODEL', 'Qwen/Qwen3-VL-235B-A22B-Instruct-FP8')

    print(f"Sending streaming request to {model}...\n")

    # Create streaming chat completion
    # KEY CHANGE: stream=True enables incremental response
    response = client.chat.completions.create(
        model=model,
        messages=[
            {
                "role": "user",
                "content": prompt
            }
        ],
        max_tokens=int(os.getenv('MAX_TOKENS', '1000')),
        stream=True  # ← THIS IS THE KEY PARAMETER
    )

    # Iterate over the streaming response chunks
    # Each chunk contains a delta with new content
    full_response = ""
    for chunk in response:
        # Check if chunk has content
        if chunk.choices[0].delta.content is not None:
            token = chunk.choices[0].delta.content
            full_response += token

            # Print token immediately (no buffering)
            print(token, end="", flush=True)

            # Yield for programmatic access
            yield token

    print("\n")  # New line after streaming completes
    return full_response


def non_streaming_chat_completion(prompt: str, model: str = None):
    """Send a chat completion request WITHOUT streaming (traditional mode).

    This waits for the entire response before returning.

    Args:
        prompt: User message to send
        model: Model to use (defaults to DOUBLEWORD_MODEL from .env.dw)

    Returns:
        str: Complete response text
    """
    if model is None:
        model = os.getenv('DOUBLEWORD_MODEL', 'Qwen/Qwen3-VL-235B-A22B-Instruct-FP8')

    print(f"Sending non-streaming request to {model}...")
    print("Waiting for complete response...\n")

    # Create non-streaming chat completion
    # KEY DIFFERENCE: stream=False (or omitted) waits for complete response
    response = client.chat.completions.create(
        model=model,
        messages=[
            {
                "role": "user",
                "content": prompt
            }
        ],
        max_tokens=int(os.getenv('MAX_TOKENS', '1000')),
        stream=False  # ← Default behavior (can be omitted)
    )

    # Access the complete message
    content = response.choices[0].message.content
    print(content)
    print()

    return content


if __name__ == "__main__":
    import sys

    # Example prompts
    test_prompt = "Explain the concept of batch processing vs streaming in 3 sentences."

    print("="*70)
    print("DOUBLEWORD API STREAMING DEMO")
    print("="*70)
    print()

    # Test streaming
    print("1. STREAMING MODE (stream=True)")
    print("-" * 70)
    print("Response appears token-by-token as generated:\n")

    try:
        list(streaming_chat_completion(test_prompt))
    except Exception as e:
        print(f"Error: {e}")
        print("\nNote: Ensure DOUBLEWORD_AUTH_TOKEN is set in .env.dw")
        sys.exit(1)

    print("\n")

    # Test non-streaming
    print("2. NON-STREAMING MODE (stream=False)")
    print("-" * 70)
    print("Response appears all at once after generation completes:\n")

    try:
        non_streaming_chat_completion(test_prompt)
    except Exception as e:
        print(f"Error: {e}")

    print("="*70)
    print("\nKEY DIFFERENCES:")
    print("  • Streaming: See tokens as generated (real-time feedback)")
    print("  • Non-streaming: Wait for complete response (simpler code)")
    print("  • Both: Same total tokens, same cost, same model")
    print("="*70)
