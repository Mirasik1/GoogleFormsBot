import requests
import random
import re
import json
import logging
from bs4 import BeautifulSoup
from typing import Dict, List, Any

logging.basicConfig(
    filename="bulk_submit_parsed.log",
    level=logging.INFO,
    format="%(asctime)s - %(message)s"
)


class FormModel:
    @staticmethod
    def _get_full_url(url: str) -> str:
        if "forms.gle" in url:
            try:
                response = requests.head(url, allow_redirects=True, timeout=5)
                url = response.url
            except Exception as e:
                logging.error(f"Failed to resolve short URL: {e}")

        if 'viewform' not in url:
            url = url.rsplit('/', 1)[0] + '/viewform'
        return url

    @classmethod
    def parse_form(cls, form_url: str) -> Dict[str, Any]:
        referer_url = cls._get_full_url(form_url)
        headers = {"Referer": referer_url, "User-Agent": "Mozilla/5.0"}

        response = requests.get(referer_url, headers=headers, allow_redirects=True)
        if response.status_code != 200:
            return {}

        soup = BeautifulSoup(response.text, "lxml")
        script_tag = soup.find("script", string=re.compile("FB_PUBLIC_LOAD_DATA_"))
        if not script_tag:
            return {}

        match = re.search(r"var FB_PUBLIC_LOAD_DATA_ = (\[.+?\]);", script_tag.text)
        if not match:
            return {}

        fb_data = json.loads(match.group(1))
        questions_data = fb_data[1][1]
        result_form = {}

        for question_block in questions_data:
            if question_block and isinstance(question_block, list):
                question_title = question_block[1]
                sub_blocks = question_block[4] if len(question_block) > 4 else []
                for sub_block in sub_blocks:
                    if isinstance(sub_block, list) and len(sub_block) > 0:
                        entry_id = str(sub_block[0])
                        cleaned_name = f"entry.{entry_id}"
                        answers_block = sub_block[1]
                        if answers_block:
                            options = [answer[0] for answer in answers_block if answer]
                            result_form[cleaned_name] = {
                                "title": question_title,
                                "options": options
                            }
        return result_form

    @classmethod
    def submit_payloads(cls, form_url: str, form_options: Dict[str, Any], counts_map: Dict[str, List[int]], total: int,
                        mode: str) -> int:
        referer_url = cls._get_full_url(form_url)
        submit_url = referer_url.rsplit('/', 1)[0] + '/formResponse'
        headers = {"Referer": referer_url, "User-Agent": "Mozilla/5.0"}

        rng = random.Random()
        payloads: List[Dict[str, Any]] = [dict() for _ in range(total)]

        if mode == "deterministic":
            indices = list(range(total))
            rng.shuffle(indices)

            for entry, data in form_options.items():
                options = data["options"]
                counts = counts_map.get(entry, [0] * len(options))
                bag = []
                for opt, cnt in zip(options, counts):
                    bag.extend([opt] * cnt)
                rng.shuffle(bag)

                for k, val in enumerate(bag):
                    if k < len(payloads):
                        payloads[indices[k]][entry] = val

                for i in range(total):
                    if entry not in payloads[i]:
                        payloads[i][entry] = rng.choice(options) if options else ""
        else:
            for i in range(total):
                payload = {}
                for entry, data in form_options.items():
                    options = data["options"]
                    payload[entry] = rng.choice(options) if options else ""
                payloads[i] = payload

        success_count = 0
        for payload in payloads:
            r = requests.post(submit_url, data=payload, headers=headers)
            if r.status_code == 200:
                success_count += 1
                logging.info(f"Sent: {payload}")
            else:
                logging.warning(f"Failed: {payload}")

        return success_count