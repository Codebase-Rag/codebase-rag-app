agent_instruction = """
{question}
Please:
Use your code retrieval and graph querying tools to understand the codebase structure,
Read relevant source files to identify optimization opportunities,
Reference established patterns and best practices,
Propose specific, actionable optimizations with file references,
IMPORTANT: Do not make any changes yet - just propose them and wait for approval,
After approval, use your file editing tools to implement the changes,

Start by analyzing the codebase structure and identifying the main areas that could benefit from optimization.
Remember: Propose changes first, wait for my approval, then implement.
"""