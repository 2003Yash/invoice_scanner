from typing import Any, Dict, List, Optional
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import BaseMessage, AIMessage, HumanMessage, SystemMessage
from langchain_core.outputs import ChatResult, ChatGeneration
from azure.ai.inference import ChatCompletionsClient
from azure.core.credentials import AzureKeyCredential
 
class AzureCohereLanguageModel(BaseChatModel):
    def __init__(
        self,
        endpoint: str,
        api_key: str,
        max_tokens: int = 2048,
        temperature: float = 0.8,
        top_p: float = 0.1,
        **kwargs: Any
    ):
        """
        Initialize Azure Cohere Language Model
       
        :param endpoint: Azure endpoint for Cohere
        :param api_key: Azure API key
        :param max_tokens: Maximum number of tokens to generate
        :param temperature: Sampling temperature
        :param top_p: Nucleus sampling parameter
        """
        super().__init__()
       
        # Create the Azure Cohere client
        self._client = ChatCompletionsClient(
            endpoint=endpoint,
            credential=AzureKeyCredential(api_key)
        )
       
        # Store generation parameters
        self._max_tokens = max_tokens
        self._temperature = temperature
        self._top_p = top_p
 
    def _convert_messages_to_azure_format(self, messages: List[BaseMessage]):
        """
        Convert LangChain messages to Azure Cohere message format
        """
        azure_messages = []
        for msg in messages:
            if isinstance(msg, HumanMessage):
                azure_messages.append({"role": "user", "content": msg.content})
            elif isinstance(msg, AIMessage):
                azure_messages.append({"role": "assistant", "content": msg.content})
            elif isinstance(msg, SystemMessage):
                azure_messages.append({"role": "system", "content": msg.content})
        return azure_messages
 
    def _generate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        **kwargs: Any
    ) -> ChatResult:
        """
        Generate response using Azure Cohere
        """
        # Prepare messages in Azure format
        azure_messages = self._convert_messages_to_azure_format(messages)
       
        # Prepare payload
        payload = {
            "messages": azure_messages,
            "max_tokens": self._max_tokens,
            "temperature": self._temperature,
            "top_p": self._top_p
        }
       
        # Call the Azure Cohere API
        response = self._client.complete(payload)
       
        # Convert response to ChatResult
        generations = [
            ChatGeneration(
                message=AIMessage(content=response.choices[0].message.content)
            )
        ]
       
        return ChatResult(generations=generations)
 
    async def _agenerate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        **kwargs: Any
    ) -> ChatResult:
        """
        Async generation method
        """
        return self._generate(messages, stop, **kwargs)
 
    @property
    def _llm_type(self) -> str:
        return "azure-cohere"