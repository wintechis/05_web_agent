from smolagents import PromptTemplates, FinalAnswerPromptTemplate
from smolagents.agents import PlanningPromptTemplate, ManagedAgentPromptTemplate


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

