import google.generativeai as genai
import logging
from typing import Optional

logger = logging.getLogger(__name__)

class AIService:
    def __init__(self, api_key: str, model_name: str = "gemini-2.0-flash-lite"):
        self.api_key = api_key
        self.model_name = model_name
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel(model_name)
    
    def generate_message(self, topic: str, min_length: int = 300, max_length: int = 400) -> Optional[str]:
        """Generate a message about the given topic."""
        try:
            prompt = f"""
Write a brief message ({min_length}-{max_length} characters) about: "{topic}"

Guidelines:
- Write from the point of view of a senior software engineer
- Be informative and engaging
- Use a conversational but professional tone
- Include technical insights where relevant
- Keep it concise and impactful
- Do not use quotes or special formatting
- Write as if you're sharing your thoughts on the topic

Topic: {topic}
"""
            
            response = self.model.generate_content(prompt)
            
            if response.text:
                message = response.text.strip()
                
                # Basic validation
                if len(message) < min_length * 0.8:  # Allow 20% tolerance
                    logger.warning(f"Generated message too short: {len(message)} characters")
                elif len(message) > max_length * 1.2:  # Allow 20% tolerance
                    logger.warning(f"Generated message too long: {len(message)} characters")
                    message = message[:max_length] + "..."
                
                return message
            else:
                logger.error("Empty response from AI service")
                return None
                
        except Exception as e:
            logger.error(f"Error generating message: {str(e)}")
            return None
    
    def is_appropriate_topic(self, topic: str) -> bool:
        """Check if the topic is appropriate for content generation."""
        # Simple content filtering - can be expanded
        inappropriate_keywords = [
            'hate', 'violence', 'illegal', 'harmful', 'dangerous',
            'porn', 'sex', 'drug', 'weapon', 'bomb', 'terror'
        ]
        
        topic_lower = topic.lower()
        return not any(keyword in topic_lower for keyword in inappropriate_keywords)
