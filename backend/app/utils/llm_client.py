"""
LLM client wrapper.
Supports multiple LLM providers: OpenAI, Anthropic, and OpenAI-compatible third-party APIs.
Automatically detects the provider based on configuration and uses the corresponding SDK.
"""

import json
import re
from typing import Optional, Dict, Any, List

from ..config import Config


def _detect_provider(base_url: str, model: str) -> str:
    """
    Auto-detect LLM provider based on base_url and model name.

    Returns:
        "anthropic" | "openai"
    """
    base_lower = (base_url or "").lower()
    model_lower = (model or "").lower()

    if "anthropic" in base_lower or model_lower.startswith("claude"):
        return "anthropic"

    return "openai"


def _is_openai_new_model(model: str) -> bool:
    """
    Check whether the model uses the new OpenAI API parameters.
    These models require:
    - max_completion_tokens (instead of max_tokens)
    - developer role (instead of system)
    - No temperature support (only accepts the default value of 1)

    Includes:
    - o-series reasoning models: o1, o3, o4-mini, etc.
    - GPT-5 series: gpt-5, gpt-5.1, gpt-5.2, gpt-5.3, gpt-5.4, etc.
    """
    model_lower = (model or "").lower()
    # o1, o1-mini, o1-preview, o3, o3-mini, o4-mini etc.
    if re.match(r'^o[134]-', model_lower):
        return True
    # gpt-5, gpt-5.1, gpt-5.2, gpt-5.3-codex, gpt-5.4, gpt-5.4-pro etc.
    if re.match(r'^gpt-5', model_lower):
        return True
    return False


class LLMClient:
    """LLM client supporting OpenAI and Anthropic."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None
    ):
        self.api_key = api_key or Config.LLM_API_KEY
        self.base_url = base_url or Config.LLM_BASE_URL
        self.model = model or Config.LLM_MODEL_NAME

        if not self.api_key:
            raise ValueError("LLM_API_KEY not configured")

        self.provider = _detect_provider(self.base_url, self.model)
        self._client = None

    @property
    def client(self):
        """Lazy initialization of client"""
        if self._client is None:
            if self.provider == "anthropic":
                import anthropic
                self._client = anthropic.Anthropic(api_key=self.api_key)
            else:
                from openai import OpenAI
                self._client = OpenAI(
                    api_key=self.api_key,
                    base_url=self.base_url
                )
        return self._client

    def chat(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 4096,
        response_format: Optional[Dict] = None
    ) -> str:
        """
        Send chat request

        Args:
            messages: Message list
            temperature: Temperature parameter
            max_tokens: Maximum number of tokens
            response_format: Response format (e.g., JSON mode)

        Returns:
            Model response text
        """
        if self.provider == "anthropic":
            content = self._chat_anthropic(messages, temperature, max_tokens)
        else:
            content = self._chat_openai(messages, temperature, max_tokens, response_format)

        # Some models (e.g., MiniMax M2.5) include <think> reasoning content that needs to be removed
        content = re.sub(r'<think>[\s\S]*?</think>', '', content).strip()
        return content

    def _chat_openai(
        self,
        messages: List[Dict[str, str]],
        temperature: float,
        max_tokens: int,
        response_format: Optional[Dict]
    ) -> str:
        """OpenAI and compatible API call."""
        is_new = _is_openai_new_model(self.model)

        kwargs = {
            "model": self.model,
            "messages": messages,
        }

        if is_new:
            # o-series / GPT-5 series:
            # - Use max_completion_tokens (max_tokens is deprecated and incompatible)
            # - Temperature not supported (only accepts the default value of 1)
            # - system role is replaced by developer role
            kwargs["max_completion_tokens"] = max_tokens
            kwargs["messages"] = self._convert_system_to_developer(messages)
            # GPT-5.x supports response_format; earlier o-series models also support it
            if response_format:
                kwargs["response_format"] = response_format
        else:
            # gpt-4o, gpt-4o-mini, and other traditional models
            kwargs["temperature"] = temperature
            kwargs["max_tokens"] = max_tokens
            if response_format:
                kwargs["response_format"] = response_format

        response = self.client.chat.completions.create(**kwargs)
        return response.choices[0].message.content

    def _chat_anthropic(
        self,
        messages: List[Dict[str, str]],
        temperature: float,
        max_tokens: int
    ) -> str:
        """Anthropic Claude API call."""
        # Extract system messages from the message list
        system_text = ""
        user_messages = []
        for msg in messages:
            if msg["role"] == "system":
                system_text += msg["content"] + "\n"
            else:
                user_messages.append(msg)

        # Make sure there is at least one user message
        if not user_messages:
            user_messages = [{"role": "user", "content": ""}]

        # Anthropic requires alternating user/assistant messages; merge consecutive same-role messages
        user_messages = self._merge_consecutive_roles(user_messages)

        kwargs = {
            "model": self.model,
            "messages": user_messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }

        if system_text.strip():
            kwargs["system"] = system_text.strip()

        response = self.client.messages.create(**kwargs)
        return response.content[0].text

    @staticmethod
    def _convert_system_to_developer(messages: List[Dict[str, str]]) -> List[Dict[str, str]]:
        """Convert system role to developer role (for OpenAI o1+ reasoning models)."""
        converted = []
        for msg in messages:
            if msg["role"] == "system":
                converted.append({"role": "developer", "content": msg["content"]})
            else:
                converted.append(msg)
        return converted

    @staticmethod
    def _merge_consecutive_roles(messages: List[Dict[str, str]]) -> List[Dict[str, str]]:
        """Merge consecutive messages with the same role (Anthropic requires alternating user/assistant)."""
        if not messages:
            return messages
        merged = [messages[0].copy()]
        for msg in messages[1:]:
            if msg["role"] == merged[-1]["role"]:
                merged[-1]["content"] += "\n\n" + msg["content"]
            else:
                merged.append(msg.copy())
        return merged

    def chat_json(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.3,
        max_tokens: int = 4096
    ) -> Dict[str, Any]:
        """
        Send chat request and return JSON.

        Args:
            messages: Message list
            temperature: Temperature parameter
            max_tokens: Maximum number of tokens

        Returns:
            Parsed JSON object
        """
        if self.provider == "anthropic":
            # Anthropic does not support response_format; request JSON output in the prompt instead
            messages = [m.copy() for m in messages]
            if messages and messages[-1]["role"] == "user":
                messages[-1]["content"] += "\n\nPlease return pure JSON only, without markdown code block tags."
            response = self.chat(
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )
        else:
            # OpenAI models (including GPT-5.x and traditional models) all support response_format
            response = self.chat(
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                response_format={"type": "json_object"}
            )

        # Strip markdown code block tags
        cleaned_response = response.strip()
        cleaned_response = re.sub(r'^```(?:json)?\s*\n?', '', cleaned_response, flags=re.IGNORECASE)
        cleaned_response = re.sub(r'\n?```\s*$', '', cleaned_response)
        cleaned_response = cleaned_response.strip()

        try:
            return json.loads(cleaned_response)
        except json.JSONDecodeError:
            raise ValueError(f"LLM returned invalid JSON: {cleaned_response}")
