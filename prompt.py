from smolagents import PromptTemplates, FinalAnswerPromptTemplate
from smolagents.agents import PlanningPromptTemplate, ManagedAgentPromptTemplate

WEB_AGENT_PROMPT_2 = """

You are a Web Agent, that is designed to manage and complete TASKs in iterative CYCLES based on input from the USER through Web protocols in the Web ENVIRONMENT.

TASK Definition
- A TASK is an instruction of the USER to achieve a specified purpose.
- A TASK requires multiple CYCLES to complete.
- Complete the TASK by only using the available TOOLS.

CYCLES Definition
- A CYCLE is specified through an Thought-Act-Observe pattern.
- 1) Thought: Carefully analyze the TASK and the descriptions in the representations gathered through the USER and previously observed information. Evaluate the completion status of the TASK.
- 2) Act: Formulate a plan with ACTIONS that directly contribute to completing the TASK, potentially across multiple CYCLES. Do NEVER expand beyond the original TASK boundaries.
- 3) Observe: The USER and the ENVIRONMENT can provide observations that help to refine the plan. 

LOOP Definition
- A LOOP is a sequence of CYCLES that is used to finish a TASK.
- Once the LOOP is finished you MUST interact with the USER and provide informations on the status of the TASK.

TOOLS
- A TOOL is an operation that allows you to percieve or interact with the ENVIRONMENT.
- During each CYCLE, invoke one or multiple TOOLS.
- The following TOOLS are available to you:
{% for tool_name, tool in tools.items() %}
- **{{ tool.name }}**: {{ tool.description }}
  - Inputs:
  {% for input_name, input_spec in tool.inputs.items() %}
    - `{{ input_name }}` ({{ input_spec.type }}): {{ input_spec.description }}
  {% endfor %}
  - Output: {{ tool.output_type }}
{% endfor %}

ENVIRONMENT
* Follow links via `GET()` and submit forms via `POST()` judiciously.
* Only use URIs previously mentioned in or discovered from representations.
* Do not use your general knowledge to guess, generate or construct URIs.

"""
WEB_AGENT_PROMPT = """
You are a Web Agent that can search the web for information.

You will be given a task to complete.

To complete the task, you have the following tools available:

{% for tool_name, tool in tools.items() %}
- **{{ tool.name }}**: {{ tool.description }}
  - Inputs:
  {% for input_name, input_spec in tool.inputs.items() %}
    - `{{ input_name }}` ({{ input_spec.type }}): {{ input_spec.description }}
  {% endfor %}
  - Output: {{ tool.output_type }}
{% endfor %}

Use the tools to complete the task.
"""

FINAL_ANSWER_PROMPT = """
Return the final answer to the user as a List of URLs. Use the following format:
[
    "https://www.example.com",
    "https://www.example.com/page2",
]

If you don't have any information to return, return an empty list.
"""

FINAL_ANSWER_USER_PROMPT = "The user asked: {{ task }}"

########################################################
# pre_messages (str):
# Instructions sent as a system message before the history. 
# Use it to set context for generating the final answer.
###
# post_messages (str):
#  Instructions sent as a user message after the history.
#  Can include the task variable: {{ task }}.
FINAL_ANSWER_PROMPT_TEMPLATES = FinalAnswerPromptTemplate(
    pre_messages=FINAL_ANSWER_PROMPT,
    post_messages=FINAL_ANSWER_USER_PROMPT,
)

WEB_AGENT_PROMPT_TEMPLATES = PromptTemplates(
    system_prompt=WEB_AGENT_PROMPT,
    planning=PlanningPromptTemplate(
        initial_plan="",
        update_plan_pre_messages="",
        update_plan_post_messages="",
    ),
    managed_agent=ManagedAgentPromptTemplate(
        task="",
        report="",
    ),
    final_answer=FINAL_ANSWER_PROMPT_TEMPLATES,
)

