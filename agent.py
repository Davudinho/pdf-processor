"""
PDF Intelligence Agent – V2
============================
Ein ReAct-Agent der auf Basis von OpenAI Function Calling autonom
Aufgaben ausführt: Suchen, Lesen, Vergleichen, Berichte erstellen.

Ablauf:
1. User gibt Task-Text ein
2. Agent schickt Task + Tool-Definitionen an OpenAI
3. OpenAI antwortet mit Werkzeug-Aufrufen
4. Agent führt Werkzeuge aus, speichert Zwischenschritte in DB
5. Loop bis OpenAI "finish_with_report" aufruft
6. Ergebnis wird in DB gespeichert
"""

import os
import json
import logging
import time
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)

# Maximale Anzahl an Werkzeug-Aufrufen pro Task (Sicherheitsbremse)
MAX_STEPS = 10


# ─── Tool-Deklarationen für OpenAI ───────────────────────────────────────────

AGENT_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "list_all_documents",
            "description": "Listet alle verfügbaren Dokumente im System auf. Gibt Name, Kategorie, Seitenanzahl und Status zurück. Verwende dies zuerst, um zu sehen, welche Dokumente vorhanden sind.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_in_documents",
            "description": "Führt eine semantische Suche über alle Dokumente durch. Findet die relevantesten Textabschnitte zu einer Suchanfrage. Verwende dies, um gezielt nach Inhalten, Themen oder Begriffen zu suchen.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Die Suchanfrage auf Deutsch oder Englisch."
                    },
                    "top_k": {
                        "type": "integer",
                        "description": "Anzahl der Ergebnisse (Standard: 5, Maximum: 10)."
                    }
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_document_summary",
            "description": "Liest die KI-generierte Zusammenfassung, Kategorie und Schlüsselwörter eines bestimmten Dokuments. Verwende dies für einen schnellen Überblick.",
            "parameters": {
                "type": "object",
                "properties": {
                    "doc_id": {
                        "type": "string",
                        "description": "Die eindeutige ID des Dokuments (aus list_all_documents)."
                    }
                },
                "required": ["doc_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_document_full_text",
            "description": "Liest den vollständigen Rohtext eines Dokuments seitenweise. Verwende dies für tiefe Analysen, wenn Zusammenfassung nicht ausreicht. VORSICHT: Nutze dies nur wenn wirklich nötig, da es sehr viel Text liefert.",
            "parameters": {
                "type": "object",
                "properties": {
                    "doc_id": {
                        "type": "string",
                        "description": "Die eindeutige ID des Dokuments."
                    },
                    "max_chars": {
                        "type": "integer",
                        "description": "Maximale Zeichenanzahl (Standard: 8000, um Tokenlimits zu vermeiden)."
                    }
                },
                "required": ["doc_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "compare_two_documents",
            "description": "Vergleicht zwei Dokumente inhaltlich miteinander und hebt Gemeinsamkeiten und Unterschiede hervor. Gibt einen strukturierten Vergleich zurück.",
            "parameters": {
                "type": "object",
                "properties": {
                    "doc_id_1": {
                        "type": "string",
                        "description": "ID des ersten Dokuments."
                    },
                    "doc_id_2": {
                        "type": "string",
                        "description": "ID des zweiten Dokuments."
                    }
                },
                "required": ["doc_id_1", "doc_id_2"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "finish_with_report",
            "description": "Schließt die Aufgabe ab und gibt den finalen Bericht an den User zurück. MUSS immer am Ende aufgerufen werden, wenn die Aufgabe abgeschlossen ist.",
            "parameters": {
                "type": "object",
                "properties": {
                    "report": {
                        "type": "string",
                        "description": "Der vollständige, gut formatierte Bericht in Markdown. Beginne mit einer kurzen Zusammenfassung, dann strukturierte Details."
                    },
                    "key_findings": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Liste der 3-5 wichtigsten Erkenntnisse als kurze Sätze."
                    }
                },
                "required": ["report", "key_findings"]
            }
        }
    }
]


# ─── Der Agent ───────────────────────────────────────────────────────────────

class PdfAgent:
    """
    Autonomer ReAct-Agent für die PDF Intelligence Platform.

    Verwendet OpenAI Function Calling für den Reasoning-Action-Loop:
    - OpenAI entscheidet, welche Werkzeuge aufgerufen werden
    - Agent führt Werkzeuge aus und gibt Ergebnisse zurück
    - Loop endet bei "finish_with_report"
    """

    def __init__(self, ai_processor, db_manager, qdrant_manager):
        self.ai = ai_processor          # AIProcessor instance
        self.db = db_manager            # MongoDBManager instance
        self.qdrant = qdrant_manager    # QdrantManager instance

    def run(self, task_text: str, task_id: str) -> dict:
        """
        Führt einen Agenten-Task aus.
        Aktualisiert die DB mit Zwischenschritten und dem Endergebnis.

        :param task_text: Die natürlichsprachliche Aufgabe des Users
        :param task_id:   Die MongoDB-Task-ID für Status-Updates
        :return: Dict mit 'report' und 'key_findings'
        """
        logger.info(f"[Agent] Starte Task {task_id}: {task_text[:80]}...")

        if not self.ai.client:
            error = "KI-Prozessor nicht initialisiert (API-Key fehlt)."
            self.db.update_agent_task(task_id, status="failed", error_message=error)
            return {"error": error}

        system_prompt = (
            "Du bist ein intelligenter Dokumenten-Assistent für ein PDF-Analyse-System. "
            "Du hast Zugriff auf eine Sammlung von PDF-Dokumenten und kannst diese durchsuchen, "
            "lesen und analysieren. "
            "\n\n"
            "Deine Aufgabe:\n"
            "1. Analysiere die Anfrage des Users.\n"
            "2. Benutze die verfügbaren Werkzeuge systematisch, um die Aufgabe zu lösen.\n"
            "3. Beginne immer mit 'list_all_documents', um zu wissen, was verfügbar ist.\n"
            "4. Schließe IMMER mit 'finish_with_report' ab, wenn du fertig bist.\n"
            "5. Antworte auf Deutsch.\n"
            "\n"
            "Wichtig: Rufe nie dasselbe Werkzeug mit denselben Parametern zweimal auf."
        )

        # Konversationsverlauf für OpenAI (Multi-Turn)
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": task_text}
        ]

        step_count = 0
        final_result = None

        try:
            while step_count < MAX_STEPS:
                step_count += 1
                logger.info(f"[Agent] Schritt {step_count}/{MAX_STEPS}")

                # OpenAI aufrufen
                try:
                    response = self.ai.client.chat.completions.create(
                        model=self.ai.model,
                        messages=messages,
                        tools=AGENT_TOOLS,
                        temperature=0.2,
                    )
                except Exception as api_err:
                    raise RuntimeError(f"OpenAI API-Fehler in Schritt {step_count}: {api_err}")

                response_message = response.choices[0].message
                
                # Assistenten-Nachricht dem Verlauf hinzufügen (erforderlich für Tool-Aufrufe)
                messages.append(response_message.model_dump(exclude_unset=True))

                if not response_message.tool_calls:
                    # Kein Werkzeug aufgerufen – Modell hat direkt geantwortet
                    text_reply = response_message.content or ""
                    logger.warning(f"[Agent] OpenAI antwortete mit Text statt Tool-Call: {text_reply[:200]}")
                    final_result = {
                        "report": text_reply or "Aufgabe abgeschlossen (kein strukturierter Bericht).",
                        "key_findings": [],
                    }
                    break

                for tool_call in response_message.tool_calls:
                    tool_name = tool_call.function.name
                    try:
                        tool_args = json.loads(tool_call.function.arguments)
                    except json.JSONDecodeError:
                        tool_args = {}

                    logger.info(f"[Agent] Werkzeug '{tool_name}' mit {tool_args}")

                    # Werkzeug ausführen
                    tool_result = self._execute_tool(tool_name, tool_args)

                    # Zwischenschritt in DB speichern
                    self.db.add_agent_task_step(
                        task_id=task_id,
                        step_num=step_count,
                        tool=tool_name,
                        tool_input=tool_args,
                        tool_output=self._summarize_output(tool_result),
                    )

                    # Sonderfall: finish_with_report beendet den Loop
                    if tool_name == "finish_with_report":
                        final_result = {
                            "report": tool_args.get("report", ""),
                            "key_findings": tool_args.get("key_findings", []),
                        }
                        # Werkzeugergebnis für die aktuelle Iteration hinzufügen
                        messages.append({
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "content": json.dumps({"status": "finished"})
                        })
                        break

                    # Ergebnis für OpenAI vorbereiten
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "name": tool_name,
                        "content": json.dumps(tool_result, ensure_ascii=False)
                    })

                if final_result:
                    break

                # Kurze Pause zwischen Schritten (Rate-Limit-Schutz)
                time.sleep(2)

            # Max Steps erreicht ohne finish_with_report
            if not final_result:
                final_result = {
                    "report": f"Der Agent hat die maximale Anzahl von {MAX_STEPS} Schritten erreicht. "
                              "Bitte formuliere die Aufgabe spezifischer.",
                    "key_findings": ["Aufgabe konnte nicht vollständig abgeschlossen werden."],
                }

            # Ergebnis in DB speichern
            self.db.update_agent_task(
                task_id=task_id,
                status="done",
                report=final_result["report"],
                key_findings=final_result["key_findings"],
            )
            logger.info(f"[Agent] Task {task_id} abgeschlossen.")

            # Webhook für n8n/Zapier auslösen
            webhook_url = os.environ.get("WEBHOOK_URL")
            if webhook_url:
                try:
                    import urllib.request
                    payload = json.dumps({
                        "task_id": task_id,
                        "task_text": task_text,
                        "status": "done",
                        "report": final_result["report"],
                        "key_findings": final_result["key_findings"]
                    }).encode('utf-8')
                    req = urllib.request.Request(
                        webhook_url, 
                        data=payload, 
                        headers={'Content-Type': 'application/json', 'User-Agent': 'PDF-Intelligence-Agent'}
                    )
                    urllib.request.urlopen(req, timeout=5)
                    logger.info(f"[Agent] Webhook erfolgreich an {webhook_url} gesendet.")
                except Exception as e:
                    logger.error(f"[Agent] Webhook Fehler: {e}")

            return final_result

        except Exception as e:
            error_msg = str(e)
            logger.error(f"[Agent] Fehler in Task {task_id}: {error_msg}")
            self.db.update_agent_task(
                task_id=task_id,
                status="failed",
                error_message=error_msg,
            )
            return {"error": error_msg}

    # ─── Werkzeug-Dispatcher ─────────────────────────────────────────────────

    def _execute_tool(self, tool_name: str, args: dict) -> dict:
        """Verteilt Werkzeug-Aufrufe an die entsprechenden Methoden."""
        try:
            if tool_name == "list_all_documents":
                return self._list_all_documents()
            elif tool_name == "search_in_documents":
                query = str(args.get("query", ""))
                try:
                    top_k = min(int(args.get("top_k", 5)), 10)
                except (ValueError, TypeError):
                    top_k = 5
                return self._search_in_documents(query=query, top_k=top_k)
            elif tool_name == "get_document_summary":
                return self._get_document_summary(str(args.get("doc_id", "")))
            elif tool_name == "get_document_full_text":
                try:
                    max_chars = int(args.get("max_chars", 8000))
                except (ValueError, TypeError):
                    max_chars = 8000
                return self._get_document_full_text(
                    doc_id=str(args.get("doc_id", "")),
                    max_chars=max_chars,
                )
            elif tool_name == "compare_two_documents":
                doc_id_1 = str(args.get("doc_id_1", ""))
                doc_id_2 = str(args.get("doc_id_2", ""))
                if not doc_id_1 or not doc_id_2:
                    return {"error": "Fehlende Parameter: doc_id_1 und doc_id_2 muessen angegeben werden."}
                return self._compare_two_documents(
                    doc_id_1=doc_id_1,
                    doc_id_2=doc_id_2,
                )
            elif tool_name == "finish_with_report":
                return {"status": "finished"}
            else:
                return {"error": f"Unbekanntes Werkzeug: {tool_name}"}
        except Exception as e:
            logger.error(f"[Agent] Fehler bei Werkzeug '{tool_name}': {e}")
            return {"error": str(e)}

    # ─── Werkzeug-Implementierungen ───────────────────────────────────────────

    def _list_all_documents(self) -> dict:
        """Gibt alle strukturierten (fertig analysierten) Dokumente zurück."""
        try:
            all_docs = self.db.get_all_documents(limit=100)
            ready_docs = [
                {
                    "doc_id": d.get("doc_id"),
                    "filename": d.get("filename"),
                    "category": d.get("category", "Unbekannt"),
                    "page_count": d.get("page_count", 0),
                    "status": d.get("status"),
                }
                for d in all_docs
                if d.get("status") == "structured"
            ]
            if not ready_docs:
                return {"documents": [], "message": "Keine fertig analysierten Dokumente vorhanden."}
            return {"documents": ready_docs, "total": len(ready_docs)}
        except Exception as e:
            return {"error": f"Fehler beim Laden der Dokumente: {e}"}

    def _search_in_documents(self, query: str, top_k: int = 5) -> dict:
        """Semantische Suche via Qdrant."""
        if not query.strip():
            return {"error": "Suchanfrage ist leer."}

        if not self.qdrant.is_connected():
            return self._fallback_keyword_search(query, top_k)

        try:
            query_embedding = self.ai.create_embedding(query)
            if not query_embedding:
                return {"error": "Embedding für Suchanfrage konnte nicht erstellt werden."}

            results = self.qdrant.search_similar(query_embedding, limit=top_k)
            if not results:
                return {"results": [], "message": "Keine passenden Ergebnisse gefunden."}

            return {
                "results": [
                    {
                        "text": r.get("text", "")[:500],
                        "doc_id": r.get("doc_id"),
                        "page_num": r.get("page_num"),
                        "score": round(r.get("score", 0), 3),
                    }
                    for r in results
                ],
                "total": len(results),
            }
        except Exception as e:
            return {"error": f"Suche fehlgeschlagen: {e}"}

    def _fallback_keyword_search(self, query: str, top_k: int) -> dict:
        """Einfache Keyword-Suche in den Dokument-Zusammenfassungen (wenn Qdrant offline)."""
        try:
            keywords = query.lower().split()
            all_docs = self.db.get_all_documents(limit=100)
            matches = []
            for doc in all_docs:
                if doc.get("status") != "structured":
                    continue
                text = f"{doc.get('filename', '')} {doc.get('summary', '')} {' '.join(doc.get('keywords', []))}".lower()
                score = sum(1 for kw in keywords if kw in text)
                if score > 0:
                    matches.append({"doc_id": doc["doc_id"], "filename": doc["filename"], "score": score})

            matches.sort(key=lambda x: x["score"], reverse=True)
            return {
                "results": matches[:top_k],
                "message": "Qdrant offline – Fallback-Suche in Zusammenfassungen verwendet.",
            }
        except Exception as e:
            return {"error": f"Fallback-Suche fehlgeschlagen: {e}"}

    def _get_document_summary(self, doc_id: str) -> dict:
        """Liest die KI-Zusammenfassung eines Dokuments."""
        if not doc_id:
            return {"error": "doc_id fehlt."}
        try:
            details = self.db.get_document_details(doc_id)
            if not details:
                return {"error": f"Dokument '{doc_id}' nicht gefunden."}
            return {
                "doc_id": doc_id,
                "filename": details.get("filename"),
                "category": details.get("category", "Unbekannt"),
                "summary": details.get("summary", "Keine Zusammenfassung verfügbar."),
                "keywords": details.get("keywords", []),
                "page_count": details.get("total_pages", 0),
            }
        except Exception as e:
            return {"error": f"Fehler beim Laden der Zusammenfassung: {e}"}

    def _get_document_full_text(self, doc_id: str, max_chars: int = 8000) -> dict:
        """Liest den Rohtext eines Dokuments (mit Zeichenbegrenzung)."""
        if not doc_id:
            return {"error": "doc_id fehlt."}
        try:
            pages = self.db.get_raw_text(doc_id)
            if not pages:
                return {"error": f"Kein Text für Dokument '{doc_id}' gefunden."}

            full_text = "\n\n".join([
                f"--- Seite {p.get('page_num', '?')} ---\n{p.get('raw_text', '')}"
                for p in pages if p.get('raw_text')
            ])

            truncated = len(full_text) > max_chars
            return {
                "doc_id": doc_id,
                "text": full_text[:max_chars],
                "total_chars": len(full_text),
                "truncated": truncated,
                "page_count": len(pages),
            }
        except Exception as e:
            return {"error": f"Fehler beim Lesen des Textes: {e}"}

    def _compare_two_documents(self, doc_id_1: str, doc_id_2: str) -> dict:
        """Vergleicht zwei Dokumente inhaltlich via KI."""
        if not doc_id_1 or not doc_id_2:
            return {"error": "Beide doc_ids müssen angegeben werden."}

        try:
            summary_1 = self._get_document_summary(doc_id_1)
            summary_2 = self._get_document_summary(doc_id_2)

            if "error" in summary_1:
                return {"error": f"Dokument 1: {summary_1['error']}"}
            if "error" in summary_2:
                return {"error": f"Dokument 2: {summary_2['error']}"}

            compare_prompt = (
                f"Vergleiche diese zwei Dokumente und nenne die wichtigsten Gemeinsamkeiten und Unterschiede:\n\n"
                f"**Dokument 1: {summary_1['filename']}**\n"
                f"Kategorie: {summary_1['category']}\n"
                f"Zusammenfassung: {summary_1['summary']}\n"
                f"Schlüsselwörter: {', '.join(summary_1['keywords'][:10])}\n\n"
                f"**Dokument 2: {summary_2['filename']}**\n"
                f"Kategorie: {summary_2['category']}\n"
                f"Zusammenfassung: {summary_2['summary']}\n"
                f"Schlüsselwörter: {', '.join(summary_2['keywords'][:10])}\n\n"
                "Antworte als JSON mit den Feldern: "
                "'similarities' (Liste), 'differences' (Liste), 'recommendation' (String)."
            )

            raw = self.ai._generate_with_retry(
                system_prompt="Du bist ein Dokumentenanalyst. Antworte nur auf Deutsch als JSON.",
                user_prompt=compare_prompt,
                config={"response_format": {"type": "json_object"}, "temperature": 0.1, "max_tokens": 1000},
            )

            comparison = self.ai._parse_json_safe(raw) if raw else {}
            return {
                "doc_1": {"doc_id": doc_id_1, "filename": summary_1["filename"]},
                "doc_2": {"doc_id": doc_id_2, "filename": summary_2["filename"]},
                "similarities": comparison.get("similarities", []),
                "differences": comparison.get("differences", []),
                "recommendation": comparison.get("recommendation", ""),
            }
        except Exception as e:
            return {"error": f"Vergleich fehlgeschlagen: {e}"}

    def _summarize_output(self, output: dict, max_chars: int = 400) -> str:
        """Kürzt Tool-Output für die Anzeige in der UI."""
        try:
            text = json.dumps(output, ensure_ascii=False)
            if len(text) > max_chars:
                return text[:max_chars] + "..."
            return text
        except Exception:
            return str(output)[:max_chars]
