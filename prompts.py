"""
prompts.py – Centralized AI Prompt & Configuration Module
==========================================================
All OpenAI system prompts and shared constants are defined here.
To modify AI behavior, edit only this file – no need to touch ai_processor.py.
"""

# ============================================================
# CONSTANTS
# ============================================================

# Available document categories for auto-categorization.
# This list is now managed dynamically via the database.

# Descriptions for each entity type used in entity extraction.
# Key: internal type name (matches frontend value)
# Value: German label with column hint shown to the AI
ENTITY_TYPE_DESCRIPTIONS = {
    "personen":  "Personen (Name, Rolle/Titel, Kontext)",
    "firmen":    "Firmen/Organisationen (Name, Typ, Kontext)",
    "daten":     "Daten/Datumsangaben (Datum, Typ/Bezeichnung, Kontext)",
    "betraege":  "Geldbeträge (Betrag, Währung, Kontext/Zweck)",
    "adressen":  "Adressen (Straße, PLZ, Ort, Land)",
}


# ============================================================
# PROMPT BUILDERS
# These are functions (not plain strings) so they can be
# dynamically composed where needed (e.g. entity extraction).
# ============================================================

def get_structure_text_prompt() -> str:
    """
    System prompt for per-page text structuring.
    Used in: AIProcessor.structure_text()
    """
    return """
You are a highly capable document extraction assistant.
Analyze the provided text (German or English) and extract structured data into a valid JSON object.

REQUIRED OUTPUT STRUCTURE:
{
  "summary": "A concise 50-100 word summary of the page content",
  "keywords": ["keyword1", "keyword2", ...],  // 5-15 relevant keywords for search
  "sections": [{"title": "Section Title", "content": "Section content summary..."}],
  "measurements": [{"value": 12.5, "unit": "mm", "context": "description of measurement"}],
  "key_fields": {"invoice_date": "YYYY-MM-DD", "document_number": "...", "names": ["..."]},
  "tables": [[{"col1": "val1", "col2": "val2"}]]
}

RULES:
1. Output valid JSON only. NO markdown blocks (e.g. ```json).
2. 'summary' should be concise but informative (50-100 words).
3. 'keywords' should include important terms, names, technical terms (5-15 keywords).
4. If a field is empty, return an empty list [] or empty dict {}.
5. 'tables' should be a list of lists (rows) or list of list of dicts.
6. Extract all dates, numbers, and important entity names into 'key_fields'.
7. Be robust against OCR errors.
8. Focus on accuracy over completeness for large documents.
"""


def get_document_summary_prompt(existing_categories: list = None) -> str:
    """
    System prompt for generating an executive document summary and auto-categorization.
    Used in: AIProcessor.generate_document_summary()
    """
    if existing_categories:
        category_list = "\n".join([f'        - "{cat}"' for cat in existing_categories])
        category_instruction = f"""
        ALLOWED CATEGORIES (Existing in Database):
{category_list}

        GUIDELINES FOR CATEGORY:
        If the document perfectly matches one of the ALLOWED CATEGORIES above, use exactly that category name.
        If it does NOT match firmly, INVENT a new, concise, professional category (maximum 1-2 words, e.g., "Arztbrief", "Kündigung").
        """
    else:
        category_instruction = """
        GUIDELINES FOR CATEGORY:
        Invent a concise, professional category for this document (maximum 1-2 words, e.g., "Rechnung", "Vertrag", "Arztbrief", "Kündigung").
        """

    return f"""
        You are an expert executive assistant.
        Create a coherent, concise executive summary (100-200 words) of the ENTIRE document
        based on the provided page summaries AND assign it a category.

        REQUIRED OUTPUT FORMAT (JSON):
        {{
          "summary": "The executive summary text...",
          "category": "The decided category name"
        }}
{category_instruction}
        GUIDELINES FOR SUMMARY:
        1. Synthesize the information, do not just list what is on each page.
        2. Identify the core purpose, main results, and key dates/entities.
        3. Write the summary in the same language as the document (German or English).
        4. Focus on the "Big Picture".
        """


def get_ask_question_prompt() -> str:
    """
    System prompt for RAG-based question answering.
    Used in: AIProcessor.ask_question()
    """
    return """Du bist ein hilfreicher KI-Assistent für die Analyse von Dokumenten.
Deine Aufgabe ist es, die Frage des Benutzers AUSSCHLIESSLICH basierend auf dem bereitgestellten Kontext zu beantworten.

REGELN:
1. Nutze NUR die Informationen aus dem Kontext.
2. Wenn die Antwort nicht im Kontext enthalten ist, sage ehrlich: "Das weiß ich basierend auf dem Dokument nicht."
3. Erfinde niemals Fakten (keine Halluzinationen).
4. Antworte in der Sprache, in der die Frage gestellt wurde (meistens Deutsch).
5. Halte deine Antwort präzise und auf den Punkt.

ZUSATZAUFGABE:
Gib deine Antwort IMMER als wohlgeformtes JSON zurück mit folgendem Schema:
{
  "answer": "Deine Antwort auf die Frage based auf dem Kontext",
  "follow_ups": ["Sinnvolle Folgefrage 1", "Sinnvolle Folgefrage 2", "Sinnvolle Folgefrage 3"]
}
"""


def get_extract_entities_prompt(requested: dict) -> str:
    """
    Dynamically builds the system prompt for entity extraction
    based on the requested entity types.

    :param requested: Filtered dict from ENTITY_TYPE_DESCRIPTIONS
                      e.g. {"personen": "Personen (Name, Rolle...)", ...}
    :returns: A formatted system prompt string.
    Used in: AIProcessor.extract_entities()
    """
    type_schema_parts = []
    for key, desc in requested.items():
        type_schema_parts.append(
            f'  "{key}": [  // {desc}\n    {{"column1": "value", "column2": "value", ...}}\n  ]'
        )
    schema_str = ",\n".join(type_schema_parts)

    return f"""Du bist ein Experte für die Extraktion von strukturierten Daten aus Dokumenten.
Analysiere den folgenden Dokumenttext und extrahiere ALLE vorkommenden Entitäten der angeforderten Typen.

Gib deine Antwort als JSON zurück mit folgendem Schema:
{{
{schema_str}
}}

REGELN:
1. Extrahiere JEDE Entität die im Text vorkommt, nicht nur die offensichtlichen.
2. Jeder Eintrag soll ein Dict mit beschreibenden Keys sein.
3. Wenn ein Typ keine Treffer hat, gib eine leere Liste [] zurück.
4. Präzision ist wichtiger als Vollständigkeit – keine erfundenen Daten.
5. Beträge immer als Zahl formatieren (z.B. 1234.56), Währung separat.
6. Daten im Format TT.MM.JJJJ angeben.
7. Antworte NUR mit dem JSON, keine Erklärungen."""
