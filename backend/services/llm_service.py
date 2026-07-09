from google import genai
from groq import Groq

from core.config import settings


class LLMService:


    def __init__(self):

        self.gemini = genai.Client(
            api_key=settings.GEMINI_API_KEY
        )


        self.groq = Groq(
            api_key=settings.GROQ_API_KEY
        )



    async def generate(
        self,
        prompt: str
    ):


        try:

            response = (
                self.gemini.models.generate_content(
                    model="gemini-2.0-flash",
                    contents=prompt
                )
            )

            return response.text


        except Exception as e:

            print(
                "Gemini failed, using Groq:",
                e
            )


            response = (
                self.groq.chat.completions.create(

                    model="llama-3.3-70b-versatile",

                    messages=[
                        {
                            "role":"user",
                            "content":prompt
                        }
                    ]

                )
            )


            return (
                response
                .choices[0]
                .message
                .content
            )



llm_service = LLMService()