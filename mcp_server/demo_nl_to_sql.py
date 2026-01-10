"""Demonstrate how NL→SQL would work in production MCP.

This shows TWO approaches:
1. LLM generates pandas code (safer, sandboxed)
2. LLM generates SQL (more powerful, but needs validation)
"""

import os
import sys
from pathlib import Path

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))


def demo_approach_1_pandas_code():
    """Approach 1: LLM generates pandas code (what we recommend)."""
    print("=" * 70)
    print("  APPROACH 1: LLM Generates Pandas Code")
    print("=" * 70)
    print()

    # Simulated data
    import pandas as pd
    df = pd.DataFrame({
        'age': [25, 30, 35, 40, 45],
        'geography': ['London', 'North', 'London', 'South', 'North'],
        'diagnosis': ['ADHD', 'ADHD', 'Autism', 'ADHD', 'Autism']
    })

    print("📊 Sample Dataset:")
    print(df)
    print()

    # User questions
    questions = [
        "What's the average age?",
        "How many patients are from London?",
        "Group patients by geography and count them"
    ]

    for question in questions:
        print("-" * 70)
        print(f"❓ Question: {question}")
        print()

        # SIMULATE LLM CALL (in production, this calls Gemini/GPT/Claude)
        llm_response = simulate_llm_generate_pandas(question, df)

        print(f"🤖 LLM Generated Code:")
        print(f"   {llm_response}")
        print()

        # Execute the code
        try:
            result = eval(llm_response)
            print(f"✅ Result: {result}")
        except Exception as e:
            print(f"❌ Error: {e}")
        print()


def demo_approach_2_sql():
    """Approach 2: LLM generates SQL."""
    print("=" * 70)
    print("  APPROACH 2: LLM Generates SQL")
    print("=" * 70)
    print()

    # Simulated schema
    table_name = "staging.tbl_adhd_aug25"
    schema = {
        'age': 'INTEGER',
        'geography': 'VARCHAR',
        'diagnosis': 'VARCHAR'
    }

    print(f"📊 Table: {table_name}")
    print(f"   Schema: {schema}")
    print()

    # User questions
    questions = [
        "What's the average age?",
        "How many patients are from London?",
        "Group patients by geography and count them"
    ]

    for question in questions:
        print("-" * 70)
        print(f"❓ Question: {question}")
        print()

        # SIMULATE LLM CALL
        sql = simulate_llm_generate_sql(question, table_name, schema)

        print(f"🤖 LLM Generated SQL:")
        print(f"   {sql}")
        print()

        # In production, you'd execute this:
        # result = pd.read_sql(sql, connection)
        print("✅ Would execute against PostgreSQL")
        print()


def demo_approach_3_tool_use():
    """Approach 3: LLM chooses which tools to use (most flexible)."""
    print("=" * 70)
    print("  APPROACH 3: LLM Tool Use (Claude/GPT-4 Style)")
    print("=" * 70)
    print()

    print("🤖 Available Tools for LLM:")
    print("""
    1. list_datasets(limit, keyword, include_stats)
       - Returns catalog of available datasets

    2. get_metadata(dataset)
       - Returns schema, column types, sample data

    3. execute_sql(dataset, sql)
       - Runs SQL query against dataset

    4. execute_pandas(dataset, code)
       - Runs pandas code against dataset
    """)
    print()

    # Complex user question
    question = "Find all ADHD datasets loaded in the last 24 hours, then show me the average age for the largest one"

    print(f"❓ Complex Question: {question}")
    print()

    print("🤖 LLM Reasoning (with tool use):")
    print()

    # Step 1: LLM chooses list_datasets
    print("Step 1: LLM calls list_datasets(keyword='adhd', include_stats=True)")
    print("   Result: 5 ADHD datasets found")
    print()

    # Step 2: LLM filters by freshness
    print("Step 2: LLM filters datasets loaded in last 24h")
    print("   Result: 3 datasets match")
    print()

    # Step 3: LLM identifies largest
    print("Step 3: LLM sorts by db_stats.size_mb, picks largest")
    print("   Result: adhd_aug25_indicator_values (1318 rows, 0.25 MB)")
    print()

    # Step 4: LLM generates SQL for average
    print("Step 4: LLM calls execute_sql('adhd_aug25_indicator_values', \"SELECT AVG(age) FROM ...\")")
    print("   Result: Average age = 32.5")
    print()

    print("✅ Final Answer: 32.5")
    print()
    print("🔑 Key: LLM CHAINS multiple tool calls to answer complex questions")


# ============================================================================
# SIMULATED LLM FUNCTIONS (In production, these call real LLMs)
# ============================================================================

def simulate_llm_generate_pandas(question: str, df) -> str:
    """Simulate LLM generating pandas code."""
    # In production: call Gemini/GPT/Claude with prompt
    # For demo: hardcoded responses

    if 'average age' in question.lower():
        return "df['age'].mean()"
    elif 'how many' in question.lower() and 'london' in question.lower():
        return "len(df[df['geography'] == 'London'])"
    elif 'group' in question.lower() and 'geography' in question.lower():
        return "df.groupby('geography').size()"
    else:
        return "df.head()"


def simulate_llm_generate_sql(question: str, table: str, schema: dict) -> str:
    """Simulate LLM generating SQL."""
    # In production: call LLM with schema context
    # For demo: hardcoded responses

    if 'average age' in question.lower():
        return f"SELECT AVG(age) FROM {table}"
    elif 'how many' in question.lower() and 'london' in question.lower():
        return f"SELECT COUNT(*) FROM {table} WHERE geography = 'London'"
    elif 'group' in question.lower() and 'geography' in question.lower():
        return f"SELECT geography, COUNT(*) FROM {table} GROUP BY geography"
    else:
        return f"SELECT * FROM {table} LIMIT 10"


# ============================================================================
# REAL IMPLEMENTATION EXAMPLE (Commented - for reference)
# ============================================================================

def production_query_handler_example():
    """This is what the REAL implementation would look like."""
    print("=" * 70)
    print("  PRODUCTION IMPLEMENTATION (Pseudocode)")
    print("=" * 70)
    print()

    code = '''
def handle_query(question: str, dataset: str) -> dict:
    """Production query handler using real LLM."""

    # 1. Load dataset and schema
    df = load_dataset(dataset)
    schema = get_schema(df)

    # 2. Build LLM prompt
    prompt = f"""
    You are a data analyst. Generate pandas code to answer this question.

    Dataset: {dataset}
    Columns: {schema['columns']}
    Types: {schema['types']}
    Sample data: {df.head(3).to_dict()}

    Question: {question}

    Rules:
    - Generate ONLY pandas code, no explanations
    - Use variable name 'df' for the dataframe
    - Return a value that can be JSON serialized
    - Do NOT use dangerous functions (eval, exec, import, etc.)

    Example: df['age'].mean()
    """

    # 3. Call LLM (Gemini in your case)
    import google.generativeai as genai
    genai.configure(api_key=os.getenv('GEMINI_API_KEY'))
    model = genai.GenerativeModel('gemini-2.0-flash-exp')
    response = model.generate_content(prompt)
    code = response.text.strip()

    # 4. Validate code (security check)
    if any(dangerous in code for dangerous in ['import', 'exec', 'eval', '__']):
        raise SecurityError("Generated code contains dangerous operations")

    # 5. Execute in restricted namespace
    namespace = {'df': df, 'pd': pd}
    result = eval(code, {"__builtins__": {}}, namespace)

    # 6. Return result
    return {
        "answer": result,
        "code_used": code,
        "dataset": dataset
    }
    '''

    print(code)
    print()
    print("🔑 Key Points:")
    print("   1. One function handles ALL query types (no fixed endpoints)")
    print("   2. LLM generates code dynamically based on question")
    print("   3. Code is validated for security before execution")
    print("   4. Result is returned as JSON")


if __name__ == "__main__":
    print()
    print("🧪 DEMONSTRATION: How NL→SQL/Code Works in Production MCP")
    print()

    demo_approach_1_pandas_code()
    print("\n" * 2)

    demo_approach_2_sql()
    print("\n" * 2)

    demo_approach_3_tool_use()
    print("\n" * 2)

    production_query_handler_example()

    print()
    print("=" * 70)
    print("  SUMMARY")
    print("=" * 70)
    print("""
✅ You DO NOT need an interface for every query type

✅ One endpoint handles infinite queries via LLM

✅ Three approaches:
   1. LLM → Pandas code (safest, sandboxed)
   2. LLM → SQL (powerful, needs validation)
   3. LLM → Tool chains (most flexible, like Claude)

✅ Current MCP prototype uses hardcoded patterns (temporary)

✅ Production MCP would use Approach 1 or 3 (LLM-powered)

🔑 The MCP we built (list_datasets with include_stats) enables
   Approach 3 - agents chain tool calls to answer complex questions
""")
