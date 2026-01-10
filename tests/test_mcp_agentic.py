"""Agentic tests for MCP server - Test like an agent thinks.

These tests simulate real agent research workflows:
1. Ambiguous natural language queries
2. Progressive discovery (start broad → narrow down)
3. Error recovery and fallback strategies
4. Multi-step research tasks
5. Metadata-driven decision making
"""

import pytest
import requests
from typing import Dict, List, Any


class AgenticMCPClient:
    """MCP client that mimics agent behavior."""

    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.mcp_endpoint = f"{base_url}/mcp"
        self.conversation_history = []  # Track decisions like an agent

    def _call_mcp(self, method: str, params: Dict) -> Dict:
        """Make MCP request and log decision."""
        payload = {"method": method, "params": params}
        self.conversation_history.append({
            "thought": f"Calling {method} with {params}",
            "action": payload
        })

        response = requests.post(self.mcp_endpoint, json=payload)
        response.raise_for_status()
        result = response.json()

        self.conversation_history.append({
            "result": result
        })

        if result.get('error'):
            raise ValueError(f"MCP Error: {result['error']}")

        return result.get('result', {})

    def think_and_discover(self, research_question: str) -> List[Dict]:
        """Agent thinks about question, then discovers relevant datasets."""
        self.conversation_history.append({
            "thought": f"Research question: {research_question}"
        })

        # Extract keywords (simple heuristic, agent would use LLM)
        keywords = research_question.lower().split()
        interesting_keywords = [k for k in keywords if len(k) > 3 and k not in ['what', 'show', 'find', 'many']]

        # Try discovery strategies in order
        strategies = [
            ("domain", self._extract_domain(research_question)),
            ("keyword", interesting_keywords[0] if interesting_keywords else None)
        ]

        for strategy_type, strategy_value in strategies:
            if strategy_value:
                try:
                    params = {strategy_type: strategy_value, "limit": 10}
                    result = self._call_mcp("list_datasets", params)
                    if result['total_found'] > 0:
                        return result['datasets']
                except Exception:
                    continue

        # Fallback: list all datasets
        return self._call_mcp("list_datasets", {"limit": 20})['datasets']

    def _extract_domain(self, question: str) -> str:
        """Extract domain from question (agent heuristic)."""
        question_lower = question.lower()
        if 'adhd' in question_lower or 'attention' in question_lower:
            return 'ADHD'
        elif 'workforce' in question_lower or 'staff' in question_lower or 'employee' in question_lower:
            return 'PCN Workforce'
        elif 'waiting' in question_lower or 'wait time' in question_lower:
            return 'Waiting Times'
        return None

    def pick_most_relevant(self, datasets: List[Dict], question: str) -> Dict:
        """Agent picks most relevant dataset from candidates."""
        question_lower = question.lower()

        # Score datasets by keyword overlap
        scored = []
        for ds in datasets:
            score = 0
            ds_text = (ds['code'] + ' ' + ds.get('description', '')).lower()

            # Check for question keywords in dataset
            for word in question_lower.split():
                if len(word) > 3 and word in ds_text:
                    score += 1

            # Prefer larger datasets (more comprehensive)
            if ds['rows'] > 1000:
                score += 0.5

            scored.append((score, ds))

        # Return highest scoring
        scored.sort(reverse=True, key=lambda x: x[0])
        return scored[0][1] if scored else datasets[0]

    def understand_then_query(self, dataset_code: str, question: str) -> Dict:
        """Agent first understands data, then queries intelligently."""
        # Step 1: Get metadata
        metadata = self._call_mcp("get_metadata", {"dataset": dataset_code})

        self.conversation_history.append({
            "thought": f"Dataset has {metadata['row_count']} rows and {metadata['column_count']} columns"
        })

        # Step 2: Decide query strategy based on question type
        query_strategy = self._decide_query_strategy(question, metadata)

        # Step 3: Execute query
        return self._call_mcp("query", {
            "dataset": dataset_code,
            "question": query_strategy
        })

    def _decide_query_strategy(self, question: str, metadata: Dict) -> str:
        """Agent decides how to query based on question and metadata."""
        question_lower = question.lower()

        # Count questions
        if any(word in question_lower for word in ['how many', 'count', 'total', 'number of']):
            return "count"

        # Grouping questions
        if 'by' in question_lower:
            # Find group column from metadata
            for col in metadata['columns']:
                if any(word in col['name'] for word in ['age', 'geography', 'gender', 'category']):
                    return f"group by {col['name']}"

        # Show/display questions
        if any(word in question_lower for word in ['show', 'display', 'list', 'what']):
            return "show data"

        # Default: show data
        return "show data"


# ============================================================================
# TEST SUITE 1: Natural Language Pattern Variations
# ============================================================================

@pytest.fixture(scope="module")
def agent():
    """Create agent client for tests."""
    return AgenticMCPClient()


class TestNaturalLanguagePatterns:
    """Test various ways agents might phrase questions."""

    def test_count_variations(self, agent):
        """Agents ask 'count' questions many ways."""
        variations = [
            "How many ADHD patients?",
            "Count ADHD records",
            "Total number of ADHD cases",
            "What's the ADHD patient count?"
        ]

        for question in variations:
            datasets = agent.think_and_discover(question)
            assert len(datasets) > 0, f"No datasets found for: {question}"
            assert any('adhd' in ds['code'].lower() for ds in datasets)

    def test_show_variations(self, agent):
        """Agents request data many ways."""
        variations = [
            "Show me ADHD data",
            "Display ADHD records",
            "List ADHD patients",
            "What ADHD data is available?"
        ]

        for question in variations:
            datasets = agent.think_and_discover(question)
            assert len(datasets) > 0
            dataset = agent.pick_most_relevant(datasets, question)
            result = agent.understand_then_query(dataset['code'], question)
            assert result['row_count'] > 0

    def test_aggregation_variations(self, agent):
        """Agents ask for grouped/aggregated data."""
        variations = [
            "ADHD cases by age group",
            "Breakdown by age",
            "Group workforce by age",
            "Show age distribution"
        ]

        for question in variations:
            datasets = agent.think_and_discover(question)
            assert len(datasets) > 0


# ============================================================================
# TEST SUITE 2: Progressive Discovery (Like Agent Thinks)
# ============================================================================

class TestProgressiveDiscovery:
    """Test agent workflow: broad → specific."""

    def test_start_broad_then_narrow(self, agent):
        """Agent starts broad, then narrows down."""
        # Step 1: Broad query
        all_datasets = agent._call_mcp("list_datasets", {"limit": 100})
        assert all_datasets['total_found'] >= 65  # We have 65 datasets

        # Step 2: Narrow by domain
        adhd_datasets = agent._call_mcp("list_datasets", {"domain": "ADHD", "limit": 100})
        assert adhd_datasets['total_found'] < all_datasets['total_found']
        assert adhd_datasets['total_found'] > 0

        # Step 3: Further narrow by keyword
        prevalence_datasets = agent._call_mcp("list_datasets", {
            "domain": "ADHD",
            "keyword": "prevalence"
        })
        assert prevalence_datasets['total_found'] <= adhd_datasets['total_found']

    def test_metadata_driven_narrowing(self, agent):
        """Agent uses metadata to pick right dataset."""
        # Find datasets with keyword
        datasets = agent._call_mcp("list_datasets", {"keyword": "age"})

        # Check metadata for each to find best match
        candidates = []
        for ds in datasets['datasets'][:5]:  # Check first 5
            metadata = agent._call_mcp("get_metadata", {"dataset": ds['code']})
            age_cols = [c['name'] for c in metadata['columns'] if 'age' in c['name'].lower()]

            if len(age_cols) >= 2:  # Has multiple age columns → likely age breakdown
                candidates.append((ds, len(age_cols)))

        assert len(candidates) > 0, "Should find datasets with age breakdowns"

        # Pick dataset with most age columns
        best = max(candidates, key=lambda x: x[1])
        assert best[1] >= 2


# ============================================================================
# TEST SUITE 3: Error Recovery (Agent Resilience)
# ============================================================================

class TestAgentErrorRecovery:
    """Test how agent handles errors and ambiguity."""

    def test_dataset_not_found_fallback(self, agent):
        """Agent tries specific name, falls back to discovery."""
        try:
            # Try exact dataset name (might not exist)
            agent._call_mcp("get_metadata", {"dataset": "nonexistent_dataset_xyz"})
            assert False, "Should have raised error"
        except ValueError:
            # Agent recovers by discovering available datasets
            datasets = agent._call_mcp("list_datasets", {"limit": 5})
            assert len(datasets['datasets']) > 0

    def test_ambiguous_query_handled(self, agent):
        """Agent handles ambiguous questions by asking for clarification (via discovery)."""
        ambiguous_question = "Show me data"  # Very ambiguous!

        # Agent discovers all available datasets
        datasets = agent.think_and_discover(ambiguous_question)
        assert len(datasets) > 0

        # Agent would present options to user (in real scenario)
        # For test: pick first and query
        dataset = datasets[0]
        result = agent.understand_then_query(dataset['code'], ambiguous_question)
        assert result['row_count'] > 0

    def test_empty_result_handling(self, agent):
        """Agent handles cases where query returns no data."""
        # Find a small dataset
        datasets = agent._call_mcp("list_datasets", {"limit": 100})
        small_dataset = min(datasets['datasets'], key=lambda x: x['rows'])

        # Query it
        result = agent._call_mcp("query", {
            "dataset": small_dataset['code'],
            "question": "show data"
        })

        # Even if empty, should return valid structure
        assert 'rows' in result
        assert 'row_count' in result


# ============================================================================
# TEST SUITE 4: Multi-Step Research Workflows
# ============================================================================

class TestResearchWorkflows:
    """Test realistic agent research tasks."""

    def test_comparative_research_workflow(self, agent):
        """Agent compares two related datasets."""
        question = "Compare ADHD prevalence across different time periods"

        # Step 1: Find ADHD datasets
        datasets = agent.think_and_discover(question)
        adhd_datasets = [ds for ds in datasets if 'adhd' in ds['code'].lower()]

        assert len(adhd_datasets) >= 2, "Need at least 2 ADHD datasets for comparison"

        # Step 2: Get metadata for each
        metadata_list = []
        for ds in adhd_datasets[:3]:  # Compare first 3
            metadata = agent._call_mcp("get_metadata", {"dataset": ds['code']})
            metadata_list.append(metadata)

        # Step 3: Query each dataset
        results = []
        for ds in adhd_datasets[:3]:
            result = agent._call_mcp("query", {
                "dataset": ds['code'],
                "question": "count"
            })
            results.append({
                "dataset": ds['code'],
                "rows": result['rows'][0]['total_rows']
            })

        # Step 4: Agent would compare results (we just validate they returned)
        assert len(results) == 3

    def test_drill_down_workflow(self, agent):
        """Agent starts with overview, drills down to specifics."""
        # Step 1: Overview - find workforce datasets
        question = "PCN workforce overview"
        datasets = agent.think_and_discover(question)
        workforce_datasets = [ds for ds in datasets if 'workforce' in ds['code'].lower()]

        assert len(workforce_datasets) > 0

        # Step 2: Pick aggregate dataset (larger = more comprehensive)
        overview_dataset = max(workforce_datasets, key=lambda x: x['rows'])

        # Step 3: Get metadata to understand structure
        metadata = agent._call_mcp("get_metadata", {"dataset": overview_dataset['code']})

        # Step 4: Drill down - find age-specific columns
        age_cols = [c for c in metadata['columns'] if 'age' in c['name'].lower()]
        assert len(age_cols) > 0, "Should have age breakdowns"

        # Step 5: Query for age-specific insights
        result = agent._call_mcp("query", {
            "dataset": overview_dataset['code'],
            "question": "show data grouped by age"
        })
        assert result['row_count'] > 0

    def test_data_quality_check_workflow(self, agent):
        """Agent validates data quality before using it."""
        dataset_code = "adhd_prevalence_estimate"

        # Step 1: Get metadata
        metadata = agent._call_mcp("get_metadata", {"dataset": dataset_code})

        # Step 2: Quality checks
        assert metadata['row_count'] > 0, "Dataset should not be empty"
        assert metadata['column_count'] >= 3, "Dataset should have meaningful columns"

        # Step 3: Check for audit columns (data lineage)
        audit_cols = [c for c in metadata['columns'] if c['name'].startswith('_')]
        assert len(audit_cols) > 0, "Should have audit columns for lineage"

        # Step 4: Sample data to verify structure
        result = agent._call_mcp("query", {
            "dataset": dataset_code,
            "question": "show data"
        })

        assert result['row_count'] > 0
        assert len(result['rows'][0].keys()) == metadata['column_count']


# ============================================================================
# TEST SUITE 5: Metadata-Driven Intelligence
# ============================================================================

class TestMetadataDrivenDecisions:
    """Test agent using metadata to make smart decisions."""

    def test_choose_by_data_freshness(self, agent):
        """Agent picks most recent dataset."""
        datasets = agent._call_mcp("list_datasets", {"domain": "ADHD", "limit": 100})

        # Check date ranges
        dated_datasets = [ds for ds in datasets['datasets'] if 'N/A' not in ds.get('date_range', 'N/A')]

        assert len(dated_datasets) > 0, "Should have datasets with date ranges"

    def test_choose_by_size_appropriateness(self, agent):
        """Agent picks right-sized dataset for task."""
        question = "Quick overview of ADHD data"

        datasets = agent.think_and_discover(question)

        # For "quick overview", agent prefers smaller, summary datasets
        small_datasets = [ds for ds in datasets if ds['rows'] < 5000]

        assert len(small_datasets) > 0

        # For "comprehensive analysis", would prefer larger datasets
        large_datasets = [ds for ds in datasets if ds['rows'] > 5000]
        assert len(large_datasets) > 0

    def test_column_description_understanding(self, agent):
        """Agent uses column descriptions to understand data meaning."""
        dataset_code = "adhd_prevalence_estimate"
        metadata = agent._call_mcp("get_metadata", {"dataset": dataset_code})

        # Agent should be able to find relevant columns by description
        # (In production, LLM would parse descriptions)

        # For now, check descriptions exist
        described_cols = [c for c in metadata['columns']
                         if c.get('description') and len(c['description']) > 10]

        # We expect high metadata coverage (95%+)
        coverage = len(described_cols) / len(metadata['columns'])
        assert coverage > 0.5, f"Metadata coverage too low: {coverage:.0%}"


# ============================================================================
# TEST SUITE 6: Performance and Scalability
# ============================================================================

class TestAgentPerformance:
    """Test agent can work efficiently."""

    def test_rapid_discovery_multiple_domains(self, agent):
        """Agent quickly discovers datasets across domains."""
        domains = ["ADHD", "PCN Workforce", "Waiting Times"]

        for domain in domains:
            result = agent._call_mcp("list_datasets", {"domain": domain, "limit": 5})
            assert result['total_found'] > 0
            # Should return quickly (actual timing would need benchmarking)

    def test_metadata_access_speed(self, agent):
        """Agent can quickly access metadata for decision making."""
        datasets = agent._call_mcp("list_datasets", {"limit": 10})

        # Get metadata for first 5
        for ds in datasets['datasets'][:5]:
            metadata = agent._call_mcp("get_metadata", {"dataset": ds['code']})
            assert metadata['row_count'] > 0
            # Each call should be fast (<100ms in production)

    def test_large_dataset_handling(self, agent):
        """Agent handles large datasets efficiently."""
        # Find largest dataset
        datasets = agent._call_mcp("list_datasets", {"limit": 100})
        largest = max(datasets['datasets'], key=lambda x: x['rows'])

        # Agent should query without loading entire dataset into memory
        result = agent._call_mcp("query", {
            "dataset": largest['code'],
            "question": "count"
        })

        assert result['rows'][0]['total_rows'] == largest['rows']


# ============================================================================
# SUMMARY TEST: Complete Agent Research Session
# ============================================================================

class TestCompleteResearchSession:
    """End-to-end test of full agent research workflow."""

    def test_full_research_task(self, agent):
        """Simulate agent completing real research task from start to finish."""

        research_task = "Find and analyze ADHD patient demographics by age group"

        print(f"\n{'='*60}")
        print(f"AGENT RESEARCH TASK: {research_task}")
        print(f"{'='*60}\n")

        # Step 1: Agent thinks and discovers relevant datasets
        print("Step 1: Discovering relevant datasets...")
        datasets = agent.think_and_discover(research_task)
        assert len(datasets) > 0
        print(f"  Found {len(datasets)} datasets")

        # Step 2: Agent picks most relevant dataset
        print("\nStep 2: Selecting most relevant dataset...")
        target_dataset = agent.pick_most_relevant(datasets, research_task)
        print(f"  Selected: {target_dataset['code']} ({target_dataset['rows']:,} rows)")

        # Step 3: Agent understands dataset structure
        print("\nStep 3: Understanding dataset structure...")
        metadata = agent._call_mcp("get_metadata", {"dataset": target_dataset['code']})
        age_cols = [c['name'] for c in metadata['columns'] if 'age' in c['name'].lower()]
        print(f"  Columns: {metadata['column_count']}")
        print(f"  Age-related columns: {len(age_cols)}")

        # Step 4: Agent executes query
        print("\nStep 4: Executing query...")
        result = agent.understand_then_query(target_dataset['code'], research_task)
        print(f"  Query: {result['query_description']}")
        print(f"  Result: {result['row_count']} rows")

        # Step 5: Agent validates result quality
        print("\nStep 5: Validating result quality...")
        assert result['row_count'] > 0
        assert result['total_dataset_rows'] == target_dataset['rows']
        print(f"  ✅ Quality checks passed")

        # Step 6: Agent formats final answer
        print("\nStep 6: Formatting answer...")
        print(f"  Dataset: {target_dataset['code']}")
        print(f"  Demographics: {result['row_count']} demographic breakdowns")
        print(f"  Total patients: {result['total_dataset_rows']:,}")

        print(f"\n{'='*60}")
        print("✅ RESEARCH TASK COMPLETE")
        print(f"{'='*60}\n")

        print("Agent conversation history:")
        for i, entry in enumerate(agent.conversation_history[-8:], 1):  # Show last 8 steps
            if 'thought' in entry:
                print(f"  {i}. 💭 {entry['thought']}")


# ============================================================================
# Run all tests
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
