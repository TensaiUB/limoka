__version__ = (1, 0, 4)
# meta banner: "🇷🇺"
# meta developer: @midga3_modules & IDEA="@bleizix & fork by @mihailkotovski & fork fork by @nenfiz"
# scope: hikka_only
# scope: hikka_min 1.2.10

import logging
import random
import re
from .. import loader, utils

logger = logging.getLogger(__name__)

@loader.tds
class NiceMessagesMod(loader.Module):
    """Я СКАЗАЛ ГОЙДАААА"""

    strings = {
        "name": "ZZZ ZOVV",
        "_cls_doc": "Я СКАЗАЛ ГОЙДАААА",
        "config_enable_doc": "ВКЛЮЧИТЬ ГОЙДУУУУ",
        "config_effects_frequency_doc": "Частота эффектов (ZOV, ГОЙДА, 🇷🇺, 🔥, ❤️‍🔥, 🤙🏻, 💨)",
        "config_enable_emojis_doc": "Включить смайлики 🔥❤️‍🔥🤙🏻💨",
        "config_enable_slang_doc": "Пацанский матерный сленг (привет → здарова, пиздец → трындец)",
        "error_message": "Ой-ой! Что-то пошло по пиздецу... Вот оригинал: {}",
    }

    strings_ru = {
        "_cls_doc": "Я СКАЗАЛ ГОЙДАААА",
        "config_enable_doc": "ВКЛЮЧИТЬ ГОЙДУУУУ",
        "config_effects_frequency_doc": "Частота эффектов (ZOV, ГОЙДА, 🇷🇺, 🔥, ❤️‍🔥, 🤙🏻, 💨)",
        "config_enable_emojis_doc": "Включить смайлики 🔥❤️‍🔥🤙🏻💨",
        "config_enable_slang_doc": "Пацанский матерный сленг (привет → здарова, пиздец → трындец)",
        "error_message": "Ой-ой! Что-то пошло по пиздецу... Вот оригинал: {}",
    }

    def __init__(self):
        self.config = loader.ModuleConfig(
            loader.ConfigValue(
                "enable",
                True,
                lambda: self.strings("config_enable_doc"),
                validator=loader.validators.Boolean(),
            ),
            loader.ConfigValue(
                "effects_frequency",
                2,
                lambda: self.strings("config_effects_frequency_doc"),
                validator=loader.validators.Integer(minimum=0, maximum=4),
            ),
            loader.ConfigValue(
                "enable_emojis",
                True,
                lambda: self.strings("config_enable_emojis_doc"),
                validator=loader.validators.Boolean(),
            ),
            loader.ConfigValue(
                "enable_slang",
                False,
                lambda: self.strings("config_enable_slang_doc"),
                validator=loader.validators.Boolean(),
            ),
        )
        
        self.emojis = ["🔥", "❤️‍🔥", "🤙🏻🤙🏻🤙🏻", "💨"]
        self.flags = ["🇷🇺"]
        self.suffixes = ["ZOV", "ГОЙДА", "🆉🅾🆅", "𓆩ƵꝊꝞ𓆪", "ᶻᴼⱽ", "꧁•⊹٭ZOV٭⊹•꧂", "G̶O̶Y̶D̶A̶", "〜G∿O∿Y∿D∿A〜"]
        self.extended_exclamations = ["!!!"]
        self.slang_dict = {
            "привет": "здарова", "здравствуй": "здаров", "как": "чё", "хорошо": "заебись",
            "отлично": "пиздец как", "нормально": "нормас", "плохо": "всрато",
            "друг": "братан", "пока": "вали", "да": "канеш", "нет": "нахуй иди",
            "спасибо": "респект", "пожалуйста": "по братски", "извини": "сорян", "извините": "проехали",
            "дома": "на хате", "работа": "темка", "деньги": "бабки", "проблема": "косяк",
            "бери": "хапай", "иди": "топай",
            "люди": "пацаны", "человек": "перс", "жду": "торчу", "пошли": "погнали",
            "похоже": "пох", "понял": "врубился", "не понял": "чё за хуйня", "быстро": "на шухере",
            "тихо": "по-тихому", "громко": "на всю катушку", "позже": "потом прикинем",
            "сейчас": "похер ща", "завтра": "на завтраке", "сегодня": "по сей день",
            "есть": "в наличии", "хочу": "загон", "надо": "втрындец",
            "сделал": "забацал", "готово": "прокатило", "класс": "бомба", "круто": "охуенно",
            "где": "хде", "зачем": "нахуя",
            "почему": "чёзанах", "вопрос": "тема", "ответ": "отмазка", "бери": "гребанул",
            "давай": "вали давай", "бери": "хватай", "уйди": "съеби"
        }

    async def client_ready(self, client, db):
        self.client = client
        self.db = db
        self._me = await client.get_me()

    def _get_frequency_prob(self):
        frequency_idx = self.config["effects_frequency"]
        if frequency_idx == 0: return 0.15
        if frequency_idx == 1: return 0.35
        if frequency_idx == 3: return 0.85
        if frequency_idx == 4: return 1.00
        return 0.65

    def _transform_patriotic_letters(self, text):
        eng_to_rus = {
            'a': 'а', 'A': 'А', 'b': 'б', 'B': 'Б', 'c': 'с', 'C': 'С', 'd': 'д', 'D': 'Д',
            'e': 'е', 'E': 'Е', 'f': 'ф', 'F': 'Ф', 'g': 'г', 'G': 'Г', 'h': 'х', 'H': 'Х',
            'i': 'и', 'I': 'И', 'j': 'й', 'J': 'Й', 'k': 'к', 'K': 'К', 'l': 'л', 'L': 'Л',
            'm': 'м', 'M': 'М', 'n': 'н', 'N': 'Н', 'o': 'о', 'O': 'О', 'p': 'п', 'P': 'П',
            'r': 'р', 'R': 'Р', 's': 'с', 'S': 'С', 't': 'т', 'T': 'Т', 'u': 'у', 'U': 'У',
            'v': 'в', 'V': 'В', 'x': 'х', 'X': 'Х', 'y': 'у', 'Y': 'У', 'z': 'з', 'Z': 'З',
            'q': 'к', 'Q': 'К', 'w': 'в', 'W': 'В'
        }
        for eng, rus in eng_to_rus.items():
            text = text.replace(eng, rus)
        text = text.replace('з', 'Z').replace('З', 'Z').replace('в', 'V').replace('В', 'V').replace('о', 'O').replace('О', 'O')
        return text

    def _transform_exclamations(self, ending_punctuation):
        def replace_match(match): return random.choice(self.extended_exclamations)
        return re.sub(r"!", replace_match, ending_punctuation)

    def _transform_slang(self, text):
        if self.config["enable_slang"]:
            words = text.split()
            transformed_words = []
            for word in words:
                word_lower = word.lower()
                if word_lower in self.slang_dict:
                    new_word = self.slang_dict[word_lower]
                    if word[0].isupper():
                        new_word = new_word.capitalize()
                    transformed_words.append(new_word)
                else:
                    transformed_words.append(word)
            return " ".join(transformed_words)
        return text

    def _apply_patriotic_transformations(self, text):
        if not text.strip():
            return text

        effects_prob = self._get_frequency_prob()

        text = self._transform_slang(text)
        text = self._transform_patriotic_letters(text)

        sentences = re.split(r'([.!?]+\s*)', text)
        result_parts = []

        for i in range(0, len(sentences), 2):
            sentence_part = sentences[i].strip() if i < len(sentences) else ""
            ending_punctuation = sentences[i+1] if i+1 < len(sentences) else ""

            if not sentence_part and ending_punctuation:
                if "!" in ending_punctuation:
                    ending_punctuation = self._transform_exclamations(ending_punctuation)
                result_parts.append(ending_punctuation)
                continue
            
            if not sentence_part and not ending_punctuation:
                continue

            words = sentence_part.split()
            processed_words = []
            for w in words:
                if not w:
                    processed_words.append(w)
                    continue
                word_with_effects = w
                if random.random() < effects_prob:
                    word_with_effects += f" {random.choice(self.flags)}"
                if self.config["enable_emojis"] and random.random() < effects_prob:
                    word_with_effects += f" {random.choice(self.emojis)}"
                processed_words.append(word_with_effects)
            sentence_part = " ".join(processed_words).strip()

            if random.random() < effects_prob:
                if sentence_part: 
                    sentence_part += f" {random.choice(self.suffixes)}"
                else: 
                    sentence_part = random.choice(self.suffixes)
                sentence_part = sentence_part.strip()

            result_parts.append(sentence_part)
            result_parts.append(ending_punctuation)
            
        return "".join(result_parts)

    @loader.watcher(tags=["out", "no_commands"])
    async def patriotic_watcher(self, message):
        """Я СКАЗАЛ СОСАТЬ СУК"""
        if not message.out:
            return

        if not self.config["enable"]:
            return

        try:
            original_text = message.text
            if not original_text:
                return

            modified_text = self._apply_patriotic_transformations(original_text)
            
            if modified_text != original_text:
                await utils.answer(message, modified_text)
                
        except Exception as e:
            logger.error(f"Error in patriotic transformation: {e}")
            error_text = self.strings("error_message").format(original_text)
            await utils.answer(message, error_text)