from openai import OpenAI
import json

client = OpenAI()

def generate_testcase(schema, seed, mutation_rules):
    prompt = f"""
You are a SOME/IP fuzzing test generator.

Schema:
{json.dumps(schema, indent=2)}

Seed:
{json.dumps(seed, indent=2)}

Mutation rules:
{json.dumps(mutation_rules, indent=2)}

Generate ONE mutated test case.
Return JSON only.
"""

    resp = client.responses.create(
        model="gpt-4.1-mini",
        input=prompt
    )

    return resp.output_text
