import asyncio
import json
from typing import Any, Dict

from cachetools.func import ttl_cache
from dotenv import load_dotenv
from mcp.server import InitializationOptions, NotificationOptions
from mcp.server import Server, types
from mcp.server.stdio import stdio_server
from pydantic import AnyUrl

# Initialize logging after imports to avoid early execution
def setup_logging():
    import logging
    import os
    from dotenv import load_dotenv
    
    # Load environment variables from .env file
    load_dotenv()
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    logger = logging.getLogger("zendesk-mcp-server")
    logger.info("zendesk mcp server started")
    
    from zendesk_mcp_server.zendesk_client import ZendeskClient
    
    zendesk_client = ZendeskClient(
        subdomain=os.getenv("ZENDESK_SUBDOMAIN"),
        email=os.getenv("ZENDESK_EMAIL"),
        token=os.getenv("ZENDESK_API_KEY")
    )
    
    return logger, zendesk_client

# Initialize these in main() to avoid early execution
logger = None
zendesk_client = None
server = Server("Zendesk Server")

TICKET_ANALYSIS_TEMPLATE = """
You are a helpful Zendesk support analyst. You've been asked to analyze ticket #{ticket_id}.

Please fetch the ticket info and comments to analyze it and provide:
1. A summary of the issue
2. The current status and timeline
3. Key points of interaction

Remember to be professional and focus on actionable insights.
"""

COMMENT_DRAFT_TEMPLATE = """
You are a helpful Zendesk support agent. You need to draft a response to ticket #{ticket_id}.

Please fetch the ticket info, comments and knowledge base to draft a professional and helpful response that:
1. Acknowledges the customer's concern
2. Addresses the specific issues raised
3. Provides clear next steps or ask for specific details need to proceed
4. Maintains a friendly and professional tone
5. Ask for confirmation before commenting on the ticket

The response should be formatted well and ready to be posted as a comment.
"""

ANALYTICS_DASHBOARD_TEMPLATE = """
You are a Zendesk analytics specialist. Please create a comprehensive support analytics dashboard.

Use the available tools to gather and analyze:
1. Overall ticket counts and distribution by status/priority
2. Recent ticket metrics and performance trends
3. Customer satisfaction scores and feedback
4. Key insights and recommendations

Present the data in a clear, executive-friendly format with:
- Key metrics summary
- Trend analysis
- Areas of concern or improvement
- Actionable recommendations

Focus on metrics that help improve customer service quality and team efficiency.
"""

TICKET_SEARCH_TEMPLATE = """
You are a Zendesk search specialist. You need to help find tickets based on the criteria: {search_criteria}

Use the search_tickets tool with appropriate Zendesk query syntax to find relevant tickets.

Guidelines for effective searching:
1. Use specific operators like status:, priority:, assignee:, created:, etc.
2. Combine multiple criteria when needed
3. Consider date ranges for time-based searches
4. Present results with key ticket details and summary stats

Provide a clear summary of what was found and suggest refinements if needed.
"""

USER_WORKLOAD_TEMPLATE = """
You are a Zendesk team lead analyzing agent workload for user #{user_id}.

Please gather comprehensive workload data:
1. Get all assigned tickets for this user
2. Get tickets they've requested (if any)
3. Get tickets they're CC'd on for collaboration tracking
4. Analyze the distribution by status and priority

Present a workload summary including:
- Current ticket load by status
- Priority distribution of assigned work
- Recent activity patterns
- Workload balance recommendations

Focus on insights that help with resource allocation and workload management.
"""


@server.list_prompts()
async def handle_list_prompts() -> list[types.Prompt]:
    """List available prompts"""
    return [
        types.Prompt(
            name="analyze-ticket",
            description="Analyze a Zendesk ticket and provide insights",
            arguments=[
                types.PromptArgument(
                    name="ticket_id",
                    description="The ID of the ticket to analyze",
                    required=True,
                )
            ],
        ),
        types.Prompt(
            name="draft-ticket-response",
            description="Draft a professional response to a Zendesk ticket",
            arguments=[
                types.PromptArgument(
                    name="ticket_id",
                    description="The ID of the ticket to respond to",
                    required=True,
                )
            ],
        ),
        types.Prompt(
            name="analytics-dashboard",
            description="Create a comprehensive analytics dashboard with ticket metrics, counts, and satisfaction data",
            arguments=[],
        ),
        types.Prompt(
            name="search-tickets",
            description="Search for tickets using specific criteria with guided query syntax",
            arguments=[
                types.PromptArgument(
                    name="search_criteria",
                    description="Description of what tickets to search for (e.g., 'high priority open tickets', 'urgent tickets from last week')",
                    required=True,
                )
            ],
        ),
        types.Prompt(
            name="analyze-user-workload",
            description="Analyze workload and ticket distribution for a specific user/agent",
            arguments=[
                types.PromptArgument(
                    name="user_id",
                    description="The ID of the user to analyze workload for",
                    required=True,
                )
            ],
        )
    ]


@server.get_prompt()
async def handle_get_prompt(name: str, arguments: Dict[str, str] | None) -> types.GetPromptResult:
    """Handle prompt requests"""
    try:
        if name == "analyze-ticket":
            if not arguments or "ticket_id" not in arguments:
                raise ValueError("Missing required argument: ticket_id")
            ticket_id = int(arguments["ticket_id"])
            prompt = TICKET_ANALYSIS_TEMPLATE.format(ticket_id=ticket_id)
            description = f"Analysis prompt for ticket #{ticket_id}"

        elif name == "draft-ticket-response":
            if not arguments or "ticket_id" not in arguments:
                raise ValueError("Missing required argument: ticket_id")
            ticket_id = int(arguments["ticket_id"])
            prompt = COMMENT_DRAFT_TEMPLATE.format(ticket_id=ticket_id)
            description = f"Response draft prompt for ticket #{ticket_id}"

        elif name == "analytics-dashboard":
            prompt = ANALYTICS_DASHBOARD_TEMPLATE
            description = "Analytics dashboard creation prompt with comprehensive metrics"

        elif name == "search-tickets":
            if not arguments or "search_criteria" not in arguments:
                raise ValueError("Missing required argument: search_criteria")
            search_criteria = arguments["search_criteria"]
            prompt = TICKET_SEARCH_TEMPLATE.format(search_criteria=search_criteria)
            description = f"Ticket search prompt for: {search_criteria}"

        elif name == "analyze-user-workload":
            if not arguments or "user_id" not in arguments:
                raise ValueError("Missing required argument: user_id")
            user_id = int(arguments["user_id"])
            prompt = USER_WORKLOAD_TEMPLATE.format(user_id=user_id)
            description = f"Workload analysis prompt for user #{user_id}"

        else:
            raise ValueError(f"Unknown prompt: {name}")

        return types.GetPromptResult(
            description=description,
            messages=[
                types.PromptMessage(
                    role="user",
                    content=types.TextContent(type="text", text=prompt.strip()),
                )
            ],
        )

    except Exception as e:
        logger.error(f"Error generating prompt: {e}")
        raise


@server.list_tools()
async def handle_list_tools() -> list[types.Tool]:
    """List available Zendesk tools"""
    return [
        types.Tool(
            name="get_ticket",
            description="Retrieve a Zendesk ticket by its ID",
            inputSchema={
                "type": "object",
                "properties": {
                    "ticket_id": {
                        "type": "integer",
                        "description": "The ID of the ticket to retrieve"
                    }
                },
                "required": ["ticket_id"]
            }
        ),
        types.Tool(
            name="get_ticket_comments",
            description="Retrieve all comments for a Zendesk ticket by its ID",
            inputSchema={
                "type": "object",
                "properties": {
                    "ticket_id": {
                        "type": "integer",
                        "description": "The ID of the ticket to get comments for"
                    }
                },
                "required": ["ticket_id"]
            }
        ),
        types.Tool(
            name="create_ticket_comment",
            description="Create a new comment on an existing Zendesk ticket",
            inputSchema={
                "type": "object",
                "properties": {
                    "ticket_id": {
                        "type": "integer",
                        "description": "The ID of the ticket to comment on"
                    },
                    "comment": {
                        "type": "string",
                        "description": "The comment text/content to add"
                    },
                    "public": {
                        "type": "boolean",
                        "description": "Whether the comment should be public",
                        "default": True
                    }
                },
                "required": ["ticket_id", "comment"]
            }
        ),
        types.Tool(
            name="search_tickets",
            description="Search for tickets using Zendesk's powerful search API with query syntax",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query using Zendesk syntax (e.g., 'status:open priority:high', 'assignee:me', 'created>2024-01-01')"
                    },
                    "sort_by": {
                        "type": "string",
                        "description": "Field to sort by (created_at, updated_at, priority, status, etc.)",
                        "default": "created_at"
                    },
                    "sort_order": {
                        "type": "string",
                        "description": "Sort order (asc or desc)",
                        "enum": ["asc", "desc"],
                        "default": "desc"
                    }
                },
                "required": ["query"]
            }
        ),
        types.Tool(
            name="get_ticket_counts",
            description="Get counts and statistics of tickets by status and priority",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            }
        ),
        types.Tool(
            name="get_ticket_metrics",
            description="Get ticket metrics and analytics data. Can get metrics for a specific ticket or aggregate metrics",
            inputSchema={
                "type": "object",
                "properties": {
                    "ticket_id": {
                        "type": "integer",
                        "description": "Optional: ID of specific ticket to get metrics for. If not provided, returns aggregate metrics"
                    }
                },
                "required": []
            }
        ),
        types.Tool(
            name="get_user_tickets",
            description="Get tickets for a specific user (requested, assigned, or CC'd)",
            inputSchema={
                "type": "object",
                "properties": {
                    "user_id": {
                        "type": "integer",
                        "description": "The ID of the user"
                    },
                    "ticket_type": {
                        "type": "string",
                        "description": "Type of tickets to retrieve",
                        "enum": ["requested", "assigned", "ccd"],
                        "default": "requested"
                    }
                },
                "required": ["user_id"]
            }
        ),
        types.Tool(
            name="get_organization_tickets",
            description="Get all tickets for a specific organization",
            inputSchema={
                "type": "object",
                "properties": {
                    "organization_id": {
                        "type": "integer",
                        "description": "The ID of the organization"
                    }
                },
                "required": ["organization_id"]
            }
        ),
        types.Tool(
            name="get_satisfaction_ratings",
            description="Get customer satisfaction (CSAT) ratings and survey responses",
            inputSchema={
                "type": "object",
                "properties": {
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of ratings to retrieve",
                        "default": 100,
                        "minimum": 1,
                        "maximum": 1000
                    }
                },
                "required": []
            }
        )
    ]


@server.call_tool()
async def handle_call_tool(
        name: str,
        arguments: dict[str, Any] | None
) -> list[types.TextContent]:
    """Handle Zendesk tool execution requests"""
    try:
        if name == "get_ticket":
            if not arguments or "ticket_id" not in arguments:
                raise ValueError("Missing required argument: ticket_id")
            ticket = zendesk_client.get_ticket(arguments["ticket_id"])
            return [types.TextContent(
                type="text",
                text=json.dumps(ticket, indent=2)
            )]

        elif name == "get_ticket_comments":
            if not arguments or "ticket_id" not in arguments:
                raise ValueError("Missing required argument: ticket_id")
            comments = zendesk_client.get_ticket_comments(
                arguments["ticket_id"])
            return [types.TextContent(
                type="text",
                text=json.dumps(comments, indent=2)
            )]

        elif name == "create_ticket_comment":
            if not arguments or "ticket_id" not in arguments or "comment" not in arguments:
                raise ValueError("Missing required arguments: ticket_id and comment")
            public = arguments.get("public", True)
            result = zendesk_client.post_comment(
                ticket_id=arguments["ticket_id"],
                comment=arguments["comment"],
                public=public
            )
            return [types.TextContent(
                type="text",
                text=f"Comment created successfully: {result}"
            )]

        elif name == "search_tickets":
            if not arguments or "query" not in arguments:
                raise ValueError("Missing required argument: query")
            query = arguments["query"]
            sort_by = arguments.get("sort_by", "created_at")
            sort_order = arguments.get("sort_order", "desc")
            
            tickets = zendesk_client.search_tickets(
                query=query,
                sort_by=sort_by,
                sort_order=sort_order
            )
            
            # Limit results to prevent overwhelming Claude
            max_tickets = 25  # Reasonable limit for display
            if len(tickets) > max_tickets:
                limited_tickets = tickets[:max_tickets]
                return [types.TextContent(
                    type="text",
                    text=json.dumps({
                        "query": query,
                        "total_found": len(tickets),
                        "showing": max_tickets,
                        "note": f"Showing first {max_tickets} of {len(tickets)} results. Use more specific query to narrow results.",
                        "tickets": limited_tickets
                    }, indent=2)
                )]
            else:
                return [types.TextContent(
                    type="text",
                    text=json.dumps({
                        "query": query,
                        "total_found": len(tickets),
                        "tickets": tickets
                    }, indent=2)
                )]

        elif name == "get_ticket_counts":
            # No arguments required for this tool
            counts = zendesk_client.get_ticket_counts()
            return [types.TextContent(
                type="text",
                text=json.dumps(counts, indent=2)
            )]

        elif name == "get_ticket_metrics":
            # Optional ticket_id argument
            ticket_id = arguments.get("ticket_id") if arguments else None
            metrics = zendesk_client.get_ticket_metrics(ticket_id)
            return [types.TextContent(
                type="text",
                text=json.dumps(metrics, indent=2)
            )]

        elif name == "get_user_tickets":
            if not arguments or "user_id" not in arguments:
                raise ValueError("Missing required argument: user_id")
            user_id = arguments["user_id"]
            ticket_type = arguments.get("ticket_type", "requested")
            
            tickets = zendesk_client.get_user_tickets(
                user_id=user_id,
                ticket_type=ticket_type
            )
            
            return [types.TextContent(
                type="text",
                text=json.dumps({
                    "user_id": user_id,
                    "ticket_type": ticket_type,
                    "total_tickets": len(tickets),
                    "tickets": tickets
                }, indent=2)
            )]

        elif name == "get_organization_tickets":
            if not arguments or "organization_id" not in arguments:
                raise ValueError("Missing required argument: organization_id")
            org_id = arguments["organization_id"]
            tickets = zendesk_client.get_organization_tickets(org_id)
            
            return [types.TextContent(
                type="text",
                text=json.dumps({
                    "organization_id": org_id,
                    "total_tickets": len(tickets),
                    "tickets": tickets
                }, indent=2)
            )]

        elif name == "get_satisfaction_ratings":
            # Optional limit argument
            limit = arguments.get("limit", 100) if arguments else 100
            ratings = zendesk_client.get_satisfaction_ratings(limit)
            
            # Calculate some basic stats
            if ratings:
                scores = [r['score'] for r in ratings if r['score']]
                score_counts = {}
                for score in scores:
                    score_counts[score] = score_counts.get(score, 0) + 1
                
                stats = {
                    "total_ratings": len(ratings),
                    "score_distribution": score_counts,
                    "ratings": ratings
                }
            else:
                stats = {
                    "total_ratings": 0,
                    "score_distribution": {},
                    "ratings": []
                }
            
            return [types.TextContent(
                type="text",
                text=json.dumps(stats, indent=2)
            )]

        else:
            raise ValueError(f"Unknown tool: {name}")

    except Exception as e:
        return [types.TextContent(
            type="text",
            text=f"Error: {str(e)}"
        )]


@server.list_resources()
async def handle_list_resources() -> list[types.Resource]:
    logger.debug("Handling list_resources request")
    return [
        types.Resource(
            uri=AnyUrl("zendesk://knowledge-base"),
            name="Zendesk Knowledge Base",
            description="Access to Zendesk Help Center articles and sections",
            mimeType="application/json",
        )
    ]


@ttl_cache(ttl=3600)
def get_cached_kb():
    return zendesk_client.get_all_articles()


@server.read_resource()
async def handle_read_resource(uri: AnyUrl) -> str:
    logger.debug(f"Handling read_resource request for URI: {uri}")
    if uri.scheme != "zendesk":
        logger.error(f"Unsupported URI scheme: {uri.scheme}")
        raise ValueError(f"Unsupported URI scheme: {uri.scheme}")

    path = str(uri).replace("zendesk://", "")
    if path != "knowledge-base":
        logger.error(f"Unknown resource path: {path}")
        raise ValueError(f"Unknown resource path: {path}")

    try:
        kb_data = get_cached_kb()
        return json.dumps({
            "knowledge_base": kb_data,
            "metadata": {
                "sections": len(kb_data),
                "total_articles": sum(len(section['articles']) for section in kb_data.values()),
            }
        }, indent=2)
    except Exception as e:
        logger.error(f"Error fetching knowledge base: {e}")
        raise


async def main():
    """Main entry point for the Zendesk MCP server"""
    import sys
    global logger, zendesk_client
    
    # Initialize logging and client
    logger, zendesk_client = setup_logging()
    
    # Check for help flag
    if len(sys.argv) > 1 and sys.argv[1] in ['--help', '-h', 'help']:
        print("""
Zendesk MCP Server

This is a Model Context Protocol (MCP) server for Zendesk integration.
It provides tools for ticket management, search, analytics, and more.

USAGE:
    This server is designed to be used with MCP clients like Claude Desktop.
    It communicates via stdin/stdout using the MCP protocol.

CONFIGURATION:
    Add this server to your Claude Desktop config:
    
    {
        "mcpServers": {
            "zendesk": {
                "command": "uv",
                "args": [
                    "--directory", 
                    "/path/to/zendesk-mcp-server",
                    "run",
                    "zendesk"
                ]
            }
        }
    }

ENVIRONMENT VARIABLES:
    ZENDESK_SUBDOMAIN - Your Zendesk subdomain
    ZENDESK_EMAIL     - Your Zendesk email
    ZENDESK_API_KEY   - Your Zendesk API key

FEATURES:
    - Ticket management (get, create comments)
    - Advanced search with query syntax
    - Analytics and performance metrics
    - Customer satisfaction tracking
    - User and organization analysis
    - Knowledge base integration

For more information, see README.md
        """)
        return
    
    # Run the MCP server using stdin/stdout streams
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream=read_stream,
            write_stream=write_stream,
            initialization_options=InitializationOptions(
                server_name="Zendesk",
                server_version="0.1.0",
                capabilities=server.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={},
                ),
            ),
        )


if __name__ == "__main__":
    asyncio.run(main())
