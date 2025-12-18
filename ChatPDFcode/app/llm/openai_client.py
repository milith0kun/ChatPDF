"""
OpenAI Client
Handles communication with OpenAI API for GPT-4 and GPT-4 Vision
"""

import json
from typing import List, Dict, Any, Optional, AsyncGenerator

from openai import AsyncOpenAI
from tenacity import retry, stop_after_attempt, wait_exponential

from app.config import settings
from app.llm.prompts import build_context_prompt


class OpenAIClient:
    """
    Async client for OpenAI API.
    Supports text generation and vision analysis.
    """
    
    def __init__(self):
        self._client = None
    
    @property
    def client(self) -> AsyncOpenAI:
        """Lazy load the OpenAI client."""
        if self._client is None:
            self._client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
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
        Generate a response using GPT-4.
        
        Args:
            system_prompt: System role instructions
            context: Retrieved document context
            query: User's question
            chat_history: Previous conversation messages
            model: Model to use (defaults to settings)
            max_tokens: Maximum response tokens
            temperature: Response creativity (0-1)
            
        Returns:
            Dict with 'answer' and optional 'confidence'
        """
        model = model or settings.LLM_MODEL
        max_tokens = max_tokens or settings.LLM_MAX_TOKENS
        temperature = temperature if temperature is not None else settings.LLM_TEMPERATURE
        
        # Build messages
        messages = [{"role": "system", "content": system_prompt}]
        
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
        
        # Call OpenAI API
        response = await self.client.chat.completions.create(
            model=model,
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature
        )
        
        answer = response.choices[0].message.content
        
        return {
            "answer": answer,
            "model": model,
            "tokens_used": response.usage.total_tokens if response.usage else None
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
        
        messages = [{"role": "system", "content": system_prompt}]
        
        if chat_history:
            for msg in chat_history[-10:]:
                messages.append({
                    "role": msg.get("role", "user"),
                    "content": msg.get("content", "")
                })
        
        user_message = build_context_prompt(context, query)
        messages.append({"role": "user", "content": user_message})
        
        stream = await self.client.chat.completions.create(
            model=model,
            messages=messages,
            max_tokens=settings.LLM_MAX_TOKENS,
            temperature=settings.LLM_TEMPERATURE,
            stream=True
        )
        
        async for chunk in stream:
            if chunk.choices[0].delta.content:
                yield json.dumps({
                    "type": "text",
                    "content": chunk.choices[0].delta.content
                })
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10)
    )
    async def analyze_image(
        self,
        image_base64: str,
        prompt: str,
        context: str = "",
        model: str = None
    ) -> str:
        """
        Analyze an image using GPT-4 Vision.
        
        Args:
            image_base64: Base64 encoded image
            prompt: Analysis instructions
            context: Surrounding text context
            
        Returns:
            Analysis description
        """
        model = model or settings.VISION_MODEL
        
        messages = [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": prompt
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/png;base64,{image_base64}",
                            "detail": "high"
                        }
                    }
                ]
            }
        ]
        
        response = await self.client.chat.completions.create(
            model=model,
            messages=messages,
            max_tokens=1000
        )
        
        return response.choices[0].message.content
    
    async def count_tokens(self, text: str, model: str = None) -> int:
        """
        Count tokens in a text string.
        Uses tiktoken for accurate counting.
        """
        import tiktoken
        
        model = model or settings.LLM_MODEL
        try:
            encoding = tiktoken.encoding_for_model(model)
        except KeyError:
            encoding = tiktoken.get_encoding("cl100k_base")
        
        return len(encoding.encode(text))


# Global instance
openai_client = OpenAIClient()
