import google.generativeai as genai
from google.generativeai.types import HarmBlockThreshold, HarmCategory

import config


class GeminiHelper:
    def __init__(self):
        self.api_key = config.GEMINI_API_KEY
        self.model = None
        self.safety_settings = {
            HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
        }
        if self.api_key:
            self._configure()

    def _configure(self) -> None:
        try:
            genai.configure(api_key=self.api_key)
            self.model = genai.GenerativeModel(config.GEMINI_MODEL)
            print("Gemini API configured successfully.")
        except Exception as exc:
            print(f"Gemini configuration failed: {exc}")
            self.model = None

    def generate_intro(self, company_name, name="there", job_title="", location=""):
        if not self.model:
            return ""

        prompt = f"""
        You are writing one short cold-email opener.

        Sender:
        - Name: {config.SENDER_NAME}
        - Company: {config.SENDER_COMPANY}
        - Background: {config.SENDER_BACKGROUND}

        Offer:
        - Product Name: {config.PRODUCT_NAME}
        - Category: {config.PRODUCT_CATEGORY}
        - Description: {config.PRODUCT_DESCRIPTION}

        Recipient:
        - Name: {name or "there"}
        - Company: {company_name}
        - Role: {job_title or config.PRODUCT_TARGET_ROLE}
        - Location: {location or "their market"}

        Rules:
        - Write exactly one sentence.
        - Maximum 18 words.
        - No greeting.
        - Mention a likely workflow pain point in a natural way.
        - Avoid hype, exclamation marks, and buzzwords.
        - Keep it professional and specific.

        Output only the sentence.
        """

        try:
            response = self.model.generate_content(
                prompt,
                safety_settings=self.safety_settings,
                generation_config={
                    "temperature": config.GEMINI_TEMPERATURE,
                    "max_output_tokens": 100,
                },
            )
            result = response.text.strip().strip("\"'")
            if len(result.split()) > 20:
                return f"I thought {config.PRODUCT_NAME} might be relevant to the work your team is already doing."
            return result
        except Exception as exc:
            print(f"Gemini generation error: {exc}")
            return ""

    def extract_email_from_text(self, text, company_name):
        if not self.model:
            return ""

        prompt = f"""
        From the following text of {company_name}'s website, find:
        1. The most relevant contact email address.
        2. If there is no email, find the full URL of the best contact page.

        Rules:
        - Output only the email address or URL.
        - No commentary.
        - If absolutely nothing useful is found, output NOT_FOUND.

        Website Text:
        {text[:8000]}
        """

        try:
            response = self.model.generate_content(prompt)
            result = response.text.strip()
            if "NOT_FOUND" in result:
                return ""
            return result
        except Exception as exc:
            print(f"Gemini extraction error: {exc}")
            return ""

    def generate_full_email(
        self,
        company_name,
        name="there",
        title="",
        location="",
        web_context="",
        tone="Professional",
        cta="",
    ):
        if not self.model:
            return "AI Model not initialized."

        recipient_name = (name or "").strip()
        if recipient_name.lower() in {"valued partner", "nan", "none"}:
            recipient_name = ""
        greeting_name = recipient_name.split()[0] if recipient_name else "there"

        has_context = bool(web_context and web_context.strip())
        context_block = web_context[:1200] if has_context else "(none available)"
        personalization_rule = (
            "Use one concrete detail from the company context. Paraphrase it naturally and avoid generic praise."
            if has_context
            else "Use the company name, role, or location to keep the opener specific."
        )
        cta_text = cta.strip() if cta.strip() else config.DEFAULT_CTA

        prompt = f"""
        You are {config.SENDER_NAME} from {config.SENDER_COMPANY}.

        Sender background:
        {config.SENDER_BACKGROUND}

        Offer:
        - Product Name: {config.PRODUCT_NAME}
        - Product Category: {config.PRODUCT_CATEGORY}
        - Product Description: {config.PRODUCT_DESCRIPTION}
        - Main pain point solved: {config.PRODUCT_PAIN_POINT}

        Recipient:
        - Name: {recipient_name or "there"}
        - Role: {title or config.PRODUCT_TARGET_ROLE}
        - Company: {company_name}
        - Location: {location or "their market"}
        - Company Context: {context_block}

        Rules:
        1. No generic openers like "I hope you're well" or "I wanted to reach out".
        2. {personalization_rule}
        3. Mention one operational pain point in one sentence.
        4. Explain how the offer helps in one sentence.
        5. Use this CTA exactly, without rephrasing: "{cta_text}"
        6. Tone: {tone}. Keep it concise and peer-to-peer.
        7. Body length under 110 words.
        8. Subject line under 6 words.
        9. No em dashes.
        10. End with the signature block only.

        Exact format:
        Subject: [subject line]
        ---
        Hi {greeting_name},

        [2-3 short paragraphs]

        Best,
        {config.SENDER_NAME}
        {config.SENDER_TAGLINE}
        {config.SENDER_COMPANY}
        {config.SENDER_DOMAIN} | LinkedIn: {config.SENDER_LINKEDIN}

        ---
        {config.SENDER_ADDRESS}
        """

        try:
            response = self.model.generate_content(
                prompt,
                safety_settings=self.safety_settings,
                generation_config={
                    "temperature": config.GEMINI_TEMPERATURE,
                    "max_output_tokens": 8192,
                },
            )
            email_content = response.text.strip()
            if "Subject:" not in email_content:
                email_content = f"Subject: Quick idea for {company_name}\n---\n{email_content}"
            return email_content
        except Exception as exc:
            return f"Error generating email: {exc}"
