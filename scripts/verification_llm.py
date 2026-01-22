import unittest
from unittest.mock import patch, MagicMock
import os
import json

# Set dummy API key for testing
os.environ['GOOGLE_API_KEY'] = 'test_key'

from simple_scoring import compute_simple_score

class TestGenAIScoring(unittest.TestCase):
    @patch('simple_scoring.genai.GenerativeModel')
    def test_scoring_success(self, MockModel):
        # Setup mock
        mock_instance = MockModel.return_value
        mock_response = MagicMock()
        mock_response.text = '{"score": 85, "reasoning": "Relevant content about Python"}'
        mock_instance.generate_content.return_value = mock_response

        # Mock get_video_details to avoid network call
        with patch('simple_scoring.get_video_details') as mock_details:
            mock_details.return_value = {
                'title': 'Python Tutorial', 
                'description': 'Learn Python programming language basic to advanced.'
            }
            
            # Execute
            score = compute_simple_score('https://youtube.com/watch?v=123', 'Learn Python')
            
            # Verify
            self.assertEqual(score, 85)
            MockModel.assert_called_with('gemini-1.5-flash')
            mock_instance.generate_content.assert_called_once()

    @patch('simple_scoring.genai.GenerativeModel')
    def test_scoring_json_cleanup(self, MockModel):
        # Test handling of markdown code blocks in response
        mock_instance = MockModel.return_value
        mock_response = MagicMock()
        mock_response.text = '```json\n{"score": 42, "reasoning": "Somewhat relevant"}\n```'
        mock_instance.generate_content.return_value = mock_response

        with patch('simple_scoring.get_video_details') as mock_details:
            mock_details.return_value = {'title': 'Random', 'description': 'stuff'}
            
            score = compute_simple_score('https://youtube.com/watch?v=123', 'testing')
            self.assertEqual(score, 42)

if __name__ == '__main__':
    unittest.main()
