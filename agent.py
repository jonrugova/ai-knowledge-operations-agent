import json
import os
import time

from openai import OpenAI

from approval_store import (
    APPROVALS_PATH,
    CANONICAL_RUSH_APPROVAL_TYPE,
    create_approval_request,
)
from delivery_tool import calculate_delivery_timeline
from observability import (
    persist_completed_trace,
    record_model_call,
    record_tool_call,
    start_trace,
)
from semantic_search import search_knowledge


SEARCH_COMPANY_KNOWLEDGE_TOOL = {
    "type": "function",
    "name": "search_company_knowledge",
    "description": (
        "Search the company knowledge base for policies, "
        "business facts, shipping, returns, duties, sizing, customizations, "
        "cancellations, and related company information."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "question": {
                "type": "string",
            }
        },
        "required": ["question"],
        "additionalProperties": False,
    },
    "strict": True,
}

CALCULATE_DELIVERY_TIMELINE_TOOL = {
    "type": "function",
    "name": "calculate_delivery_timeline",
    "description": (
        "Calculate estimated production-ready and DHL delivery dates from a "
        "specific order date."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "order_date": {
                "type": "string",
                "description": "Order date in YYYY-MM-DD format.",
            }
        },
        "required": ["order_date"],
        "additionalProperties": False,
    },
    "strict": True,
}

REQUEST_HUMAN_APPROVAL_TOOL = {
    "type": "function",
    "name": "request_human_approval",
    "description": (
        "Create a pending human approval request for an approximately "
        "two-week rush production request. This requests review but does not "
        "grant approval."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "reason": {
                "type": "string",
            },
            "user_request": {
                "type": "string",
            },
        },
        "required": ["reason", "user_request"],
        "additionalProperties": False,
    },
    "strict": True,
}

TOOLS = [
    SEARCH_COMPANY_KNOWLEDGE_TOOL,
    CALCULATE_DELIVERY_TIMELINE_TOOL,
    REQUEST_HUMAN_APPROVAL_TOOL,
]

INSTRUCTIONS = (
    "You are an internal company knowledge and operations assistant. The user "
    "is a company employee, not the customer. The employee may describe a "
    "customer's question, order, or request. Do not assume the employee is the "
    "customer. When appropriate, refer to \"the customer\", \"the order\", or "
    "\"the request\". If the employee explicitly asks for customer-facing "
    "reply wording, you may draft it using retrieved company knowledge. "
    "Otherwise, answer as an internal operational assistant. "
    "Use search_company_knowledge for company policy and fact "
    "questions, including shipping, production, returns, duties, sizing, "
    "customizations, cancellations, collections, and other company-specific "
    "information. Use calculate_delivery_timeline when the user asks for an "
    "estimated arrival based on a specific order date. Do not calculate "
    "delivery dates mentally when calculate_delivery_timeline can calculate "
    "them. Never present estimated delivery dates as guaranteed. Do not rely "
    "on your own memory for company-specific facts. "
    "If the user asks for an approximately two-week rush, do not confirm the "
    "rush. Use search_company_knowledge if policy knowledge is needed, then "
    "call request_human_approval exactly once to create a pending request. "
    "Clearly tell the user that human review or approval is required and that "
    "the rush is not approved yet, then stop. The agent itself cannot approve, "
    "reject, or directly execute the protected action. Protected actions resume "
    "only after an authorized human approval through the human workflow. Never "
    "claim that approval occurred or that the protected action executed before "
    "the human approval workflow reports execution. Pending or rejected "
    "approval must never be treated as approved. Approval status must come "
    "from the persisted approval record. "
    "If the tool results do not contain enough information, say exactly: "
    "\"I don't have enough information in the company knowledge base.\" "
    "For normal conversation that does not require company knowledge, respond "
    "without using the tool. Do not mention internal embeddings, vectors, "
    "PostgreSQL, retrieval systems, or tool implementation details to the user."
)


def search_company_knowledge(question: str, trace=None):
    # Python executes the actual tool; the model does not access PostgreSQL.
    matches = search_knowledge(question, top_k=3, trace=trace)
    return [
        {
            "section": match["section"],
            "content": match["content"],
            "similarity": match["similarity"],
        }
        for match in matches
    ]


def _usage_value(usage, name):
    if usage is None:
        return 0
    return getattr(usage, name, 0) or 0


def answer_question(question: str, requester_id: str | None = None):
    trace = start_trace(question)

    try:
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError(
                "OPENAI_API_KEY environment variable is not set."
            )

        client = OpenAI(api_key=api_key)
        input_items = [{"role": "user", "content": question}]
        tool_calls = []

        while True:
            # The model decides whether the company-knowledge tool is needed.
            model_call_start = time.perf_counter()
            try:
                response = client.responses.create(
                    model="gpt-5.6-luna",
                    instructions=INSTRUCTIONS,
                    input=input_items,
                    tools=TOOLS,
                    tool_choice="auto",
                    parallel_tool_calls=False,
                )
            except Exception:
                record_model_call(
                    trace,
                    (time.perf_counter() - model_call_start) * 1000,
                )
                raise
            else:
                usage = getattr(response, "usage", None)
                input_details = getattr(
                    usage,
                    "input_tokens_details",
                    None,
                )
                record_model_call(
                    trace,
                    (time.perf_counter() - model_call_start) * 1000,
                    input_tokens=_usage_value(usage, "input_tokens"),
                    cached_input_tokens=_usage_value(
                        input_details,
                        "cached_tokens",
                    ),
                    output_tokens=_usage_value(usage, "output_tokens"),
                    total_tokens=_usage_value(usage, "total_tokens"),
                )

            function_calls = [
                item
                for item in response.output
                if item.type == "function_call"
            ]
            if not function_calls:
                persist_completed_trace(trace, "success")
                return response.output_text, tool_calls

            input_items.extend(response.output)

            for function_call in function_calls:
                arguments = json.loads(function_call.arguments)
                tool_call_start = time.perf_counter()
                try:
                    if function_call.name == "search_company_knowledge":
                        results = search_company_knowledge(
                            arguments["question"],
                            trace=trace,
                        )
                        sections = [
                            result["section"] for result in results
                        ]
                    elif (
                        function_call.name
                        == "calculate_delivery_timeline"
                    ):
                        results = calculate_delivery_timeline(
                            arguments["order_date"]
                        )
                        sections = []
                    elif function_call.name == "request_human_approval":
                        # The agent requests approval but does not grant it.
                        if not isinstance(requester_id, str) or not requester_id.strip():
                            raise ValueError(
                                "A valid requester identity is required "
                                "to create an approval request."
                            )
                        results = create_approval_request(
                            approval_type=CANONICAL_RUSH_APPROVAL_TYPE,
                            reason=arguments["reason"],
                            user_request=arguments["user_request"],
                            requested_by=requester_id,
                        )
                        # Pending stops execution until a human decision.
                        sections = []
                    else:
                        raise ValueError(
                            f"Unknown tool: {function_call.name}"
                        )
                finally:
                    record_tool_call(
                        trace,
                        function_call.name,
                        (time.perf_counter() - tool_call_start) * 1000,
                    )

                tool_calls.append(
                    {
                        "name": function_call.name,
                        "arguments": arguments,
                        "sections": sections,
                        "output": results,
                    }
                )

                # Give the tool result back to the model.
                input_items.append(
                    {
                        "type": "function_call_output",
                        "call_id": function_call.call_id,
                        "output": json.dumps(results),
                    }
                )
    except Exception as error:
        persist_completed_trace(
            trace,
            "error",
            type(error).__name__,
        )
        raise


def main():
    questions = [
        "Can you rush my dress so I receive it in about two weeks?",
        "What is the normal production time?",
        "A customer plans to order on 2026-10-01. What estimated delivery "
        "window should I give them?",
    ]

    for question in questions:
        answer, tool_calls = answer_question(
            question,
            requester_id="employee",
        )

        print("USER QUESTION")
        print(question)
        print(
            f"TOOLS USED: "
            f"{', '.join(call['name'] for call in tool_calls) or 'NONE'}"
        )
        print("TOOL ARGUMENTS")
        if tool_calls:
            for tool_call in tool_calls:
                print(
                    json.dumps(
                        tool_call["arguments"],
                        ensure_ascii=False,
                    )
                )
        else:
            print("NONE")
        print("TOOL OUTPUT")
        if tool_calls:
            for tool_call in tool_calls:
                print(
                    json.dumps(
                        tool_call["output"],
                        ensure_ascii=False,
                    )
                )
        else:
            print("NONE")
        print("FINAL ANSWER")
        print(answer)
        print()

    print("CONTENTS OF data/approvals.json")
    print(APPROVALS_PATH.read_text(encoding="utf-8"), end="")


if __name__ == "__main__":
    main()