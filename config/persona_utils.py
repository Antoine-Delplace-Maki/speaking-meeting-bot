import os
import random
from pathlib import Path
from typing import Dict, Optional

import markdown
from dotenv import load_dotenv
from loguru import logger

load_dotenv()


class PersonaManager:
    def __init__(self, personas_dir: Optional[Path] = None):
        self.personas_dir = personas_dir or Path(__file__).parent / "personas"
        self.md = markdown.Markdown(extensions=["meta"])
        self.personas = self.load_personas()

    def parse_readme(self, content: str) -> Dict:
        """Parse README.md content to extract persona information"""
        self.md.reset()
        self.md.convert(content)

        sections = content.split("\n## ")

        name = sections[0].split("\n", 1)[0].replace("# ", "").strip()
        prompt = sections[0].split("\n\n", 1)[1].strip()

        metadata = {
            "image": "",
            "entry_message": "",
            "cartesia_voice_id": "",
            "gender": "",
            "relevant_links": [],
            "randomize": "",
        }
        for section in sections:
            if section.startswith("Metadata"):
                for line in section.split("\n"):
                    if line.startswith("- "):
                        try:
                            key_value = line[2:].split(": ", 1)
                            if len(key_value) == 2:
                                key, value = key_value
                                if key == "relevant_links":
                                    metadata[key] = [
                                        url for url in value.strip().split() if url
                                    ]
                                else:
                                    metadata[key] = value.strip()
                        except ValueError:
                            continue
                break

        return {
            "name": name,
            "prompt": prompt,
            "image": metadata.get("image", ""),
            "entry_message": metadata.get("entry_message", ""),
            "cartesia_voice_id": metadata.get("cartesia_voice_id", ""),
            "gender": metadata.get("gender", ""),
            "relevant_links": metadata.get("relevant_links", []),
            "randomize": metadata.get("randomize", "").lower() == "true",
        }

    def load_additional_content(self, persona_dir: Path) -> str:
        """Load additional markdown content from persona directory"""
        additional_content = []
        skip_files = {"README.md", ".DS_Store"}

        try:
            for file_path in persona_dir.glob("*.md"):
                if file_path.name not in skip_files:
                    with open(file_path, "r", encoding="utf-8") as f:
                        content = f.read().strip()
                        if content:
                            additional_content.append(
                                f"# Content from {file_path.name}\n\n{content}"
                            )
        except Exception as e:
            logger.error(f"Error loading additional content from {persona_dir}: {e}")

        return "\n\n".join(additional_content)

    def load_personas(self) -> Dict:
        """Load personas from directory structure"""
        personas = {}
        try:
            for persona_dir in self.personas_dir.iterdir():
                if not persona_dir.is_dir():
                    continue

                readme_file = persona_dir / "README.md"
                if not readme_file.exists():
                    logger.warning(
                        f"Skipping persona without README: {persona_dir.name}"
                    )
                    continue

                with open(readme_file, "r", encoding="utf-8") as f:
                    content = f.read()
                    persona_data = self.parse_readme(content)

                    additional_content = self.load_additional_content(persona_dir)
                    if additional_content:
                        persona_data["additional_content"] = additional_content

                    personas[persona_dir.name] = persona_data

            return personas
        except Exception as e:
            logger.error(f"Failed to load personas: {e}")
            raise

    def get_persona(self, name: Optional[str] = None) -> Dict:
        """Get a persona by name or return a random one"""
        if name:
            folder_name = name.lower().replace(" ", "_")

            if folder_name in self.personas:
                persona = self.personas[folder_name].copy()
                logger.info(f"Using specified persona folder: {folder_name}")
            else:
                words = set(name.lower().split())
                closest_match = None
                max_overlap = 0

                for persona_key in self.personas.keys():
                    persona_words = set(persona_key.split("_"))
                    overlap = len(words & persona_words)
                    if overlap > max_overlap:
                        max_overlap = overlap
                        closest_match = persona_key

                if closest_match and max_overlap >= 1:
                    persona = self.personas[closest_match].copy()
                    logger.warning(
                        f"Using closest matching persona folder: {closest_match} (from: {name})"
                    )
                else:
                    raise KeyError(
                        f"Persona '{name}' not found. Valid options: {', '.join(self.personas.keys())}"
                    )
        else:
            persona = random.choice(list(self.personas.values())).copy()
            logger.info(f"Randomly selected persona: {persona['name']}")

        if not persona.get("image"):
            persona["image"] = ""

        persona_key = (
            name.lower().replace(" ", "_")
            if name
            else persona["name"].lower().replace(" ", "_")
        )
        persona["path"] = os.path.join(self.personas_dir, persona_key)
        return persona


persona_manager = PersonaManager()
