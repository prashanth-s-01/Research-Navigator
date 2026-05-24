from typing import Any, Dict, List, Optional


PROMPT_TEMPLATE = """You are a research assistant.
Use the following source passages to answer the question truthfully, concisely, and with citations.

{context}

Question:
{question}

Answer:
"""


def format_source_snippets(snippets: List[str], max_snippets: int = 5) -> str:
    formatted_snippets = []
    for index, snippet in enumerate(snippets[:max_snippets], start=1):
        snippet_text = snippet.strip()
        if not snippet_text:
            continue
        formatted_snippets.append(f"SOURCE {index}:\n{snippet_text}\n")
    return "\n".join(formatted_snippets) if formatted_snippets else "No sources were provided."


def build_groq_prompt(question: str, snippets: List[str], citations: Optional[List[str]] = None) -> str:
    source_text = format_source_snippets(snippets)
    citation_text = "\n".join(f"- {citation}" for citation in citations) if citations else ""
    if citation_text:
        source_text += f"\nCitations:\n{citation_text}\n"

    return PROMPT_TEMPLATE.format(context=source_text, question=question)


def extract_retrieval_snippets(retrieval: Dict[str, Any], max_snippets: int = 5) -> List[str]:
    snippets: List[str] = []
    if retrieval.get("answer"):
        snippets.append(str(retrieval["answer"]))

    if retrieval.get("content"):
        snippets.append(str(retrieval["content"]))

    if retrieval.get("text"):
        snippets.append(str(retrieval["text"]))

    if retrieval.get("result"):
        result = retrieval["result"]
        if isinstance(result, dict):
            if result.get("text"):
                snippets.append(str(result["text"]))
            elif result.get("answer"):
                snippets.append(str(result["answer"]))
        elif isinstance(result, str):
            snippets.append(result)

    if retrieval.get("results") and isinstance(retrieval["results"], list):
        for item in retrieval["results"]:
            if isinstance(item, dict):
                text = item.get("text") or item.get("answer") or item.get("content")
                if text:
                    snippets.append(str(text))
            elif isinstance(item, str):
                snippets.append(item)

    if retrieval.get("retrieval") and isinstance(retrieval["retrieval"], dict):
        nested = retrieval["retrieval"]
        if nested.get("answer"):
            snippets.append(str(nested["answer"]))
        if nested.get("content"):
            snippets.append(str(nested["content"]))

    retrieved_nodes = retrieval.get("retrieved_nodes")
    if isinstance(retrieved_nodes, list):
        for node in retrieved_nodes:
            if not isinstance(node, dict):
                continue
            relevant_contents = node.get("relevant_contents")
            if not isinstance(relevant_contents, list):
                continue
            for group in relevant_contents:
                items = group if isinstance(group, list) else [group]
                for item in items:
                    if isinstance(item, dict) and item.get("relevant_content"):
                        snippets.append(str(item["relevant_content"]))
                    elif isinstance(item, str):
                        snippets.append(item)

    return [snippet for snippet in snippets if snippet][:max_snippets]
