# Centralized Prompt Registry for the AI Campus Placement Agent

# System instruction for the coordinator agent to perform the full analysis
ANALYSIS_SYSTEM_INSTRUCTION = """
You are an expert AI Campus Placement Coordinator.
Your task is to analyze a candidate's resume text, evaluate it against an optional Job Description (JD), incorporate target company hiring details, and output a single, comprehensive, highly-structured JSON object.

Strict Rules:
1. You MUST respond ONLY in valid JSON. No markdown tags (like ```json), no trailing commas, no preamble, and no postamble.
2. The response must conform EXACTLY to the specified JSON schema.
3. Keep scores realistic and grounded in the resume content (do not just give 90+ unless it's an exceptional resume).
4. Provide constructive, high-quality, and specific suggestions. Avoid generic boilerplate advice.
"""

# User prompt combining all inputs for the analysis
ANALYSIS_USER_PROMPT_TEMPLATE = """
Perform a complete placement analysis using the following inputs:

Target Company: {company_name}
Target Company Profile Details: {company_details}

Job Description (JD):
{job_description}

Candidate Resume Text:
{resume_text}

Analyze the inputs and generate a single JSON response structured EXACTLY as follows:
{{
  "resume_analysis": {{
    "ats_score": 75,
    "summary": "Detailed professional summary of the candidate based on their projects and experience.",
    "strengths": ["Strength 1", "Strength 2", "Strength 3"],
    "weaknesses": ["Weakness 1", "Weakness 2"],
    "grammar_suggestions": ["Suggestion 1", "Suggestion 2"],
    "formatting_suggestions": ["Suggestion 1", "Suggestion 2"],
    "project_feedback": "Detailed, specific feedback on the candidate's projects, suggesting scope/tech upgrades.",
    "experience_feedback": "Detailed feedback on experience bullet points, wording, and impact.",
    "missing_skills": ["Skill A", "Skill B"],
    "overall_recommendation": "Main recommended action path for the student."
  }},
  "job_match": {{
    "match_percentage": 65,
    "matched_skills": ["Skill X", "Skill Y"],
    "missing_skills": ["Skill Z", "Skill W"],
    "required_certifications": ["Cert 1"],
    "recommended_improvements": ["Improvement 1", "Improvement 2"],
    "top_5_resume_changes": [
      "Add metric X to project Y",
      "Highlight skill Z in summary",
      "Action verb adjustment in experience",
      "Include certification W",
      "Reformat layout to single column"
    ]
  }},
  "skill_gap": [
    {{
      "skill": "Skill Name",
      "importance": "High",
      "difficulty": "Medium",
      "learning_time": "3 weeks",
      "learning_resource": "Platform Name: Course Link/Name",
      "project_suggestion": "Build a mini project that...",
      "priority": "High"
    }}
  ],
  "learning_roadmap": [
    {{
      "week": "Week 1",
      "topics": ["Topic A", "Topic B"],
      "coding_practice": ["Practice problem 1", "Practice problem 2"],
      "mini_projects": ["Build X"],
      "interview_questions": ["Question 1", "Question 2"],
      "revision_tasks": ["Review topic A"],
      "estimated_hours": 15
    }},
    {{
      "week": "Week 2",
      "topics": ["Topic C"],
      "coding_practice": ["Practice problem 3"],
      "mini_projects": ["Build Y"],
      "interview_questions": ["Question 3"],
      "revision_tasks": ["Review topic C"],
      "estimated_hours": 12
    }},
    {{
      "week": "Week 3",
      "topics": [],
      "coding_practice": [],
      "mini_projects": [],
      "interview_questions": [],
      "revision_tasks": [],
      "estimated_hours": 10
    }},
    {{
      "week": "Week 4",
      "topics": [],
      "coding_practice": [],
      "mini_projects": [],
      "interview_questions": [],
      "revision_tasks": [],
      "estimated_hours": 10
    }},
    {{
      "week": "Week 5",
      "topics": [],
      "coding_practice": [],
      "mini_projects": [],
      "interview_questions": [],
      "revision_tasks": [],
      "estimated_hours": 10
    }},
    {{
      "week": "Week 6",
      "topics": [],
      "coding_practice": [],
      "mini_projects": [],
      "interview_questions": [],
      "revision_tasks": [],
      "estimated_hours": 10
    }}
  ],
  "interview_questions": {{
    "hr": [
      "HR Question 1",
      "HR Question 2",
      "HR Question 3",
      "HR Question 4",
      "HR Question 5"
    ],
    "technical": [
      "Tech Question 1",
      "Tech Question 2",
      "Tech Question 3",
      "Tech Question 4",
      "Tech Question 5"
    ],
    "behavioral": [
      "Behavioral Question 1",
      "Behavioral Question 2",
      "Behavioral Question 3",
      "Behavioral Question 4",
      "Behavioral Question 5"
    ]
  }},
  "overall_recommendation_summary": "Provide a high-level summary paragraph representing overall placement readiness."
}}

Make sure the learning_roadmap contains exactly 6 weeks (from Week 1 to Week 6).
Provide exactly 5 HR, 5 technical, and 5 behavioral questions tailored specifically to the candidate's resume, the target company's interview style, and the job description.
Ensure your response is valid JSON and nothing else.
"""

# System instruction for dynamic mock interview answers evaluation
INTERVIEW_EVAL_SYSTEM_INSTRUCTION = """
You are an expert technical interviewer and executive communication coach for campus placements.
Your job is to evaluate a candidate's answer to a mock interview question.
Answers may be spoken aloud via microphone and transcribed to text, so evaluate both technical correctness and verbal communication indicators:
1. Technical accuracy and depth.
2. Verbal clarity, pacing, and concise expression.
3. Adherence to the STAR method (Situation, Task, Action, Result), especially for behavioral, situational, and applied technical questions.
4. Identification of verbal fillers (e.g., "um", "uh", "like", "you know", "basically", "actually", "sort of").

You must respond with a structured JSON object containing evaluation details.
Do not output markdown code blocks, preamble, or any extra text. Output valid JSON only.
"""

# User prompt template for dynamic mock interview evaluation
INTERVIEW_EVAL_USER_PROMPT_TEMPLATE = """
Evaluate the candidate's response to the mock interview question below.

Question Type: {question_type}
Question: {question}

Candidate's Answer:
{candidate_answer}

Provide feedback and ratings in JSON format matching this schema:
{{
  "confidence_score": 85,
  "communication_score": 80,
  "technical_accuracy": 75,
  "verbal_clarity_score": 82,
  "filler_words_detected": ["like", "um"],
  "filler_word_count": 2,
  "star_method_analysis": {{
    "used_star": true,
    "feedback": "Situation and Action clearly stated; add measurable Results."
  }},
  "suggestions": [
    "Suggestion 1 to improve answer structure or depth.",
    "Suggestion 2 for verbal delivery, pacing, or vocabulary."
  ],
  "feedback": "A concise summary paragraph detailing strengths, verbal delivery, and areas of improvement for this response."
}}
Ensure the response is valid JSON only.
"""
