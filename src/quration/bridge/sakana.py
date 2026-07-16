import time
from typing import List, Dict, Any
from quration.bridge.protocols import AgentProtocol, AgentResult, Tool

class SakanaScientistWrapper(AgentProtocol):
    """
    A wrapper/simulation of Sakana AI's 'The AI Scientist'.

    In a real implementation, this would import `sakana` and delegate calls.
    Here, we simulate the 'Idea Generation -> Code Execution' loop using Quration's tools.
    """
    name = "Sakana AI Scientist (Simulated)"

    def run(self, input_text: str, tools: List[Tool]) -> AgentResult:
        print(f"\n[Agent: {self.name}] Received Goal: {input_text}")

        # 1. Simulate "Idea Generation" phase
        print(f"[Agent: {self.name}] 🧠 Generating research plan...")
        time.sleep(1)
        plan = "Plan: Search for relevant GEO datasets, extract metadata, and summarize findings."
        print(f"[Agent: {self.name}] Plan created: {plan}")

        # 2. Simulate "Tool Selection" phase
        output_log = []
        found_datasets = []

        # Look for the search tool
        search_tool = next((t for t in tools if t.name == "search_geo_datasets"), None)

        if search_tool:
            print(f"[Agent: {self.name}] 🛠️  Selected tool: {search_tool.name}")

            # Simulate extracting keywords from input
            # For demo purposes, we'll assume the input *is* the query or close to it
            query = input_text.replace("search for", "").strip()

            print(f"[Agent: {self.name}] 🏃 Executing tool with query: '{query}'")
            results = search_tool.execute(query=query, limit=3)

            found_datasets = results
            output_log.append(f"Found {len(results)} datasets for query '{query}':")
            for d in results:
                output_log.append(f"- {d.get('id')}: {d.get('title')} ({d.get('organism')})")
        else:
            output_log.append("Error: Could not find search tool.")

        # 3. Simulate "Writeup" phase
        print(f"[Agent: {self.name}] 📝 Writing final report...")
        final_report = f"# Research Report: {input_text}\n\n"
        final_report += "## Methodology\nAutomated search of Gene Expression Omnibus.\n\n"
        final_report += "## Findings\n"
        final_report += "\n".join(output_log)

        return AgentResult(
            output=final_report,
            artifacts=[],
            cost=0.05, # Simulated cheap cost
            metadata={"model": "sakana-simulated-v1", "steps": 3}
        )
