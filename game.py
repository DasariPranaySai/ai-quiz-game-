# game.py
import requests
import json
import random
import time
import re
from typing import List, Dict, Set, Optional, Iterator

# Optional spaCy usage (gracefully falls back if not installed)
try:
    import spacy
    nlp = spacy.load("en_core_web_sm")
except (ImportError, OSError):
    print("spaCy model 'en_core_web_sm' not found. Lemmatization and better NER will be disabled.")
    print("To enable: pip install spacy && python -m spacy download en_core_web_sm")
    nlp = None

# --- Constants ---
# Base URL for the Ollama API
OLLAMA_BASE_URL = "http://localhost:11434"

# Lists of words for story generation to provide variety
OBJECT_WORDS = [
    'amulet', 'armor', 'arrow', 'artifact', 'bag', 'banner', 'boat', 'book', 'bow', 'box',
    'bracelet', 'bridge', 'brooch', 'cabinet', 'carriage', 'castle', 'cauldron', 'cave',
    'chalice', 'chest', 'clock', 'clue', 'coin', 'compass', 'crown', 'crystal', 'dagger',
    'datapad', 'desk', 'device', 'diary', 'door', 'dragon', 'drone', 'drum', 'elixir',
    'engine', 'envelope', 'flute', 'forest', 'fountain', 'gem', 'goblet', 'grimoire',
    'harp', 'helmet', 'hologram', 'horse', 'house', 'idol', 'jetpack', 'journal', 'key',
    'knight', 'lamp', 'lantern', 'laser', 'letter', 'locket', 'manuscript', 'map',
    'mask', 'medallion', 'mirror', 'monster', 'mountain', 'necklace', 'note', 'orb',
    'painting', 'pendant', 'photograph', 'plate', 'portal', 'potion', 'relic', 'ring',
    'river', 'robot', 'rope', 'runestone', 'scepter', 'scroll', 'shield', 'ship',
    'spaceship', 'spear', 'spellbook', 'staff', 'statue', 'stone', 'sword', 'talisman',
    'tapestry', 'telescope', 'throne', 'torch', 'treasure', 'tree', 'wand', 'waterfall',
    'whistle', 'wizard', 'bird', 'cat', 'chair', 'dog', 'flower', 'table'
]

PLACE_WORDS = [
    'academy', 'alley', 'arena', 'asteroid field', 'asylum', 'beach', 'bunker',
    'canyon', 'castle', 'catacomb', 'cathedral', 'cave', 'chamber', 'chapel',
    'citadel', 'city', 'clearing', 'coast', 'cottage', 'courtyard', 'crypt',
    'desert', 'dock', 'dungeon', 'estate', 'factory', 'farm', 'field', 'forest',
    'fortress', 'galaxy', 'garden', 'glade', 'harbor', 'headquarters', 'hill',
    'hospital', 'house', 'island', 'jungle', 'kingdom', 'laboratory', 'lair',
    'lake', 'library', 'mansion', 'market', 'meadow', 'mine', 'monastery',
    'mountain', 'museum', 'observatory', 'ocean', 'outpost', 'palace', 'path',
    'planet', 'port', 'prison', 'realm', 'river', 'road', 'ruins', 'sanctuary',
    'school', 'sewer', 'shop', 'space station', 'stronghold', 'swamp', 'temple',
    'tomb', 'tower', 'town', 'tunnel', 'valley', 'village', 'volcano', 'warehouse'
]


class OllamaStoryQuizGame:
    """
    A class to represent the core story quiz game logic.
    It handles story and quiz generation using the Ollama service.
    """
    def __init__(self, model_name: str = "gemma:2b", genre: str = "adventure"):
        """
        Initializes the game with a model name, genre, and other default values.
        """
        self.model_name = model_name
        self.genre = genre
        self.ollama_api_url = f"{OLLAMA_BASE_URL}/api/generate"
        self.score = 0
        self.questions_answered = 0
        self.used_stories: Set[str] = set()
        self.session = requests.Session()

        # Sensible defaults for the game
        self.story_word_limit = 150
        self.num_questions_per_round = 3

    def check_ollama_connection(self) -> bool:
        """
        Checks if the Ollama service is running and accessible.
        """
        try:
            r = self.session.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=5)
            return r.status_code == 200
        except requests.RequestException:
            return False

    def generate_with_ollama(self, prompt: str, max_tokens: int = 200) -> str:
        """
        Generates text using the Ollama API with the specified prompt and parameters.
        """
        try:
            payload = {
                "model": self.model_name, "prompt": prompt, "stream": False,
                "options": {"num_predict": max_tokens, "temperature": 0.7, "top_p": 0.9}
            }
            response = self.session.post(self.ollama_api_url, json=payload, timeout=60)
            response.raise_for_status()
            # The expected JSON has a "response" field; this might need adjustment if the endpoint differs
            result = response.json().get("response", "")
            return result.strip() if result else ""
        except Exception:
            return ""

    def _truncate_story(self, story: str, word_limit: int) -> str:
        """
        Truncates a story to a specified word limit, ensuring it ends at a sentence boundary if possible.
        """
        words = story.split()
        if len(words) <= word_limit:
            return story
        truncated = ' '.join(words[:word_limit])
        last_period = truncated.rfind('.')
        if last_period != -1:
            return truncated[:last_period + 1]
        return truncated + "..."

    def generate_story_stream(self, prompt: str, ollama_max_tokens: int) -> Iterator[str]:
        """
        Generates a story and yields it character by character for a streaming effect on the frontend.
        """
        try:
            raw = self.generate_with_ollama(prompt, max_tokens=ollama_max_tokens)
            final_story = self._truncate_story(raw, self.story_word_limit) if raw else self.get_fallback_story()
            for ch in final_story:
                yield ch
                time.sleep(0.01)
        except Exception:
            yield "Error: Could not generate story."

    # -------------------------
    # Helpers
    # -------------------------
    def _safe_sample(self, pool: List[str], k: int, fallback_pool: List[str]) -> List[str]:
        """
        Safely samples k items from a pool, falling back to another pool if the first is too small.
        """
        pool = [p for p in pool if p and str(p).strip() != ""]
        seen = set()
        pool = [x for x in pool if not (x in seen or seen.add(x))]
        if len(pool) >= k:
            return random.sample(pool, k)
        result = pool.copy()
        for item in fallback_pool:
            if len(result) >= k:
                break
            if item not in result:
                result.append(item)
        while len(result) < k:
            result.append("None")
        return result

    def _normalize_text(self, txt: str) -> str:
        """
        Normalizes text by stripping whitespace, removing punctuation, and converting to lowercase.
        Uses lemmatization if spaCy is available.
        """
        if not txt:
            return ""
        s = txt.strip()
        s = re.sub(r'[^\w\s]', '', s)
        s = re.sub(r'\s+', ' ', s).strip().lower()
        try:
            if nlp:
                doc = nlp(s)
                lemmas = [tok.lemma_ for tok in doc if tok.lemma_]
                if lemmas:
                    return ' '.join(lemmas).lower()
        except Exception:
            pass
        if s.endswith('ed'):
            return s[:-2]
        if s.endswith('ing'):
            return s[:-3]
        return s

    def _action_by_main_character(self, story: str, main_character: str) -> Optional[str]:
        """
        Identifies a key action performed by the main character using spaCy for linguistic analysis.
        """
        if not nlp or not main_character:
            return None
        try:
            doc = nlp(story)
            target_names = {main_character.split()[0].lower()}
            for ent in doc.ents:
                if ent.label_ == "PERSON" and main_character.lower() in ent.text.lower():
                    target_names.add(ent.text.split()[0].lower())
            for sent in doc.sents:
                for token in sent:
                    if token.pos_ == "VERB":
                        for child in token.children:
                            if child.dep_ in ("nsubj", "nsubjpass") and child.text.lower() in target_names:
                                return token.lemma_.lower()
            return None
        except Exception:
            return None

    # -------------------------
    # Robust parser for AI output
    # -------------------------
    def parse_quiz_questions(self, txt: str) -> List[Dict]:
        """
        Parses the text output from the AI to extract multiple-choice questions.
        This function is designed to be robust against formatting variations.
        """
        if not txt:
            return []

        questions = []
        lines = [ln.rstrip() for ln in txt.replace('\r', '').split('\n')]
        blocks = []
        current = []
        for line in lines:
            if re.match(r'^\s*Question\b', line, re.I) and current:
                blocks.append(current)
                current = [line]
            else:
                current.append(line)
        if current:
            blocks.append(current)

        option_re = re.compile(r'^\s*([A-D])\s*[\)\.\:]\s*(.+)$', re.I)
        answer_re_list = [
            re.compile(r'Correct Answer\s*[:\-]?\s*([A-D])', re.I),
            re.compile(r'Correct\s*[:\-]?\s*([A-D])', re.I),
            re.compile(r'Answer\s*[:\-]?\s*([A-D])', re.I)
        ]

        for block in blocks:
            b_lines = [l for l in block if l and l.strip() != '']
            if not b_lines:
                continue
            opt_idx = None
            for i, l in enumerate(b_lines):
                if option_re.match(l):
                    opt_idx = i
                    break
            if opt_idx is None:
                continue
            question_text = ' '.join(b_lines[:opt_idx]).strip()
            question_text = re.sub(r'^\s*Question\s*\d*\s*[:\-]?\s*', '', question_text, flags=re.I).strip()
            options = {}
            for l in b_lines[opt_idx:]:
                m = option_re.match(l)
                if m:
                    key = m.group(1).upper()
                    val = re.sub(r'\s+', ' ', m.group(2).strip())
                    options[key] = val
            correct_letter = None
            block_text = '\n'.join(b_lines)
            for are in answer_re_list:
                am = are.search(block_text)
                if am:
                    correct_letter = am.group(1).upper()
                    break
            if question_text and len(options) == 4 and correct_letter and correct_letter in options:
                questions.append({
                    'question': question_text,
                    'options': options,
                    'correct': correct_letter
                })
        return questions

    # -------------------------
    # Fallbacks
    # -------------------------
    def get_fallback_story(self) -> str:
        """
        Provides a random fallback story if the AI fails to generate one.
        """
        fallback_stories = [
            "Maya found a magical music box in her grandmother's attic. When she opened it, a tiny dancer began to spin, and the melody transported her to a world where colors had sounds and dreams took flight.",
            "Ben discovered an old compass that didn't point north. Instead, it led him through the enchanted forest to a clearing where time moved backwards and he could see his future self waving from tomorrow.",
            "Luna's pet rabbit, Whiskers, started talking one morning. He told her about the secret underground city where all lost socks go, and together they planned an epic adventure to retrieve her favorite striped pair."
        ]
        return random.choice(fallback_stories)

    def get_fallback_quiz(self, story: str) -> List[Dict]:
        """
        Generates a fallback quiz if the AI fails to generate one.
        This uses the `generate_unique_questions` method which is more reliable.
        """
        print("🎯 Generating story-specific fallback questions.")
        num_questions = getattr(self, 'num_questions_per_round', 3)
        elements = self.extract_story_elements(story)
        unique_questions = self.generate_unique_questions(story, elements)
        if len(unique_questions) >= num_questions:
            return unique_questions[:num_questions]
        remaining_needed = num_questions - len(unique_questions)
        for _ in range(remaining_needed):
            contextual_q = self.create_contextual_question(story, elements, set())
            if contextual_q:
                unique_questions.append(contextual_q)
        return unique_questions[:num_questions]

    # -------------------------
    # Core story helpers
    # -------------------------
    def generate_story(self) -> str:
        """
        Generates a story using the Ollama service, with retries and a fallback.
        """
        story_starters = [
            f"Write a unique {self.genre} story",
            f"Create an original {self.genre} tale",
            f"Tell a fresh {self.genre} narrative",
            f"Craft a new {self.genre} adventure",
            f"Compose a distinctive {self.genre} story",
        ]
        settings = [
            "in a forgotten library full of whispering books",
            "in a magical garden where flowers sing at dawn",
            "in a mysterious forest under a perpetual twilight",
            "in a quiet, snow-covered village on the edge of the world",
            "in a secret underground laboratory filled with strange devices",
            "in a spooky, abandoned mansion on a windswept hill",
            "on a futuristic space station orbiting a distant star",
        ]
        story_starter = random.choice(story_starters)
        setting = random.choice(settings)
        random_seed = random.randint(1000, 9999)
        keyword_guidance = ""
        if random.random() < 0.6:
            keyword_object = random.choice(OBJECT_WORDS)
            keyword_place = random.choice(PLACE_WORDS)
            keyword_guidance = f"Try to include an object like a '{keyword_object}' and a place like a '{keyword_place}' in the story."
        prompt = f"""{story_starter} {setting}. {keyword_guidance}
Make the story approximately {self.story_word_limit} words. Use creative characters and unique plot events. Include specific names, objects, and actions. Seed: {random_seed}

Requirements:
- Age-appropriate for grades 6-10
- Safe for school environment
- Include specific character names
- Have a clear beginning, middle, and end"""
        for attempt in range(3):
            story = self.generate_with_ollama(prompt, max_tokens=self.story_word_limit + 100)
            if story:
                story_hash = str(hash(story))
                if story_hash not in self.used_stories:
                    self.used_stories.add(story_hash)
                    return self._truncate_story(story, self.story_word_limit)
            time.sleep(1)
        return self.get_fallback_story()

    def extract_story_elements(self, story: str) -> Dict:
        """
        Extracts specific elements from the story for question generation.
        This is safe to call even if the story is None or empty.
        """
        if not story:
            story = ""

        # Split sentences safely
        sentences = re.split(r'[.!?]+', story)
        sentences = [s.strip() for s in sentences if s and s.strip()]

        # Simple name pattern and fallback NER if available
        name_pattern = r'\b[A-Z][a-z]{2,}\b'
        potential_names = re.findall(name_pattern, story or "")

        # Collect names using spaCy if available
        names = []
        if nlp and story:
            try:
                doc = nlp(story)
                names = [ent.text for ent in doc.ents if ent.label_ == "PERSON"]
            except Exception:
                names = []

        # Combine heuristics with small safeguards
        common_words = {
            'The', 'This', 'That', 'They', 'Then', 'There', 'These', 'Those',
            'When', 'Where', 'What', 'Who', 'Why', 'How', 'And', 'But', 'Or',
            'So', 'For', 'As', 'At', 'By', 'In', 'On', 'To', 'With', 'From', 'A', 'An',
        }
        titles = {
            'Agent', 'Captain', 'Commander', 'Dame', 'Detective', 'Dr', 'General', 'King',
            'Lady', 'Lord', 'Miss', 'Mr', 'Mrs', 'Ms', 'Officer', 'Prince', 'Princess',
            'Professor', 'Queen', 'Sergeant', 'Sir'
        }

        combined_names = set(names)
        for i, word in enumerate(potential_names):
            if word in titles and i + 1 < len(potential_names):
                full_name = f"{word} {potential_names[i+1]}"
                combined_names.add(full_name)
            elif word not in common_words:
                combined_names.add(word)

        names = sorted(list(combined_names), key=len, reverse=True)

        # Verbs/actions via spaCy lemma if available
        action_words = []
        if nlp and story:
            try:
                doc = nlp(story)
                action_words = [token.lemma_ for token in doc if token.pos_ == "VERB" and token.dep_ != 'aux']
            except Exception:
                action_words = []

        # Objects/places detection using the constant lists; use lowercased story safely
        story_lower = (story or "").lower()
        objects = [obj for obj in OBJECT_WORDS if obj in story_lower]
        places = [place for place in PLACE_WORDS if place in story_lower]

        return {
            'names': list(set(names))[:5],
            'actions': list(set(action_words))[:5],
            'objects': list(set(objects))[:5],
            'places': list(set(places))[:5],
            'sentences': sentences[:6],
            'first_sentence': sentences[0] if sentences else "",
            'story_words': (story or "").split()
        }

    # -------------------------
    # Improved, varied question generation
    # -------------------------
    def generate_unique_questions(self, story: str, elements: Dict) -> List[Dict]:
        """
        Generates a variety of unique questions based on the extracted story elements.
        This method is designed to create more engaging and less repetitive quizzes.
        """
        questions: List[Dict] = []
        used_elements: Set[str] = set()
        num_needed = getattr(self, 'num_questions_per_round', 3)

        def make_mcq(correct_text: str, decoy_pool: List[str], fallback_pool: List[str], title_case: bool = False):
            """Helper function to create a multiple-choice question."""
            decoys = self._safe_sample([d for d in decoy_pool if d and d.lower() != correct_text.lower()], 3, fallback_pool)
            opts = [correct_text] + decoys
            random.shuffle(opts)
            if title_case:
                opts_display = [o.title() if isinstance(o, str) else str(o) for o in opts]
            else:
                opts_display = [str(o) for o in opts]
            options = {chr(65 + i): opts_display[i] for i in range(4)}
            norm_correct = self._normalize_text(correct_text)
            correct_key = None
            for k, v in options.items():
                if self._normalize_text(v) == norm_correct or norm_correct in self._normalize_text(v) or self._normalize_text(v) in norm_correct:
                    correct_key = k
                    break
            if not correct_key:
                idx = opts.index(correct_text)
                correct_key = chr(65 + idx)
            return options, correct_key

        candidate_generators = []

        # -- Question Generator Functions --
        def q_name():
            # ... (code for generating a question about the main character)
            names = elements.get('names', [])
            if not names:
                return None
            main = names[0]
            if main.lower() in used_elements:
                return None
            used_elements.add(main.lower())
            decoy_names = [
                'Aarav', 'Aditi', 'Advik', 'Aisha', 'Alex', 'Anika', 'Arjun', 'Aryan',
                'Ava', 'Benjamin', 'Caleb', 'Casey', 'Charlotte', 'Chloe', 'Cyrus',
                'Daniel', 'David', 'Diya', 'Elena', 'Elijah', 'Emily', 'Emma', 'Ethan',
                'Finn', 'Freya', 'Gabriel', 'Grace', 'Harper', 'Henry', 'Ishan',
                'Isabella', 'Jack', 'James', 'Jasper', 'Jordan', 'Julian', 'Kai',
                'Kavya', 'Krish', 'Leo', 'Liam', 'Lily', 'Logan', 'Lucas', 'Luna',
                'Madison', 'Mason', 'Mateo', 'Maya', 'Meera', 'Mia', 'Michael',
                'Morgan', 'Nitya', 'Noah', 'Nora', 'Oliver', 'Olivia', 'Om', 'Owen',
                'Penelope', 'Priya', 'Rahul', 'Riley', 'River', 'Riya', 'Rohan',
                'Sage', 'Sam', 'Samuel', 'Shaan', 'Siya', 'Sofia', 'Sophia', 'Taylor',
                'Vihaan', 'Vivaan', 'William', 'Wyatt', 'Zara', 'Zoe'
            ]
            opts, key = make_mcq(main, decoy_names, decoy_names, title_case=True)
            return {
                'question': random.choice([
                    "Who is the main character in the story?",
                    "Which character is central to the tale?",
                    "Who does the story follow?",
                    "Which of the following characters appears in the story?"
                ]),
                'options': opts,
                'correct': key
            }
        candidate_generators.append(q_name)

        def q_action():
            # ... (code for generating a question about a key action)
            actions = elements.get('actions', [])
            if not actions:
                return None
            main_char = elements.get('names', [None])[0]
            main_action = None
            if main_char:
                main_action = self._action_by_main_character(story, main_char)
            if not main_action:
                main_action = actions[0]
            if not main_action:
                return None
            if main_action.lower() in used_elements:
                return None
            used_elements.add(main_action.lower())
            decoy_actions = [
                'argued', 'built', 'calculated', 'climbed', 'cooked', 'cried', 'danced',
                'decoded', 'drew', 'dreamed', 'escaped', 'flew', 'laughed', 'listened',
                'meditated', 'negotiated', 'painted', 'played', 'programmed', 'ran',
                'read', 'repaired', 'sang', 'shouted', 'slept', 'studied', 'surrendered',
                'swam', 'teleported', 'trained', 'traveled', 'waited', 'walked',
                'whispered', 'worked', 'wrote', 'stepped', 'entered', 'invited'
            ]
            opts, key = make_mcq(main_action, decoy_actions, decoy_actions, title_case=True)
            return {
                'question': random.choice([
                    "What is a key action that takes place in the story?",
                    "Which of these actions is described in the narrative?",
                    "What did someone in the story do?"
                ]),
                'options': opts,
                'correct': key
            }
        candidate_generators.append(q_action)

        def q_object():
            # ... (code for generating a question about an object)
            objs = elements.get('objects', [])
            if not objs:
                return None
            main_obj = objs[0]
            if main_obj.lower() in used_elements:
                return None
            used_elements.add(main_obj.lower())
            decoy_objs = [
                'amulet', 'compass', 'crystal', 'key', 'lantern', 'map', 'mirror', 'orb',
                'potion', 'ring', 'scroll', 'staff', 'sword', 'talisman', 'treasure chest',
                'vial', 'wand', 'journal', 'relic'
            ]
            opts, key = make_mcq(main_obj, decoy_objs, decoy_objs, title_case=True)
            return {
                'question': random.choice([
                    "Which important object is mentioned in the story?",
                    "What item plays a role in the narrative?",
                    "Which of these objects appears in the tale?"
                ]),
                'options': opts,
                'correct': key
            }
        candidate_generators.append(q_object)

        def q_place():
            # ... (code for generating a question about the setting)
            places = elements.get('places', [])
            if not places:
                return None
            main_place = places[0]
            if main_place.lower() in used_elements:
                return None
            used_elements.add(main_place.lower())
            decoy_places = [
                'desert', 'ocean', 'jungle', 'space station', 'volcano', 'swamp', 'canyon',
                'meadow', 'tundra', 'castle', 'temple', 'city', 'laboratory', 'mansion',
                'market', 'mine', 'observatory', 'palace', 'ruins', 'tower', 'harbor',
                'factory'
            ]
            opts, key = make_mcq(main_place, decoy_places, decoy_places, title_case=True)
            return {
                'question': random.choice([
                    "Where does the story take place?",
                    "What is the primary setting of the story?",
                    "Which location is described in the narrative?",
                    "The story is set in which of these locations?",
                    "What is the backdrop for this tale?"
                ]),
                'options': opts,
                'correct': key
            }
        candidate_generators.append(q_place)

        def q_sequence():
            # ... (code for generating a question about the sequence of events)
            sents = elements.get('sentences', [])
            if len(sents) < 2:
                return None
            first = sents[0].strip()
            second = sents[1].strip()
            def short(p):
                w = p.split()
                return ' '.join(w[:10]) + ('...' if len(w) > 10 else '')
            opts_list = [short(first), short(second)]
            decoy_pool = [
                "They found a glowing key", "A ship sailed away", "A mysterious letter arrived",
                "The village celebrated", "A bell began to ring", "The sun hid behind clouds",
                "A storm began to brew", "The hero made a plan", "A map was discovered",
                "The door creaked open", "A secret was revealed", "They started their journey",
                "A strange sound was heard", "The group took a rest", "A decision was made",
                "An old enemy appeared"
            ]
            decoys = self._safe_sample(decoy_pool, 2, decoy_pool)
            options = [opts_list[0], opts_list[1], decoys[0], decoys[1]]
            random.shuffle(options)
            options_dict = {chr(65 + i): options[i] for i in range(4)}
            correct_key = None
            for k, v in options_dict.items():
                if v == opts_list[0]:
                    correct_key = k
                    break
            return {
                'question': random.choice([
                    "Which of the following happened first in the story?",
                    "What event comes earliest in the narrative?",
                    "How does the story begin?",
                    "Which event marks the start of the story?"
                ]),
                'options': options_dict,
                'correct': correct_key
            }
        candidate_generators.append(q_sequence)

        def q_true_false():
            # ... (code for generating a true/false question)
            names = elements.get('names', [])
            if not names:
                return None
            subj = names[0]
            obj = elements.get('objects', [None])[0]
            action = elements.get('actions', [None])[0]
            if obj:
                stmt = f"{subj} discovered a {obj}."
                correct_answer = "True" if obj.lower() in ' '.join(elements.get('story_words', [])).lower() else "False"
            elif action:
                stmt = f"{subj} {action} in the story."
                correct_answer = "True" if action.lower() in ' '.join(elements.get('story_words', [])).lower() else "False"
            else:
                return None
            options = {'A': 'True', 'B': 'False', 'C': 'Maybe', 'D': 'Not stated'}
            correct_key = 'A' if correct_answer == 'True' else 'B'
            return {
                'question': f"True or False: {stmt}",
                'options': options,
                'correct': correct_key
            }
        candidate_generators.append(q_true_false)

        def q_not_mentioned():
            # ... (code for generating a "which was not mentioned" question)
            story_text = ' '.join(elements.get('story_words', [])).lower()
            decoy_candidates = [
                'spaceship', 'glacier', 'police station', 'motorcycle', 'astronaut', 'market',
                'jewel', 'statue', 'bridge', 'robot', 'scepter', 'chronometer'
            ]
            mentioned_candidates = elements.get('objects', []) + elements.get('places', []) + elements.get('names', [])
            mentioned = [m for m in mentioned_candidates if m and m.lower() in story_text]
            not_mentioned_pool = [d for d in decoy_candidates if d.lower() not in story_text]
            if not not_mentioned_pool:
                return None
            correct_item = self._safe_sample(not_mentioned_pool, 1, decoy_candidates)[0]
            other_pool = [m for m in mentioned if m] + not_mentioned_pool
            other_pool = [o for o in other_pool if o.lower() != correct_item.lower()]
            others = self._safe_sample(other_pool, 3, decoy_candidates)
            opts = [correct_item] + others
            random.shuffle(opts)
            opts_dict = {chr(65 + i): opts[i].title() for i in range(4)}
            correct_key = None
            for k, v in opts_dict.items():
                if v.lower() == correct_item.lower():
                    correct_key = k
                    break
            if not correct_key:
                correct_key = 'A'
            return {
                'question': random.choice([
                    "Which of the following is NOT mentioned in the story?",
                    "Which item/place/character did the story NOT mention?"
                ]),
                'options': opts_dict,
                'correct': correct_key
            }
        candidate_generators.append(q_not_mentioned)

        def q_inference():
            # ... (code for generating an inference question)
            names = elements.get('names', [])
            if not names:
                return None
            subj = names[0]
            sents = elements.get('sentences', [])
            reason = None
            for s in sents:
                if 'because' in s.lower() or 'so that' in s.lower() or 'to' in s.lower():
                    reason = s
                    break
            if not reason:
                reason = sents[0] if sents else None
            if not reason:
                return None
            verb_like = elements.get('actions', [None])[0]
            if not verb_like:
                return None
            decoy_reasons = [
                "To find treasure", "To escape danger", "To meet a friend",
                "To learn a secret", "To show off", "By accident", "Because they were told to"
            ]
            correct_reason = "To explore" if any(w in reason.lower() for w in ['explor', 'discover', 'find', 'enter', 'step']) else "Because they had to"
            choices = [correct_reason] + self._safe_sample(decoy_reasons, 3, decoy_reasons)
            random.shuffle(choices)
            opts = {chr(65 + i): choices[i] for i in range(4)}
            correct_key = next((k for k, v in opts.items() if v == correct_reason), 'A')
            return {
                'question': random.choice([
                    f"Why did {subj} do what they did in the story?",
                    f"What is the most likely reason {subj} acted as they did?"
                ]),
                'options': opts,
                'correct': correct_key
            }
        candidate_generators.append(q_inference)

        # Shuffle and generate questions until the required number is met
        random.shuffle(candidate_generators)
        for gen in candidate_generators:
            if len(questions) >= num_needed:
                break
            try:
                q = gen()
                if q:
                    questions.append(q)
            except Exception:
                continue

        # Fill with contextual questions if needed
        while len(questions) < num_needed:
            ctx = self.create_contextual_question(story, elements, used_elements)
            if not ctx:
                break
            questions.append(ctx)

        # Clean up questions to ensure they are well-formed
        cleaned = []
        for q in questions[:num_needed]:
            opts = q.get('options', {})
            if len(opts) != 4:
                vals = list(opts.values())[:4]
                while len(vals) < 4:
                    vals.append("Not stated")
                opts = {chr(65 + i): vals[i] for i in range(4)}
                q['options'] = opts
                if 'correct' not in q or q['correct'] not in opts:
                    q['correct'] = 'A'
            cleaned.append(q)
        return cleaned[:num_needed]

    def create_contextual_question(self, story: str, elements: Dict, used_elements: set) -> Optional[Dict]:
        """
        Generates contextual questions as a fallback, ensuring there are always questions available.
        """
        first_sentence = (elements.get('first_sentence') or "")
        story_words = elements.get('story_words') or []
        story_text_lower = ' '.join(story_words).lower()

        # 1) Beginning phrase (if available)
        if first_sentence:
            words = (first_sentence or "").split()
            if len(words) > 2:
                first_phrase = ' '.join(words[:4])
                decoys = [
                    "On a stormy night", "Deep within the forest", "It was the silence",
                    "In a faraway land", "Long ago, in a kingdom", "No one expected this"
                ]
                choices = [first_phrase] + self._safe_sample(decoys, 3, decoys)
                random.shuffle(choices)
                opts = {chr(65 + i): choices[i] for i in range(4)}
                correct = next((k for k, v in opts.items() if v == first_phrase), 'A')
                if first_phrase.lower() not in used_elements:
                    used_elements.add(first_phrase.lower())
                    return {
                        'question': "Which phrase opens the story?",
                        'options': opts,
                        'correct': correct
                    }

        # 2) Word-count / length estimate (if story long enough)
        word_count = len(story_words)
        if word_count > 40:
            ranges = [
                f"About {word_count} words",
                f"About {max(10, word_count - 40)} words",
                f"About {word_count + 30} words",
                f"About {max(10, word_count + 60)} words"
            ]
            random.shuffle(ranges)
            opts = {chr(65 + i): ranges[i] for i in range(4)}
            correct = next((k for k, v in opts.items() if str(word_count) in v), 'A')
            return {
                'question': "Approximately how long is this story?",
                'options': opts,
                'correct': correct
            }

        # 3) Which of these is NOT mentioned? (fallback)
        possible_not = ['spaceship', 'museum', 'robot', 'castle', 'river', 'key', 'lantern', 'dragon', 'market']
        not_mentioned = [w for w in possible_not if w not in story_text_lower]
        if len(not_mentioned) >= 1:
            correct_choice = self._safe_sample(not_mentioned, 1, possible_not)[0]
            other_choices = self._safe_sample([w for w in possible_not if w.lower() != correct_choice.lower()], 3, possible_not)
            options = [correct_choice] + other_choices
            random.shuffle(options)
            opts = {chr(65 + i): options[i].title() for i in range(4)}
            correct_key = next((k for k, v in opts.items() if v.lower() == correct_choice.lower()), 'A')
            return {
                'question': "Which of these is NOT mentioned in the story?",
                'options': opts,
                'correct': correct_key
            }

        # 4) Generic fallback True/False
        opts = {'A': 'True', 'B': 'False', 'C': 'Not stated', 'D': 'Maybe'}
        return {
            'question': "True or False: The story included a surprising event.",
            'options': opts,
            'correct': 'A'
        }

    # -------------------------
    # UI / Game loop (for command-line execution)
    # -------------------------
    def display_story(self, story: str) -> None:
        """
        Displays the story in the console.
        """
        print("\n" + "=" * 60 + "\nYOUR STORY\n" + "=" * 60)
        print(story)
        print("\n" + "=" * 60)

    def ask_quiz_question(self, question_data: Dict, question_num: int) -> bool:
        """
        Asks a quiz question in the console and returns whether the answer was correct.
        """
        print(f"\nQUESTION {question_num}\n" + "-" * 40)
        print(question_data['question'])
        for letter, option in question_data['options'].items():
            print(f"{letter}) {option}")
        while True:
            answer = input("\nYour answer (A, B, C, or D): ").upper().strip()
            if answer in ['A', 'B', 'C', 'D']:
                break
            print("Please enter A, B, C, or D")
        is_correct = (answer == question_data.get('correct', '').upper())
        if is_correct:
            print("✅ Correct! Well done!")
            self.score += 1
        else:
            print(f"❌ Incorrect. The correct answer was {question_data.get('correct')}")
            correct_option = question_data['options'].get(question_data.get('correct', ''), '')
            if correct_option:
                print(f"   Correct answer: {correct_option}")
        self.questions_answered += 1
        return is_correct

    def play_game(self) -> None:
        """
        Starts the game loop for command-line play.
        """
        try:
            print("\nWelcome to the Story Quiz! Type Ctrl+C at any time to quit.\n")
            while True:
                story = self.generate_story()
                self.display_story(story)
                questions = self.generate_quiz_questions(story)
                if not questions:
                    print("⚠️ No questions could be generated for this story. Generating a fallback quiz...")
                    questions = self.get_fallback_quiz(story)
                round_correct = 0
                for idx, q in enumerate(questions, start=1):
                    correct = self.ask_quiz_question(q, idx)
                    if correct:
                        round_correct += 1
                print("\n" + "-" * 40)
                print(f"Round complete — you answered {round_correct}/{len(questions)} correctly.")
                print(f"Total score: {self.score} (questions answered: {self.questions_answered})")
                while True:
                    cont = input("\nPlay another round? (Y/n): ").strip().lower()
                    if cont in ("", "y", "yes"):
                        break
                    elif cont in ("n", "no"):
                        print("\nThanks for playing! Final score:", self.score)
                        return
                    else:
                        print("Please enter 'y' to continue or 'n' to quit.")
        except KeyboardInterrupt:
            print("\n\nGame interrupted. Thanks for playing! Final score:", self.score)
            return
        except Exception as e:
            print(f"\nAn unexpected error occurred during gameplay: {e}")
            return

    def generate_quiz_questions(self, story: str) -> List[Dict]:
        """
        Generates quiz questions based on the story, with improved fallback and None-guards.
        """
        if story is None:
            story = ""
        num_questions = getattr(self, 'num_questions_per_round', 3)
        elements = self.extract_story_elements(story)
        focus_points = []
        if elements.get('names'):
            focus_points.append(f"the main character, {elements['names'][0]}")
        if elements.get('objects'):
            focus_points.append(f"the role of the {elements['objects'][0]}")
        if elements.get('actions'):
            focus_points.append(f"a key action, such as '{elements['actions'][0]}'")
        focus_prompt = f"Focus the questions on key details like {', '.join(focus_points)}." if focus_points else ""
        quiz_prompt = f"""Based only on the details within the following story, create exactly {num_questions} unique and insightful multiple-choice questions to test reading comprehension. {focus_prompt}

Story: {story}

Format:
Question: [text]
A) [option]
B) [option]
C) [option]
D) [option]
Correct Answer: [A-D]
"""
        for attempt in range(3):
            quiz_text = self.generate_with_ollama(quiz_prompt, max_tokens=400)
            parsed_questions = self.parse_quiz_questions(quiz_text)
            if len(parsed_questions) == num_questions:
                return parsed_questions
            time.sleep(1)
        return self.get_fallback_quiz(story)


class OllamaStoryQuizGameWithLevels(OllamaStoryQuizGame):
    """
    An advanced version of the game with progressive levels, longer stories, and hints.
    """
    def __init__(self, model_name: str = "gemma:2b", genre: str = "adventure", start_level: int = 1):
        """
        Initializes the advanced game with level-specific parameters.
        """
        super().__init__(model_name, genre)
        self.level = start_level
        self.level_score = 0
        self.story_word_limit = 100 + (25 * (start_level -1))
        self.max_level = 50
        self.hints = 3
        self.num_questions_per_round = 3 + ((start_level -1) // 5)


    def advance_level(self) -> bool:
        """
        Advances the player to the next level, increasing difficulty and awarding hints.
        """
        hint_awarded = False
        if self.level < self.max_level:
            print(f"\n🎉 LEVEL UP! Welcome to Level {self.level + 1}!")
            if (self.level + 1) > 1 and (self.level + 1) % 2 != 0:
                self.hints += 1
                hint_awarded = True
            self.level += 1
            self.level_score = 0
            self.story_word_limit = min(self.story_word_limit + 25, 600)
            self.num_questions_per_round = min(3 + (self.level // 5), 8)
            print(f"📈 Stories are now ~{self.story_word_limit} words")
            print(f"🎯 Questions per round: {self.num_questions_per_round}")
        return hint_awarded

    def generate_story(self) -> str:
        """
        Generates a story with complexity based on the current level.
        """
        story_starters = [
            f"Write a captivating {self.genre} story",
            f"Create an engaging {self.genre} tale",
            f"Tell an exciting {self.genre} adventure",
            f"Craft a thrilling {self.genre} narrative",
            f"Compose a unique {self.genre} saga",
            f"Weave a new {self.genre} legend",
            f"Imagine an original {self.genre} chronicle",
        ]
        settings = [
            "in a forgotten library full of whispering books",
            "in a magical garden where flowers sing at dawn",
            "in a mysterious forest under a perpetual twilight",
            "in a quiet, snow-covered village on the edge of the world",
            "in a secret underground laboratory filled with strange devices",
            "in a spooky, abandoned mansion on a windswept hill",
            "on a futuristic space station orbiting a distant star",
            "aboard a creaky pirate ship on the high seas",
            "within a bustling cyberpunk city under neon lights",
            "in a hidden valley where dinosaurs still roam",
            "at a grand masquerade ball with a secret agenda",
        ]

        complexity_levels = {
            1: "simple vocabulary and straightforward plot",
            5: "moderate vocabulary with some complex sentences",
            10: "advanced vocabulary and intricate plot twists",
            15: "sophisticated language and multi-layered storylines"
        }
        # Determine complexity based on level, defaulting to the simplest for level 1.
        # This ensures complexity gradually increases in a stable way.
        if self.level >= 15: complexity_key = 15
        elif self.level >= 10: complexity_key = 10
        elif self.level >= 5: complexity_key = 5
        else: complexity_key = 1
        complexity = complexity_levels[complexity_key]

        setting = random.choice(settings)
        story_starter = random.choice(story_starters)
        random_seed = random.randint(1000, 9999)
        keyword_guidance = ""
        
        # Add more creative elements to the prompt, similar to the base class
        if random.random() < 0.6:
            keyword_object = random.choice(OBJECT_WORDS)
            keyword_place = random.choice(PLACE_WORDS)
            keyword_guidance = f"Try to include an object like a '{keyword_object}' and a place like a '{keyword_place}'."
        
        prompt = f"""{story_starter} {setting}. The story should be approximately {self.story_word_limit} words. Use {complexity}. {keyword_guidance}
Include specific character names, unique objects, and detailed settings. Make it age-appropriate for grades 6-10.
Ensure a clear beginning, middle, and end. Seed: {random_seed}"""

        raw_story = self.generate_with_ollama(prompt, max_tokens=self.story_word_limit + 100)
        story = self._truncate_story(raw_story, self.story_word_limit) if raw_story else ""
        return story if story else self.get_fallback_story()


if __name__ == "__main__":
    # This block runs when the script is executed directly
    print("🎮 QUEST ACADEMY - Choose Your Adventure!")
    print("=" * 50)
    print("1️⃣  Basic Mode - 150 word stories, 3 questions")
    print("2️⃣  Advanced Mode - Progressive levels with longer stories")
    print("=" * 50)

    choice = input("Enter your choice (1 or 2): ").strip()

    if choice == "2":
        game = OllamaStoryQuizGameWithLevels()
    else:
        game = OllamaStoryQuizGame()

    game.play_game()