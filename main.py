import sys
import requests
import random
import logging
import re
import json
import time
from bs4 import BeautifulSoup
from typing import Dict, List, Any, Optional
logging.basicConfig(
    filename="bulk_submit_parsed.log",
    level=logging.INFO,
    format="%(asctime)s - %(message)s"
)


GOOGLE_FORM_URL = "URL"
SUBMIT_URL = GOOGLE_FORM_URL + "/formResponse"
REFERER_URL = GOOGLE_FORM_URL + "/viewform"

HEADERS = {
    "Referer": REFERER_URL,
    "User-Agent": "Mozilla/5.0"
}


def fetch_valid_entries(url):

    response = requests.get(url, headers=HEADERS)
    valid_entries = []
    if response.status_code == 200:
        soup = BeautifulSoup(response.text, "lxml")
        inputs = soup.findAll(
            'input',
            {
                'type': 'hidden',
                'name': lambda name: name and name.startswith('entry.')
            }
        )
        for input_tag in inputs:
            name_value = input_tag.get('name', '')
            cleaned_name = name_value.replace('_sentinel', '')
            entry_id = cleaned_name.replace('entry.', "")
            valid_entries.append((entry_id, cleaned_name))
        logging.info(f"Valid Entries: {valid_entries}")
    return valid_entries

def fetch_script_data(url):

    response = requests.get(url, headers=HEADERS)
    if response.status_code == 200:
        soup = BeautifulSoup(response.text, "lxml")
        script_tag = soup.find("script", string=re.compile("FB_PUBLIC_LOAD_DATA_"))
        if script_tag:
            script_content = script_tag.text
            match = re.search(r"var FB_PUBLIC_LOAD_DATA_ = (\[.+?\]);", script_content)
            if match:
                fb_data = json.loads(match.group(1))
                logging.info("FB_PUBLIC_LOAD_DATA_ extracted successfully")
                return fb_data
        logging.warning("FB_PUBLIC_LOAD_DATA_ not found")
    return None

def extract_options(valid_entries, fb_data):
    """Создаём словарь {entry.ID: [варианты ответов]}"""
    if not fb_data:
        logging.warning("FB Data is empty")
        return {}

    questions_data = fb_data[1][1]
    results = {}
    for question_block in questions_data:
        if question_block and isinstance(question_block, list):
            sub_blocks = question_block[4] if len(question_block) > 4 else []
            for sub_block in sub_blocks:
                if isinstance(sub_block, list):
                    entry_id = str(sub_block[0])
                    for _id, cleaned_name in valid_entries:
                        if _id == entry_id:
                            answers_block = sub_block[1]
                            if answers_block:
                                results[cleaned_name] = [
                                    answer[0] for answer in answers_block if answer
                                ]
    logging.info(f"Extracted Options: {results}")
    return results

# --------------------------
# Генерация случайного payload
# --------------------------
def generate_random_payload(form_options):
    return {key: random.choice(values) for key, values in form_options.items()}


def submit(payload):
    print(payload)
    r = requests.post(SUBMIT_URL, data=payload, headers=HEADERS)
    if r.status_code ==200:
        print("Sent")
    else:
        print("Not sent")

def build_payloads_from_counts(
    form_options: Dict[str, List[str]],
    counts_map: Dict[str, List[int]],
    total: int,
    *,
    seed: Optional[int] = None,
    fill_mode: str = "random"  # "random" | "first" | "none"
) -> List[Dict[str, Any]]:
    rng = random.Random(seed)

    # создаём пустые payload'ы
    payloads: List[Dict[str, Any]] = [dict() for _ in range(total)]

    # перемешиваем позиции, чтобы не было "первые все одинаковые"
    indices = list(range(total))
    rng.shuffle(indices)

    for entry, options in form_options.items():
        counts = counts_map.get(entry)

        if counts is None:
            # если counts не задан — просто заполнение по fill_mode
            counts = [0] * len(options)

        if len(counts) != len(options):
            raise ValueError(f"{entry}: counts длина {len(counts)} != options длина {len(options)}")

        if sum(counts) > total:
            raise ValueError(f"{entry}: сумма counts {sum(counts)} > total {total}")

        # строим "мешок" ответов
        bag = []
        for opt, cnt in zip(options, counts):
            bag.extend([opt] * cnt)

        rng.shuffle(bag)

        # раскладываем bag по payload'ам
        for k, val in enumerate(bag):
            payloads[indices[k]][entry] = val

        # добиваем оставшиеся payload'ы для этого entry
        for i in range(total):
            if entry in payloads[i]:
                continue
            if fill_mode == "random":
                payloads[i][entry] = rng.choice(options) if options else ""
            elif fill_mode == "first":
                payloads[i][entry] = options[0] if options else ""
            elif fill_mode == "none":
                pass
            else:
                raise ValueError("fill_mode должен быть: 'random', 'first', 'none'")

    return payloads
def generate_count_dict(form_options, total_number):
    counts_map = {}

    for key, options in form_options.items():
        s = input(f"{key} options={options}\nВведите counts через пробел (длина {len(options)}): ")
        parts = s.strip().split()

        if len(parts) != len(options):
            raise ValueError(f"{key}: нужно {len(options)} чисел, получили {len(parts)}")

        counts = [int(x) for x in parts]
        if any(c < 0 for c in counts):
            raise ValueError(f"{key}: counts должны быть >= 0")

        if sum(counts) > total_number:
            raise ValueError(f"{key}: сумма counts ({sum(counts)}) > total ({total_number})")

        counts_map[key] = counts

    return counts_map



def main():
    valid_entries = fetch_valid_entries(REFERER_URL)
    fb_data = fetch_script_data(REFERER_URL)
    form_options = extract_options(valid_entries, fb_data)
    n = int(input("Input all number of answers: "))
    submit(generate_random_payload(form_options))
    counts_map = generate_count_dict(form_options, n)
    print(counts_map)
    payloads = build_payloads_from_counts(form_options, counts_map, n, seed=42, fill_mode="random")



    if not form_options:
        print("Не удалось получить варианты ответов. Проверьте ссылку на форму.")
        return

    try:
        for i in payloads:

            submit(i)


    except ValueError:
        print("Введите число.")

if __name__ == "__main__":
    main()
