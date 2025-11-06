"""CLI command for executing research queries.

Purpose:
    Provide command-line interface for executing research queries generated
    from preflight extraction, or running ad-hoc research searches across
    multiple databases and web sources.
External Dependencies:
    Python standard library modules ``argparse``, ``json``, ``logging``,
    ``sys``, ``pathlib``.
Fallback Semantics:
    Reports errors to stderr and continues with available functionality.
Timeout Strategy:
    Delegates timeout handling to research API orchestrator.
"""

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Any, Dict, Optional

from src.application.research_execution import ResearchQueryExecutor
from src.domain.preflight.models import BuiltQuery, QueryPlan
from src.research_apis import ResearchAPIOrchestrator

logger = logging.getLogger(__name__)


def load_query_plan(path: Path) -> QueryPlan:
    """Load a query plan from JSON file.
    
    Args:
        path: Path to query plan JSON file
    
    Returns:
        QueryPlan instance
    
    Raises:
        FileNotFoundError: If path does not exist
        json.JSONDecodeError: If JSON is invalid
        ValueError: If JSON structure is invalid
    
    Side Effects:
        Reads file from disk
    
    Timeout:
        Not applicable for file I/O
    """
    if not path.exists():
        raise FileNotFoundError(f"Query plan file not found: {path}")
    
    with path.open('r', encoding='utf-8') as f:
        data = json.load(f)
    
    # Parse queries
    queries = []
    for q_data in data.get('queries', []):
        query = BuiltQuery(
            id=q_data['id'],
            text=q_data['text'],
            purpose=q_data.get('purpose', ''),
            priority=q_data.get('priority', 0),
            depends_on_ids=tuple(q_data.get('depends_on_ids', [])),
            target_audience=q_data.get('target_audience'),
            suggested_tooling=tuple(q_data.get('suggested_tooling', [])),
        )
        queries.append(query)
    
    return QueryPlan(
        queries=tuple(queries),
        rationale=data.get('rationale', ''),
        assumptions=tuple(data.get('assumptions', [])),
        risks=tuple(data.get('risks', [])),
    )


def execute_query_plan_command(args: argparse.Namespace, config: Dict[str, Any]) -> int:
    """Execute a query plan from file.
    
    Args:
        args: Parsed command-line arguments
        config: Configuration dictionary
    
    Returns:
        Exit code (0 for success, 1 for failure)
    
    Raises:
        None - errors are logged
    
    Side Effects:
        Executes research queries and writes results
    
    Timeout:
        Depends on research API configuration
    """
    try:
        query_plan_path = Path(args.query_plan)
        logger.info("Loading query plan from %s", query_plan_path)
        
        query_plan = load_query_plan(query_plan_path)
        logger.info("Loaded query plan with %d queries", len(query_plan.queries))
        
        # Initialize research orchestrator
        orchestrator = ResearchAPIOrchestrator(config=config)
        
        # Initialize executor
        executor_config = {
            'max_results_per_query': args.max_results,
            'parallel_execution': not args.sequential,
        }
        executor = ResearchQueryExecutor(orchestrator, config=executor_config)
        
        # Parse sources if provided
        sources = None
        if args.sources:
            sources = [s.strip() for s in args.sources.split(',')]
        
        # Execute query plan
        output_path = Path(args.output) if args.output else None
        result = executor.execute_query_plan(
            query_plan,
            max_results_per_query=args.max_results,
            sources=sources,
            output_path=output_path
        )
        
        # Print summary
        print(f"\n{'='*60}")
        print("Research Query Execution Summary")
        print(f"{'='*60}")
        print(f"Total queries: {result.total_queries}")
        print(f"Successful: {result.successful_queries}")
        print(f"Failed: {result.failed_queries}")
        print(f"Total results: {result.total_results}")
        
        if output_path:
            print(f"\nResults saved to: {output_path}")
        
        if result.failed_queries > 0:
            print(f"\n{result.failed_queries} queries failed. Check logs for details.")
            return 1
        
        return 0
        
    except Exception as exc:  # noqa: BLE001 - defensive CLI handling
        logger.error("Query plan execution failed: %s", exc, exc_info=True)
        print(f"Error: {exc}", file=sys.stderr)
        return 1


def execute_ad_hoc_query_command(args: argparse.Namespace, config: Dict[str, Any]) -> int:
    """Execute an ad-hoc research query.
    
    Args:
        args: Parsed command-line arguments
        config: Configuration dictionary
    
    Returns:
        Exit code (0 for success, 1 for failure)
    
    Raises:
        None - errors are logged
    
    Side Effects:
        Executes research query and writes results
    
    Timeout:
        Depends on research API configuration
    """
    try:
        query_text = args.query
        logger.info("Executing ad-hoc query: %s", query_text)
        
        # Initialize research orchestrator
        orchestrator = ResearchAPIOrchestrator(config=config)
        
        # Initialize executor
        executor_config = {
            'max_results_per_query': args.max_results,
            'parallel_execution': not args.sequential,
        }
        executor = ResearchQueryExecutor(orchestrator, config=executor_config)
        
        # Create a simple query
        query = BuiltQuery(
            id="adhoc_query",
            text=query_text,
            purpose="Ad-hoc research query",
            priority=0,
        )
        
        # Parse sources if provided
        sources = None
        if args.sources:
            sources = [s.strip() for s in args.sources.split(',')]
        
        # Execute query
        results = executor.execute_single_query(
            query,
            max_results=args.max_results,
            sources=sources
        )
        
        # Print results
        print(f"\n{'='*60}")
        print(f"Research Results for: {query_text}")
        print(f"{'='*60}\n")
        print(f"Found {len(results)} results:\n")
        
        for i, result in enumerate(results, 1):
            print(f"{i}. {result.title}")
            print(f"   Source: {result.source}")
            print(f"   URL: {result.url}")
            if result.authors:
                authors_str = ", ".join(result.authors[:3])
                if len(result.authors) > 3:
                    authors_str += " et al."
                print(f"   Authors: {authors_str}")
            if result.published_date:
                print(f"   Published: {result.published_date}")
            if result.abstract:
                abstract_preview = result.abstract[:200]
                if len(result.abstract) > 200:
                    abstract_preview += "..."
                print(f"   Abstract: {abstract_preview}")
            print()
        
        # Save to file if requested
        if args.output:
            output_path = Path(args.output)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            results_data = [
                {
                    'title': r.title,
                    'authors': r.authors,
                    'abstract': r.abstract,
                    'url': r.url,
                    'published_date': r.published_date,
                    'source': r.source,
                    'metadata': r.metadata,
                }
                for r in results
            ]
            
            with output_path.open('w', encoding='utf-8') as f:
                json.dump({
                    'query': query_text,
                    'results_count': len(results),
                    'results': results_data,
                }, f, indent=2, ensure_ascii=False)
            
            print(f"Results saved to: {output_path}")
        
        return 0
        
    except Exception as exc:  # noqa: BLE001 - defensive CLI handling
        logger.error("Ad-hoc query execution failed: %s", exc, exc_info=True)
        print(f"Error: {exc}", file=sys.stderr)
        return 1


def build_argument_parser() -> argparse.ArgumentParser:
    """Build the argument parser for the research CLI.
    
    Returns:
        Configured ArgumentParser instance
    """
    parser = argparse.ArgumentParser(
        description="Execute research queries across multiple databases and web sources",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Command to execute')
    
    # Query plan execution command
    plan_parser = subparsers.add_parser(
        'execute-plan',
        help='Execute a query plan from JSON file'
    )
    plan_parser.add_argument(
        'query_plan',
        help='Path to query plan JSON file'
    )
    plan_parser.add_argument(
        '--output', '-o',
        help='Output file for results (JSON)'
    )
    plan_parser.add_argument(
        '--max-results',
        type=int,
        default=10,
        help='Maximum results per query (default: 10)'
    )
    plan_parser.add_argument(
        '--sources',
        help='Comma-separated list of sources (pubmed,semantic_scholar,crossref,web_search)'
    )
    plan_parser.add_argument(
        '--sequential',
        action='store_true',
        help='Execute queries sequentially instead of in parallel'
    )
    
    # Ad-hoc query command
    query_parser = subparsers.add_parser(
        'query',
        help='Execute an ad-hoc research query'
    )
    query_parser.add_argument(
        'query',
        help='Research query text'
    )
    query_parser.add_argument(
        '--output', '-o',
        help='Output file for results (JSON)'
    )
    query_parser.add_argument(
        '--max-results',
        type=int,
        default=10,
        help='Maximum results per source (default: 10)'
    )
    query_parser.add_argument(
        '--sources',
        help='Comma-separated list of sources to query'
    )
    query_parser.add_argument(
        '--sequential',
        action='store_true',
        help='Query sources sequentially instead of in parallel'
    )
    
    # List sources command
    subparsers.add_parser(
        'list-sources',
        help='List available research sources'
    )
    
    return parser


def main(argv=None) -> int:
    """Main entry point for research CLI.
    
    Args:
        argv: Optional command-line arguments
    
    Returns:
        Exit code
    """
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(name)s - %(message)s'
    )
    
    parser = build_argument_parser()
    args = parser.parse_args(argv)
    
    if not args.command:
        parser.print_help()
        return 1
    
    # Load configuration
    config_path = Path('config.json')
    if config_path.exists():
        with config_path.open('r') as f:
            config = json.load(f)
    else:
        config = {}
    
    # Handle commands
    if args.command == 'execute-plan':
        return execute_query_plan_command(args, config)
    elif args.command == 'query':
        return execute_ad_hoc_query_command(args, config)
    elif args.command == 'list-sources':
        orchestrator = ResearchAPIOrchestrator(config=config)
        sources = orchestrator.get_available_sources()
        print("Available research sources:")
        for source in sources:
            print(f"  - {source}")
        return 0
    else:
        parser.print_help()
        return 1


if __name__ == '__main__':
    sys.exit(main())
