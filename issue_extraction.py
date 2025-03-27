# issue_extraction.py
from transformers import pipeline

classifier = pipeline("zero-shot-classification", model="facebook/bart-large-mnli")


CANDIDATE_LABELS = [
    "fast",        
    "understand",        
    "engagement",   
    "communication",  
    "knowledge",      
    "explanation",    
    "rude",   
    "organization",   
    "tone",           
    "preparation",    
    "responsiveness", 
    "technical issues", 
    "adaptability",
    "patience",
    "empathy",
    "motivation",
    "resourcefulness",
    "interaction",
    "clarification",
    "creativity",
    "confidence",
    "inclusivity",
    "feedback incorporation"
]

def extract_issues(text: str, candidate_labels=CANDIDATE_LABELS, threshold: float = 0.1) -> list:
    """
    Extract issues from the feedback text using zero-shot classification.

    Args:
        text (str): The input feedback text.
        candidate_labels (list): A list of candidate issue labels.
        threshold (float): Confidence threshold to consider a label valid.

    Returns:
        list: A list of dictionaries, each containing an issue and its confidence score.
    """
    result = classifier(text, candidate_labels)
    
    print("Raw classifier output:")
    print(result)
    
    issues = []
    for label, score in zip(result["labels"], result["scores"]):
        if score >= threshold:
            issues.append({"issue": label, "score": score})
    return issues

if __name__ == "__main__":
    test_text = "The tutor spoke too fast and didn't explain things well enough for me to understand. The session was also too short and I felt rushed."
    issues_found = extract_issues(test_text)
    print("Extracted Issues:")
    for issue in issues_found:
        print(f"{issue['issue']} (score: {issue['score']:.2f})")
