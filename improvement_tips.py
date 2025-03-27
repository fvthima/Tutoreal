# improvement_tips.py


improvement_mapping = {
    "fast": "Try slowing down and pausing for questions to ensure students keep up.",
    "understand": "Consider using simpler language and more examples to explain complex concepts.",
    "engagement": "Incorporate more interactive elements and ask engaging questions during the session.",
    "communication": "Focus on clear and concise communication to avoid misunderstandings.",
    "knowledge": "Deepen your subject knowledge by reviewing additional resources before sessions.",
    "explanation": "Break down complex ideas into smaller, manageable parts for better understanding.",
    "rude": "Maintain a warm, approachable tone to make students feel comfortable.",
    "organization": "Structure your session with clear objectives and transitions between topics.",
    "tone": "Ensure your tone is supportive and positive to encourage student participation.",
    "preparation": "Prepare well in advance with notes and relevant examples to guide the session.",
    "responsiveness": "Be attentive and responsive to student questions throughout the session.",
    "technical issues": "Double-check your technical setup and ensure a stable connection before starting.",
    "adaptability": "Adjust your teaching style based on real-time student feedback and different learning styles.",
    "patience": "Give students ample time to process information and ask questions without feeling rushed.",
    "empathy": "Show understanding of student challenges and offer supportive guidance.",
    "motivation": "Use positive reinforcement and set clear, achievable goals to keep students motivated.",
    "resourcefulness": "Incorporate diverse resources such as videos, diagrams, and practical examples.",
    "interaction": "Encourage active participation and interactive discussions to enhance engagement.",
    "clarification": "Regularly check for student understanding and clarify confusing points immediately.",
    "creativity": "Incorporate creative teaching methods to make the learning experience more engaging.",
    "confidence": "Boost student confidence by affirming their progress and encouraging risk-taking in learning.",
    "inclusivity": "Ensure your teaching approach is inclusive and caters to diverse learning needs.",
    "feedback incorporation": "Actively incorporate student feedback into your teaching strategies for continuous improvement."
}

def generate_improvement_tip(issues: list) -> str:
    """
    Generate a combined improvement tip based on the extracted issues.
    
    Args:
        issues (list): A list of dictionaries containing detected issues 
                       (each dictionary should have an 'issue' key).
    
    Returns:
        str: A concatenated string of improvement suggestions.
    """
    tips = []
    for issue_dict in issues:
        issue = issue_dict.get("issue")
        tip = improvement_mapping.get(issue)
        if tip:
            tips.append(tip)
    return " ".join(tips) if tips else "Great, no improvement suggestions needed."

if __name__ == "__main__":
    sample_issues = [
        {"issue": "pacing", "score": 0.75},
        {"issue": "clarity", "score": 0.65},
        {"issue": "engagement", "score": 0.55}
    ]
    improvement_tip = generate_improvement_tip(sample_issues)
    print("Improvement Tip:")
    print(improvement_tip)
