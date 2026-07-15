#!/usr/bin/env python3
"""
Remote Ollama API Example
========================

This script demonstrates how to use the Ollama AI model server
running on the Hostinger VPS remotely.

Server Details:
- IP Address: 72.61.176.37
- Port: 11434
- WebUI: http://72.61.176.37:8080
- Current Model: llama3.2 (3.2B parameters)

Prerequisites:
- Python 3.6+
- requests library: pip install requests
- ollama library (optional): pip install ollama

Usage:
    python3 ollama_remote_example.py
"""

import json
import time
from typing import Any, Dict, Generator, List, Optional

import requests

# ============================================================================
# CONFIGURATION
# ============================================================================

OLLAMA_URL = "http://72.61.176.37:11434"
MODEL_NAME = "llama3.2"
TIMEOUT = 30  # seconds for API calls

# Optional: Add authentication if configured
HEADERS = {"Content-Type": "application/json", "User-Agent": "Ollama Remote Client/1.0"}

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================


def make_request(method: str, endpoint: str, data: Optional[Dict] = None) -> Dict:
    """
    Make an HTTP request to the Ollama API with error handling.

    Args:
        method: HTTP method (GET, POST, etc.)
        endpoint: API endpoint (e.g., '/api/generate')
        data: Optional JSON data for POST requests

    Returns:
        JSON response as dictionary

    Raises:
        requests.exceptions.RequestException: On network errors
        ValueError: On invalid response or API errors
    """
    url = f"{OLLAMA_URL}{endpoint}"

    try:
        if method.upper() == "GET":
            response = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
        elif method.upper() == "POST":
            response = requests.post(url, headers=HEADERS, json=data, timeout=TIMEOUT)
        else:
            raise ValueError(f"Unsupported HTTP method: {method}")

        response.raise_for_status()

        # Handle empty responses
        if response.status_code == 204:
            return {}

        return response.json()

    except requests.exceptions.Timeout:
        raise TimeoutError(f"Request to {endpoint} timed out after {TIMEOUT} seconds")
    except requests.exceptions.RequestException as e:
        raise ConnectionError(f"Network error connecting to Ollama API: {e}")
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON response from API: {e}")


def stream_response_generator(endpoint: str, data: Dict) -> Generator[str, None, None]:
    """
    Stream responses from Ollama API.

    Args:
        endpoint: API endpoint (e.g., '/api/generate')
        data: JSON data for the request

    Yields:
        Chunks of the response as they arrive
    """
    url = f"{OLLAMA_URL}{endpoint}"
    data["stream"] = True

    try:
        with requests.post(
            url, headers=HEADERS, json=data, stream=True, timeout=TIMEOUT
        ) as response:
            response.raise_for_status()

            for line in response.iter_lines():
                if line:
                    try:
                        chunk = json.loads(line.decode("utf-8"))
                        if "response" in chunk:
                            yield chunk["response"]
                        if chunk.get("done", False):
                            break
                    except json.JSONDecodeError:
                        # Skip invalid JSON lines
                        continue

    except requests.exceptions.RequestException as e:
        raise ConnectionError(f"Error during streaming: {e}")


# ============================================================================
# API WRAPPER FUNCTIONS
# ============================================================================


def check_health() -> Dict:
    """Check if Ollama API is accessible and get version info."""
    return make_request("GET", "/api/version")


def list_models() -> List[Dict]:
    """List all available models on the server."""
    response = make_request("GET", "/api/tags")
    return response.get("models", [])


def get_model_info(model_name: str = MODEL_NAME) -> Dict:
    """Get detailed information about a specific model."""
    return make_request("POST", "/api/show", {"name": model_name})


def generate_text(
    prompt: str,
    model: str = MODEL_NAME,
    system_prompt: Optional[str] = None,
    stream: bool = False,
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
) -> Any:
    """
    Generate text using the specified model.

    Args:
        prompt: The input prompt
        model: Model name (default: llama3.2)
        system_prompt: Optional system prompt for context
        stream: Whether to stream the response
        temperature: Controls randomness (0.0-1.0)
        max_tokens: Maximum tokens to generate

    Returns:
        Full response dict if not streaming, otherwise generator
    """
    data = {"model": model, "prompt": prompt, "stream": stream}

    # Add optional parameters
    if system_prompt:
        data["system"] = system_prompt
    if temperature is not None:
        data.setdefault("options", {})["temperature"] = temperature
    if max_tokens is not None:
        data.setdefault("options", {})["num_predict"] = max_tokens

    if stream:
        return stream_response_generator("/api/generate", data)
    else:
        return make_request("POST", "/api/generate", data)


def chat(
    messages: List[Dict[str, str]],
    model: str = MODEL_NAME,
    stream: bool = False,
    temperature: Optional[float] = None,
) -> Any:
    """
    Have a conversation with the model.

    Args:
        messages: List of message dicts with 'role' and 'content'
                  Example: [{"role": "user", "content": "Hello"}]
        model: Model name (default: llama3.2)
        stream: Whether to stream the response
        temperature: Controls randomness (0.0-1.0)

    Returns:
        Chat response
    """
    data = {"model": model, "messages": messages, "stream": stream}

    if temperature is not None:
        data.setdefault("options", {})["temperature"] = temperature

    if stream:
        return stream_response_generator("/api/chat", data)
    else:
        return make_request("POST", "/api/chat", data)


def get_embeddings(text: str, model: str = MODEL_NAME) -> List[float]:
    """
    Get embeddings for a piece of text.

    Args:
        text: Input text to embed
        model: Model name (default: llama3.2)

    Returns:
        List of embedding values
    """
    response = make_request("POST", "/api/embeddings", {"model": model, "prompt": text})
    return response.get("embedding", [])


# ============================================================================
# EXAMPLE USAGE FUNCTIONS
# ============================================================================


def example_health_check():
    """Example: Check server health and version."""
    print("=" * 60)
    print("EXAMPLE 1: Health Check")
    print("=" * 60)

    try:
        health = check_health()
        print(f"✅ Ollama API is accessible")
        print(f"   Version: {health.get('version', 'unknown')}")
        print(f"   URL: {OLLAMA_URL}")
    except Exception as e:
        print(f"❌ Health check failed: {e}")
        return False

    return True


def example_list_models():
    """Example: List all available models."""
    print("\n" + "=" * 60)
    print("EXAMPLE 2: List Available Models")
    print("=" * 60)

    try:
        models = list_models()
        if models:
            print(f"📚 Found {len(models)} model(s):")
            for model in models:
                size_gb = model.get("size", 0) / 1024**3
                print(f"   • {model.get('name', 'unknown')}")
                print(f"     Size: {size_gb:.1f} GB")
                print(f"     Modified: {model.get('modified_at', 'unknown')[:10]}")
        else:
            print("⚠ No models found on server")
    except Exception as e:
        print(f"❌ Failed to list models: {e}")


def example_text_generation():
    """Example: Generate text with different parameters."""
    print("\n" + "=" * 60)
    print("EXAMPLE 3: Text Generation")
    print("=" * 60)

    # Example 3a: Simple generation
    print("\n3a. Simple text generation:")
    prompt = "Explain quantum computing in one sentence."

    try:
        start_time = time.time()
        response = generate_text(prompt, stream=False)
        elapsed = time.time() - start_time

        if "response" in response:
            print(f"   Prompt: {prompt}")
            print(f"   Response: {response['response']}")
            print(
                f"   Time: {elapsed:.2f}s, Tokens: {response.get('eval_count', 'N/A')}"
            )
        else:
            print(f"   ❌ Unexpected response format: {response}")

    except Exception as e:
        print(f"   ❌ Generation failed: {e}")

    # Example 3b: With system prompt
    print("\n3b. With system prompt:")
    system_prompt = "You are a helpful science teacher explaining complex topics to high school students."
    user_prompt = "What is photosynthesis?"

    try:
        response = generate_text(
            prompt=user_prompt, system_prompt=system_prompt, temperature=0.7
        )

        if "response" in response:
            print(f"   System: {system_prompt}")
            print(f"   User: {user_prompt}")
            print(f"   Response: {response['response'][:200]}...")
    except Exception as e:
        print(f"   ❌ Generation with system prompt failed: {e}")

    # Example 3c: Streaming
    print("\n3c. Streaming response:")
    stream_prompt = "Count from 1 to 5:"

    try:
        print(f"   Prompt: {stream_prompt}")
        print("   Response (streaming): ", end="", flush=True)

        start_time = time.time()
        for chunk in generate_text(stream_prompt, stream=True):
            print(chunk, end="", flush=True)
        elapsed = time.time() - start_time

        print(f"\n   Stream completed in {elapsed:.2f}s")

    except Exception as e:
        print(f"\n   ❌ Streaming failed: {e}")


def example_chat_conversation():
    """Example: Have a conversation with the model."""
    print("\n" + "=" * 60)
    print("EXAMPLE 4: Chat Conversation")
    print("=" * 60)

    conversation = [
        {"role": "user", "content": "What's the weather like today?"},
        {
            "role": "assistant",
            "content": "I'm an AI and don't have real-time weather data. Where are you located?",
        },
        {"role": "user", "content": "I'm in Paris, France."},
    ]

    try:
        print("Conversation:")
        for msg in conversation:
            print(f"   {msg['role'].title()}: {msg['content']}")

        print("\n   Generating response...")
        response = chat(conversation, temperature=0.8)

        if "message" in response:
            print(f"   Assistant: {response['message']['content']}")
            print(f"   Duration: {response.get('total_duration', 0) / 1e9:.2f}s")
    except Exception as e:
        print(f"   ❌ Chat failed: {e}")


def example_embeddings():
    """Example: Get embeddings for text."""
    print("\n" + "=" * 60)
    print("EXAMPLE 5: Text Embeddings")
    print("=" * 60)

    texts = [
        "Artificial intelligence is transforming industries.",
        "Machine learning algorithms can recognize patterns.",
        "The weather is sunny and warm today.",
    ]

    try:
        for i, text in enumerate(texts, 1):
            print(f"\n5.{i}. Text: '{text}'")

            start_time = time.time()
            embedding = get_embeddings(text)
            elapsed = time.time() - start_time

            if embedding:
                print(f"   Embedding length: {len(embedding)} dimensions")
                print(f"   First 5 values: {embedding[:5]}")
                print(f"   Time: {elapsed:.3f}s")
            else:
                print(f"   ❌ No embedding returned")

    except Exception as e:
        print(f"   ❌ Embeddings failed: {e}")


def example_error_handling():
    """Example: Demonstrate error handling."""
    print("\n" + "=" * 60)
    print("EXAMPLE 6: Error Handling")
    print("=" * 60)

    # Test 1: Invalid model name
    print("\n6a. Testing with invalid model:")
    try:
        response = generate_text("Hello", model="non_existent_model_123")
        print(f"   Unexpected success: {response}")
    except Exception as e:
        print(f"   ✅ Correctly caught error: {type(e).__name__}: {e}")

    # Test 2: Empty prompt
    print("\n6b. Testing with empty prompt:")
    try:
        response = generate_text("")
        print(f"   Response: {response.get('response', 'No response')}")
    except Exception as e:
        print(f"   Error: {e}")


def example_custom_use_case():
    """Example: Custom use case - QMS document analysis."""
    print("\n" + "=" * 60)
    print("EXAMPLE 7: Custom Use Case - QMS Document Analysis")
    print("=" * 60)

    qms_context = """
    Quality Management System (QMS) for Cannabis EU GMP compliance.
    Key requirements: Document control, Change management, CAPA, Training.
    """

    questions = [
        "What are the key components of a GMP-compliant QMS?",
        "How should document changes be managed?",
        "Explain CAPA in the context of cannabis production.",
    ]

    try:
        for i, question in enumerate(questions, 1):
            system_msg = f"You are a GMP consultant. Context: {qms_context}"

            print(f"\n7.{i}. Question: {question}")

            response = generate_text(
                prompt=question,
                system_prompt=system_msg,
                temperature=0.3,  # Lower temperature for more factual responses
            )

            if "response" in response:
                # Truncate long responses for display
                answer = response["response"]
                if len(answer) > 300:
                    answer = answer[:300] + "..."
                print(f"   Answer: {answer}")

    except Exception as e:
        print(f"   ❌ QMS analysis failed: {e}")


# ============================================================================
# MAIN EXECUTION
# ============================================================================


def run_all_examples():
    """Run all example functions."""
    print("\n" + "=" * 60)
    print("REMOTE OLLAMA API EXAMPLES")
    print("=" * 60)
    print(f"Server: {OLLAMA_URL}")
    print(f"Model: {MODEL_NAME}")
    print("=" * 60)

    # First check if server is accessible
    if not example_health_check():
        print("\n⚠ Server not accessible. Please check:")
        print(f"  1. Is the VPS running? (72.61.176.37)")
        print(
            f"  2. Is Ollama service running? (ssh ollama-vps 'systemctl status ollama')"
        )
        print(f"  3. Is port 11434 open? (ufw allow 11434/tcp)")
        return

    # Run other examples
    example_list_models()
    example_text_generation()
    example_chat_conversation()
    example_embeddings()
    example_error_handling()
    example_custom_use_case()

    print("\n" + "=" * 60)
    print("EXAMPLES COMPLETE")
    print("=" * 60)
    print("\n📖 Quick Reference Commands:")
    print(f"  Test API: curl {OLLAMA_URL}/api/version")
    print(f"  List models: curl {OLLAMA_URL}/api/tags")
    print(f"  Web Interface: http://72.61.176.37:8080")
    print(f"  SSH Access: ssh ollama-vps")
    print("\n🚀 Ready to build your AI applications!")


# ============================================================================
# ADVANCED USAGE - REUSABLE CLIENT CLASS
# ============================================================================


class OllamaRemoteClient:
    """Advanced client for Ollama remote API with connection pooling and retries."""

    def __init__(self, base_url: str = OLLAMA_URL, max_retries: int = 3):
        self.base_url = base_url.rstrip("/")
        self.max_retries = max_retries
        self.session = requests.Session()
        self.session.headers.update(HEADERS)

    def _request_with_retry(
        self, method: str, endpoint: str, data: Optional[Dict] = None
    ) -> Dict:
        """Make request with exponential backoff retry."""
        url = f"{self.base_url}{endpoint}"

        for attempt in range(self.max_retries):
            try:
                if method.upper() == "GET":
                    response = self.session.get(url, timeout=TIMEOUT)
                elif method.upper() == "POST":
                    response = self.session.post(url, json=data, timeout=TIMEOUT)
                else:
                    raise ValueError(f"Unsupported method: {method}")

                response.raise_for_status()
                return response.json()

            except (requests.exceptions.RequestException, ConnectionError) as e:
                if attempt == self.max_retries - 1:
                    raise

                wait_time = 2**attempt  # Exponential backoff
                print(
                    f"⚠ Request failed (attempt {attempt + 1}/{self.max_retries}), "
                    f"retrying in {wait_time}s..."
                )
                time.sleep(wait_time)

        raise ConnectionError(f"All {self.max_retries} retries failed")

    def batch_generate(self, prompts: List[str], model: str = MODEL_NAME) -> List[Dict]:
        """Generate text for multiple prompts."""
        results = []
        for prompt in prompts:
            try:
                result = self._request_with_retry(
                    "POST",
                    "/api/generate",
                    {"model": model, "prompt": prompt, "stream": False},
                )
                results.append(result)
            except Exception as e:
                results.append({"error": str(e), "prompt": prompt})

        return results

    def close(self):
        """Close the session."""
        self.session.close()


# ============================================================================
# SCRIPT ENTRY POINT
# ============================================================================

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Remote Ollama API Examples")
    parser.add_argument("--test", action="store_true", help="Run quick connection test")
    parser.add_argument("--prompt", type=str, help="Generate text for a custom prompt")
    parser.add_argument("--chat", type=str, help="Start a chat with initial message")
    parser.add_argument("--embed", type=str, help="Get embeddings for text")

    args = parser.parse_args()

    if args.test:
        # Quick test mode
        try:
            health = check_health()
            models = list_models()
            print(f"✅ Connection successful")
            print(f"   Version: {health.get('version')}")
            print(f"   Models: {len(models)} available")
        except Exception as e:
            print(f"❌ Test failed: {e}")

    elif args.prompt:
        # Generate text for custom prompt
        try:
            response = generate_text(args.prompt)
            print(f"Response: {response.get('response', 'No response')}")
        except Exception as e:
            print(f"Error: {e}")

    elif args.chat:
        # Start chat
        try:
            response = chat([{"role": "user", "content": args.chat}])
            print(
                f"Assistant: {response.get('message', {}).get('content', 'No response')}"
            )
        except Exception as e:
            print(f"Error: {e}")

    elif args.embed:
        # Get embeddings
        try:
            embedding = get_embeddings(args.embed)
            print(f"Embedding dimensions: {len(embedding)}")
            print(f"Sample values: {embedding[:5]}")
        except Exception as e:
            print(f"Error: {e}")

    else:
        # Run all examples
        run_all_examples()
