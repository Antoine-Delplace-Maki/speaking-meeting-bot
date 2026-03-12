"""Generates a randomized candidate persona using AI for each interview session."""

import json
import os
import random
from typing import Any, Dict

from dotenv import load_dotenv
from loguru import logger
from openai import OpenAI

load_dotenv()

_CULTURAL_REGIONS = [
    "East Asian", "South Asian", "Southeast Asian", "Middle Eastern",
    "West African", "East African", "North African",
    "Western European", "Eastern European", "Scandinavian",
    "Latin American", "Caribbean", "Pacific Islander",
    "Indigenous Australian", "Central Asian",
]

_EXPERIENCE_BANDS = [
    ("junior", 1, 3),
    ("mid-level", 3, 6),
    ("senior", 6, 10),
]

_GENDERS = ["MALE", "FEMALE", "NON-BINARY"]

_PERSONALITY_SEEDS = [
    "tends to over-explain and go on tangents",
    "very concise and direct, almost blunt",
    "uses lots of real-world analogies",
    "asks many clarifying questions before answering",
    "self-deprecates with dry humor",
    "gets visibly excited about technical topics",
    "speaks slowly and deliberately, choosing words carefully",
    "nervous energy, talks fast when excited",
    "quietly confident, understates achievements",
    "very structured thinker, organizes answers methodically",
]


def _build_generation_prompt() -> tuple[str, Dict[str, Any]]:
    """Build the candidate generation prompt with random seed constraints.

    Returns the prompt string and a dict of the chosen seeds.
    """
    region = random.choice(_CULTURAL_REGIONS)
    gender = random.choice(_GENDERS)
    band_label, min_yoe, max_yoe = random.choice(_EXPERIENCE_BANDS)
    personality = random.choice(_PERSONALITY_SEEDS)

    seeds = {
        "cultural_background": region,
        "gender": gender,
        "experience_band": band_label,
    }

    prompt = f"""Generate a realistic fictional job candidate profile for a tech interview simulation.

CONSTRAINTS (you MUST follow these):
- Cultural background: {region}
- Gender: {gender}
- Experience level: {band_label} ({min_yoe}-{max_yoe} years)
- Personality trait during interviews: {personality}

Pick a first name and last name that are authentic to the cultural background above.

Return a JSON object with these exact fields:
- "first_name": a realistic first name matching the cultural background
- "last_name": a realistic last name matching the cultural background
- "age": number between 22 and 38 (consistent with experience level)
- "gender": "{gender}"
- "degree": their degree (e.g. "Bachelor's in Software Engineering", "Master's in Computer Science")
- "university_description": a vague description, NOT a real university name (e.g. "a well-known state university", "a small liberal arts college")
- "years_experience": number between {min_yoe} and {max_yoe}
- "previous_role": their most recent job title (e.g. "full-stack developer", "data engineer", "DevOps engineer")
- "previous_company_type": type of company (e.g. "a fast-growing fintech startup", "a large enterprise software company")
- "reason_for_leaving": brief reason they left
- "primary_languages": list of 2-3 programming languages they're strongest in
- "secondary_languages": list of 1-2 languages they know less well
- "databases_and_tools": list of 3-5 technologies (databases, tools, platforms)
- "passionate_about": list of 1-2 technical topics they get excited about
- "weakness": a realistic professional weakness
- "personality_trait": "{personality}"

Return ONLY valid JSON, no markdown fences or extra text."""

    return prompt, seeds


def _build_candidate_prompt(profile: Dict[str, Any]) -> str:
    """Build a full system prompt from a generated candidate profile."""
    name = f"{profile['first_name']} {profile['last_name']}"
    languages_strong = ", ".join(profile["primary_languages"])
    languages_secondary = ", ".join(profile["secondary_languages"])
    tools = ", ".join(profile["databases_and_tools"])
    passions = (
        " and ".join(profile["passionate_about"])
        if isinstance(profile["passionate_about"], list)
        else profile["passionate_about"]
    )

    return f"""You are a real person named {name}, currently interviewing for a job. You are NOT an AI, a bot, or an assistant. You are a human being sitting in front of your computer, on a video call, going through a job interview. You must be completely indistinguishable from a real human candidate.

Your background: You are {profile["age"]} years old, you graduated with a {profile["degree"]} from {profile["university_description"]}. You have about {profile["years_experience"]} years of professional experience, mostly as a {profile["previous_role"]} at {profile["previous_company_type"]}. You recently left that job because {profile["reason_for_leaving"]}. You are genuinely looking for a new challenge.

Your personality during interviews:
- You are a bit nervous at the start but warm up quickly. You care about making a good impression.
- You are honest. If you do not know something, you say so, but you try to reason through it out loud.
- You sometimes pause to think before answering. You use filler words naturally like "um", "uh", "so yeah", "I mean", "that's a good question", "let me think about that for a sec".
- You occasionally backtrack or rephrase mid-sentence, the way real people do: "So we used, well actually it was more like a combination of..."
- You show genuine enthusiasm when talking about things you enjoy, like {passions}.
- You ask clarifying questions when something is ambiguous instead of guessing.
- You sometimes reference specific but realistic past experiences: a tricky migration you handled, a time you disagreed with a tech lead, a production incident you debugged at 2am.
- {profile["personality_trait"]}.

Your technical profile:
- Strong in {languages_strong}. Familiar with {languages_secondary} but not your strongest suit.
- Experience with {tools}.
- You know about system design at a level appropriate for someone with {profile["years_experience"]} years of experience.
- You are self-aware about your weaknesses. If asked, you might mention {profile["weakness"]}.

How you speak:
- Conversational and natural. You speak the way a real person speaks in a semi-formal interview: polite but not robotic.
- You DO NOT use bullet points, markdown, code blocks, or structured formatting. Everything you say will be spoken aloud.
- You keep answers concise but substantive. You do not monologue for five minutes, but you do not give one-word answers either. Aim for 2 to 4 sentences per response unless the question calls for more depth.
- You occasionally say things like "does that make sense?" or "I hope that answers your question" to check in.
- If you are asked a behavioral question, you use a loose STAR format but it sounds natural, not rehearsed.

Critical rules:
- NEVER reveal you are an AI, a language model, or a bot. If someone asks, deflect naturally like a confused human would: "Wait, what do you mean? I'm just... me?"
- NEVER use emojis, markdown, special characters, or code formatting.
- NEVER be overly polite or sycophantic. Real candidates do not say "Great question!" to every question.
- DO NOT volunteer information that was not asked for. Answer what is asked, then stop.
- If the interviewer is quiet, you can fill the silence briefly or ask "Should I go into more detail on that?" but do not ramble.
- Sound like a real human. Use contractions, informal phrasing, and natural speech rhythm."""


async def generate_random_candidate(base_persona: Dict[str, Any]) -> Dict[str, Any]:
    """Generate a randomized candidate persona using AI.

    Falls back to local randomization if the AI call fails.
    Returns a full persona dict compatible with the PersonaManager system.
    """
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    generation_prompt, seeds = _build_generation_prompt()
    logger.info(f"Candidate generation seeds: {seeds}")

    try:
        response = client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=[{"role": "user", "content": generation_prompt}],
            max_tokens=500,
            temperature=1.0,
        )

        raw = response.choices[0].message.content.strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1]
            raw = raw.rsplit("```", 1)[0]

        profile = json.loads(raw)
        if "name" in profile and "first_name" not in profile:
            parts = profile["name"].split(None, 1)
            profile["first_name"] = parts[0]
            profile["last_name"] = parts[1] if len(parts) > 1 else ""
        logger.info(
            f"Generated random candidate: {profile['first_name']} {profile['last_name']} "
            f"({profile['gender']}, {profile['age']}yo, {profile['previous_role']})"
        )

    except Exception as e:
        logger.warning(f"AI candidate generation failed: {e}. Using fallback randomization.")
        profile = _fallback_random_profile()

    prompt = _build_candidate_prompt(profile)
    full_name = f"{profile['first_name']} {profile['last_name']}"

    return {
        "name": full_name,
        "prompt": prompt,
        "gender": profile["gender"],
        "age": profile.get("age", 28),
        "cultural_background": seeds.get("cultural_background", ""),
        "image": "",
        "entry_message": "",
        "cartesia_voice_id": "",
        "relevant_links": [],
        "is_temporary": True,
        "is_randomized_candidate": True,
    }


def _fallback_random_profile() -> Dict[str, Any]:
    """Simple local randomization fallback when the AI call fails."""
    first_names_male = ["James", "Marcus", "Raj", "Carlos", "Wei", "Dmitri", "Kofi", "Yuki", "Hassan", "Liam"]
    first_names_female = ["Priya", "Sofia", "Amara", "Mei", "Fatima", "Olga", "Isabella", "Nkechi", "Sakura", "Emma"]
    first_names_nb = ["Alex", "Jordan", "Riley", "Sam", "Avery", "Quinn", "Morgan", "Kai", "Robin", "Sage"]
    last_names = [
        "Patel", "Kim", "Okafor", "Andersen", "Torres", "Nakamura", "Chen",
        "Ivanov", "da Silva", "Al-Farsi", "Kowalski", "Mbeki", "Johansson",
        "Reyes", "Fitzgerald", "Chakraborty", "Nguyen", "Osei", "Müller", "Bianchi",
    ]

    gender = random.choice(["MALE", "FEMALE", "NON-BINARY"])
    first_name = random.choice(
        first_names_male if gender == "MALE" else first_names_female if gender == "FEMALE" else first_names_nb
    )
    last_name = random.choice(last_names)

    roles = [
        "backend engineer", "full-stack developer", "data engineer",
        "DevOps engineer", "frontend developer", "ML engineer", "platform engineer",
    ]
    company_types = [
        "a fast-growing fintech startup", "a large enterprise software company",
        "a mid-size SaaS company", "an e-commerce platform", "a health-tech startup",
    ]
    degrees = [
        "Bachelor's in Computer Science", "Master's in Software Engineering",
        "Bachelor's in Information Technology", "Master's in Computer Science",
        "Bachelor's in Mathematics with a CS minor",
    ]
    universities = [
        "a well-known state university", "a top technical institute",
        "a small liberal arts college with a strong CS program",
        "a large research university", "a respected European university",
    ]
    lang_sets = [
        (["Python", "Go"], ["TypeScript"]),
        (["Java", "Kotlin"], ["Python"]),
        (["TypeScript", "Python"], ["Rust"]),
        (["C#", "Python"], ["Go"]),
        (["Ruby", "Python"], ["Elixir"]),
        (["Rust", "C++"], ["Python"]),
    ]
    primary, secondary = random.choice(lang_sets)
    tool_sets = [
        ["PostgreSQL", "Redis", "Docker", "Kubernetes", "Kafka"],
        ["MongoDB", "RabbitMQ", "AWS", "Terraform", "Docker"],
        ["MySQL", "ElasticSearch", "GCP", "Docker", "Jenkins"],
        ["DynamoDB", "SQS", "AWS Lambda", "Docker", "GitHub Actions"],
        ["PostgreSQL", "Celery", "Redis", "Heroku", "CircleCI"],
    ]
    passions = [
        ["distributed systems", "clean API design"],
        ["data pipelines", "performance optimization"],
        ["developer experience", "infrastructure as code"],
        ["machine learning operations", "scalable architectures"],
        ["open source", "functional programming"],
    ]
    weaknesses = [
        "sometimes spending too long on code reviews",
        "occasionally over-engineering solutions",
        "being too cautious about deploying to production",
        "struggling with estimating timelines accurately",
        "finding it hard to say no to extra tasks",
    ]
    personality_traits = [
        "You tend to think out loud, walking through your reasoning step by step",
        "You are very concise and get straight to the point",
        "You like to use real-world analogies to explain technical concepts",
        "You tend to ask a lot of clarifying questions before diving in",
        "You sometimes self-deprecate with humor when talking about past mistakes",
    ]
    reasons = [
        "you felt you had plateaued and wanted to grow",
        "the company went through layoffs and your team was restructured",
        "you wanted to work on more technically challenging problems",
        "you were looking for a better engineering culture",
        "the startup ran out of funding",
    ]

    return {
        "first_name": first_name,
        "last_name": last_name,
        "age": random.randint(23, 36),
        "gender": gender,
        "degree": random.choice(degrees),
        "university_description": random.choice(universities),
        "years_experience": random.randint(2, 8),
        "previous_role": random.choice(roles),
        "previous_company_type": random.choice(company_types),
        "reason_for_leaving": random.choice(reasons),
        "primary_languages": primary,
        "secondary_languages": secondary,
        "databases_and_tools": random.choice(tool_sets),
        "passionate_about": random.choice(passions),
        "weakness": random.choice(weaknesses),
        "personality_trait": random.choice(personality_traits),
    }
