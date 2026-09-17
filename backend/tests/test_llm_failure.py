import pytest
from unittest.mock import MagicMock, patch
from services.llm_service import llm_service, AllLLMProvidersFailedError
from core.config import settings

@pytest.mark.anyio
async def test_llm_service_failure_raises_exception():
    # Assert settings.ALLOW_MOCK_FALLBACK is False by default
    assert settings.ALLOW_MOCK_FALLBACK is False

    # Mock Gemini Client models.generate_content to raise an Exception
    mock_gemini_generate = MagicMock(side_effect=Exception("Gemini mock error"))
    
    # Mock Groq Client completions.create to raise an Exception
    mock_groq_create = MagicMock(side_effect=Exception("Groq mock error"))
    
    # We patch OpenAI chat completions create inside services.llm_service
    # since it's imported dynamically as "from openai import OpenAI"
    with patch("services.llm_service.genai.Client") as mock_genai, \
         patch("services.llm_service.Groq") as mock_groq_cls, \
         patch("openai.OpenAI") as mock_openai_cls:
         
        # Set up OpenRouter mock failure
        mock_openai_instance = MagicMock()
        mock_openai_cls.return_value = mock_openai_instance
        mock_openai_instance.chat.completions.create.side_effect = Exception("OpenRouter mock error")

        # Temporarily swap service attributes
        old_gemini = llm_service._gemini
        old_groq = llm_service._groq
        
        llm_service._gemini = MagicMock()
        llm_service._gemini.models.generate_content = mock_gemini_generate
        
        llm_service._groq = MagicMock()
        llm_service._groq.chat.completions.create = mock_groq_create

        try:
            # Expecting AllLLMProvidersFailedError to be raised
            with pytest.raises(AllLLMProvidersFailedError) as exc_info:
                await llm_service.generate("Test prompt")
            
            assert "All LLM providers" in str(exc_info.value) or "All providers" in str(exc_info.value)
        finally:
            # Restore service attributes
            llm_service._gemini = old_gemini
            llm_service._groq = old_groq
