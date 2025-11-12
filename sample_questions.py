"""
Sample question pairs for the survey.

Copy this structure to app.py and replace the QUESTION_PAIRS list with your actual questions.
Each entry needs: id, prompt, question_a, and question_b
"""

SAMPLE_QUESTIONS = [
    {
        "id": 1,
        "prompt": "Create a question about artificial intelligence for a general audience.",
        "question_a": "What is artificial intelligence and how does it work?",
        "question_b": "Can you explain the fundamental principles behind AI systems?"
    },
    {
        "id": 2,
        "prompt": "Write a question about climate change for high school students.",
        "question_a": "How does human activity contribute to global warming?",
        "question_b": "What are the main causes and effects of climate change?"
    },
    {
        "id": 3,
        "prompt": "Ask about healthy eating habits in simple terms.",
        "question_a": "What foods should I eat to stay healthy?",
        "question_b": "How can I improve my diet to be healthier?"
    },
    {
        "id": 4,
        "prompt": "Inquire about exercise for beginners.",
        "question_a": "What exercises are good for someone just starting out?",
        "question_b": "How should I begin an exercise routine as a beginner?"
    },
    {
        "id": 5,
        "prompt": "Ask about time management for students.",
        "question_a": "How can I manage my time better as a student?",
        "question_b": "What are effective time management strategies for studying?"
    },
    # Add 25 more question pairs below...
    # Template:
    # {
    #     "id": N,
    #     "prompt": "Your prompt here - what you're asking the questions to accomplish",
    #     "question_a": "First version of the question",
    #     "question_b": "Second version of the question"
    # },
]

# Instructions:
# 1. Create 30 total question pairs (5 samples provided above)
# 2. Make sure each id is unique (1-30)
# 3. The prompt explains what the question should accomplish
# 4. question_a and question_b are two different ways to ask about the topic
# 5. Copy the completed list to app.py, replacing the QUESTION_PAIRS variable

