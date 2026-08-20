"""
RAGAS evaluation for interview-generated report sections.

Each interview produces one "answer" (the written section) grounded in
"contexts" (the Tavily search results retrieved during that interview) in
response to a "question" (the analyst's opening question / topic framing).
That triple is exactly the shape RAGAS expects, so evaluation runs per
section rather than on the merged final report.

Metrics used:
  - faithfulness        — is the section actually supported by its retrieved context?
  - answer_relevancy     — does the section address the analyst's question?
  - context_precision    — how much of the retrieved context was actually useful?

This is intentionally decoupled from the LangGraph workflow itself (it's not
a graph node) — it runs as a post-hoc scoring pass over the sections a report
produced, since RAGAS evaluation calls its own LLM judge and would otherwise
add latency/cost to every report generation. Call `evaluate_sections()`
explicitly (e.g. in a nightly eval job or before shipping a prompt change).
"""

import logging
from typing import Optional

log = logging.getLogger(__name__)


def evaluate_sections(section_records: list, llm=None, embeddings=None) -> Optional[dict]:
    """
    Score a batch of interview sections with RAGAS.

    Args:
        section_records: list of dicts, each with:
            {
                "question": str,   # the analyst's opening question / topic
                "answer": str,     # the generated section text
                "contexts": list[str],  # the retrieved Tavily context strings
            }
        llm: optional LangChain chat model to use as the RAGAS judge
             (defaults to RAGAS's own default if not provided).
        embeddings: optional embeddings model for context_precision.

    Returns:
        dict of metric_name -> average score across the batch, or None if
        RAGAS isn't installed or the input is empty.
    """
    if not section_records:
        log.info("No section records supplied to evaluate_sections — skipping")
        return None

    try:
        from datasets import Dataset
        from ragas import evaluate
        from ragas.metrics import faithfulness, answer_relevancy, context_precision
    except ImportError:
        log.warning(
            "ragas / datasets not installed — run `pip install ragas datasets` to enable evaluation"
        )
        return None

    try:
        dataset = Dataset.from_list([
            {
                "question": rec["question"],
                "answer": rec["answer"],
                "contexts": rec["contexts"] if rec["contexts"] else ["[No context]"],
            }
            for rec in section_records
        ])

        kwargs = {}
        if llm is not None:
            kwargs["llm"] = llm
        if embeddings is not None:
            kwargs["embeddings"] = embeddings

        log.info("Running RAGAS evaluation | sections=%s", len(section_records))
        result = evaluate(
            dataset,
            metrics=[faithfulness, answer_relevancy, context_precision],
            **kwargs,
        )
        scores = {k: float(v) for k, v in result.items()}
        log.info("RAGAS evaluation complete | scores=%s", scores)
        return scores

    except Exception as e:
        log.error("RAGAS evaluation failed | error=%s", str(e), exc_info=True)
        return None


class SectionEvalCollector:
    """
    Small helper the interview workflow can use to accumulate
    (question, answer, contexts) triples as interviews complete, so the
    caller has a ready-made `section_records` list to pass to
    `evaluate_sections()` once a report finishes.
    """

    def __init__(self):
        self._records: list = []

    def add(self, question: str, answer: str, contexts: list):
        self._records.append({
            "question": question,
            "answer": answer,
            "contexts": contexts,
        })

    @property
    def records(self) -> list:
        return list(self._records)

    def clear(self):
        self._records.clear()
