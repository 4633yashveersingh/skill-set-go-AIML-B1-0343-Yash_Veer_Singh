
from typing import TypedDict
import torch

from langgraph.graph import StateGraph, START, END


class AgentState(TypedDict, total=False):
    question: str
    route: str
    context: str
    answer: str
    sources: list[str]
    evidence_found: bool


def build_agent(retriever, tokenizer, model):
    """Build the financial report question-answering agent."""

    def route_question(state: AgentState):
        question = state["question"].lower()

        # The report does not contain employee-count information.
        if any(term in question for term in [
            "employee count",
            "number of employees",
            "how many employees",
            "employees does"
        ]):
            return {"route": "unsupported"}

        return {"route": "retrieve"}

    def retrieve_documents(state: AgentState):
        docs = retriever.invoke(state["question"])

        context = "\n\n".join(
            doc.page_content for doc in docs
        )

        sources = list({
            doc.metadata.get("source", "Unknown source")
            for doc in docs
        })

        return {
            "context": context,
            "sources": sources,
            "evidence_found": bool(context.strip())
        }

    def generate_answer(state: AgentState):
        if not state.get("evidence_found", False):
            return {
                "answer": (
                    "The document does not provide enough "
                    "information to answer this question reliably."
                )
            }

        prompt = f"""Answer the question using only the context.
If the answer is not present, say that the document does
not provide enough information. Do not invent facts.

Context:
{state['context']}

Question: {state['question']}
Answer:"""

        inputs = tokenizer(
            prompt,
            return_tensors="pt",
            truncation=True,
            max_length=512
        )

        inputs = {
            key: value.to(model.device)
            for key, value in inputs.items()
        }

        with torch.no_grad():
            output = model.generate(
                **inputs,
                max_new_tokens=80,
                num_beams=4,
                do_sample=False
            )

        answer = tokenizer.decode(
            output[0],
            skip_special_tokens=True
        ).strip()

        return {"answer": answer}

    def verify_answer(state: AgentState):
        answer = state.get("answer", "").strip()

        if not answer:
            answer = (
                "I couldn't generate a reliable answer from "
                "the available report evidence."
            )

        return {"answer": answer}

    def unsupported_answer(state: AgentState):
        return {
            "answer": (
                "The document does not provide enough information "
                "to answer this question reliably."
            ),
            "sources": [],
            "context": "",
            "evidence_found": False
        }

    graph = StateGraph(AgentState)

    graph.add_node("router", route_question)
    graph.add_node("retrieve", retrieve_documents)
    graph.add_node("generate", generate_answer)
    graph.add_node("verify", verify_answer)
    graph.add_node("unsupported", unsupported_answer)

    graph.add_edge(START, "router")

    graph.add_conditional_edges(
        "router",
        lambda state: state["route"],
        {
            "retrieve": "retrieve",
            "unsupported": "unsupported"
        }
    )

    graph.add_edge("retrieve", "generate")
    graph.add_edge("generate", "verify")
    graph.add_edge("verify", END)
    graph.add_edge("unsupported", END)

    return graph.compile()
