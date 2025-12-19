"""
Anthropic Client
Handles communication with Claude API for text generation
"""

import json
from typing import List, Dict, Any, Optional, AsyncGenerator

from anthropic import AsyncAnthropic
from tenacity import retry, stop_after_attempt, wait_exponential

from app.config import settings
from app.llm.prompts import build_context_prompt


class AnthropicClient:
    """
    Async client for Anthropic Claude API.
    Used for text generation (cheaper than OpenAI).
    """
    
    def __init__(self):
        self._client = None
    
    @property
    def client(self) -> AsyncAnthropic:
        """Lazy load the Anthropic client."""
        if self._client is None:
            self._client = AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
        return self._client
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10)
    )
    async def generate_response(
        self,
        system_prompt: str,
        context: str,
        query: str,
        chat_history: List[Dict[str, Any]] = None,
        model: str = None,
        max_tokens: int = None,
        temperature: float = None
    ) -> Dict[str, Any]:
        """
        Generate a response using Claude.
        
        Args:
            system_prompt: System role instructions
            context: Retrieved document context
            query: User's question
            chat_history: Previous conversation messages
            model: Model to use (defaults to settings)
            max_tokens: Maximum response tokens
            temperature: Response creativity (0-1)
            
        Returns:
            Dict with 'answer' and optional metadata
        """
        model = model or settings.LLM_MODEL
        max_tokens = max_tokens or settings.LLM_MAX_TOKENS
        temperature = temperature if temperature is not None else settings.LLM_TEMPERATURE
        
        # Build messages
        messages = []
        
        # Add chat history (last 10 messages for context)
        if chat_history:
            for msg in chat_history[-10:]:
                messages.append({
                    "role": msg.get("role", "user"),
                    "content": msg.get("content", "")
                })
        
        # Add current context and query
        user_message = build_context_prompt(context, query)
        messages.append({"role": "user", "content": user_message})
        
        # Call Claude API
        response = await self.client.messages.create(
            model=model,
            system=system_prompt,
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature
        )
        
        answer = response.content[0].text
        
        # Token usage info
        input_tokens = response.usage.input_tokens if response.usage else 0
        output_tokens = response.usage.output_tokens if response.usage else 0
        
        return {
            "answer": answer,
            "model": model,
            "provider": "anthropic",
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": input_tokens + output_tokens
        }
    
    async def generate_response_stream(
        self,
        system_prompt: str,
        context: str,
        query: str,
        chat_history: List[Dict[str, Any]] = None,
        model: str = None
    ) -> AsyncGenerator[str, None]:
        """
        Generate a streaming response.
        
        Yields JSON chunks with type and content.
        """
        model = model or settings.LLM_MODEL
        
        messages = []
        
        if chat_history:
            for msg in chat_history[-10:]:
                messages.append({
                    "role": msg.get("role", "user"),
                    "content": msg.get("content", "")
                })
        
        user_message = build_context_prompt(context, query)
        messages.append({"role": "user", "content": user_message})
        
        async with self.client.messages.stream(
            model=model,
            system=system_prompt,
            messages=messages,
            max_tokens=settings.LLM_MAX_TOKENS,
            temperature=settings.LLM_TEMPERATURE
        ) as stream:
            async for text in stream.text_stream:
                yield json.dumps({
                    "type": "text",
                    "content": text
                })


# Global instance
anthropic_client = AnthropicClient()
