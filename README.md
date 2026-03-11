##Agentic AI Research Workflow System

LangGraph + FastAPI

A production-oriented Agentic AI system that orchestrates multi-step LLM workflows to generate structured research reports with controlled execution, web search integration, and cost-aware optimisation.

    Overview

This project implements a multi-agent research workflow using LangGraph to manage structured LLM execution across clearly defined stages:
Analyst persona generation
Structured interview simulation
LLM-driven search query generation
Tool-based web search integration (Tavily)
Expert response synthesis
Section writing and aggregation
Automated report compilation (DOCX & PDF)
The system focuses on deterministic workflow execution, modular design, and performance optimisation.

System Architecture
Agentic Workflow Orchestration (LangGraph)
Node-based execution graph
Controlled transitions between stages
Deterministic execution to avoid redundant LLM calls
Human-in-the-loop feedback integration

    Backend API Layer (FastAPI)

REST endpoints for workflow execution
Clear separation between:
Core AI logic
Production concerns (logging, configuration, exception handling)
Structured logging for observability

    Web Search Integration

Tavily search tool integration
LLM-driven structured query generation
Controlled context injection (top 3 search results)
In-memory caching to prevent redundant external API calls

    Token Usage & Cost Monitoring

The system tracks:
Prompt tokens
Completion tokens
Total tokens per workflow node

This enables:
Cost analysis
Token optimisation
Performance benchmarking

    Performance Optimisations

Reduced prompt size through controlled context injection
Limited external search results to minimise token usage
Implemented in-memory caching for repeated search queries
Structured execution flow to prevent unnecessary LLM re-execution

    Output Capabilities

Automated structured report generation
Section aggregation
Export formats:
DOCX
PDF
