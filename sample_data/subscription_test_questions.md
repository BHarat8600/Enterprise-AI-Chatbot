# Subscription Analysis Test Questions

## Direct SQL Tool

1. Show me the Subscription_Analysis database schema columns.
2. Which subscription plans have the highest active contract value?
3. Show societies with expired or upcoming renewals in the next 30 days.
4. Which payments failed or are still pending?
5. Show complaint tickets that breached SLA.
6. Summarize societies by city, state, and total flats.

## PDF Tool

1. Summarize this PDF: `output/pdf/subscription_analysis_demo.pdf`.
2. What SLA policy does the demo PDF describe?
3. What payment risk signals are described in the PDF?

## Document Tool

1. Search this markdown file for renewal risk: `sample_data/subscription_analysis_knowledge.md`.
2. Summarize the business definitions from the knowledge document.

## RAG Tool

1. Retrieve the subscription renewal risk definition from the knowledge base.
2. What is payment leakage according to the indexed documents?
3. How should SLA breach be calculated?

## Multi-Tool Questions

1. Summarize the demo PDF and compare it with active subscription value from SQL.
2. Retrieve the SLA breach definition from RAG, then show breached complaint tickets from SQL.
3. Use the knowledge base to explain renewal risk, then list societies with expired or near-expiring subscriptions from SQL.
4. Compare payment leakage guidance from RAG with failed payment rows from SQL.

