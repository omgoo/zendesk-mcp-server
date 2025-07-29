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
Analyze user/agent workload and performance. Available tools:
- get_user_tickets: Get tickets for a specific user
- get_organization_tickets: Get tickets for an organization  
- search_tickets: Search with user-specific queries

Useful queries:
- assignee:user@company.com status:open (user's open tickets)
- requester:user@company.com (tickets requested by user)
- organization:"Company Name" status:pending
"""

AGENT_PERFORMANCE_TEMPLATE = """
Analyze support agent performance metrics over a specified time period. This tool provides:

**Key Metrics:**
- Tickets solved per agent
- Average priority score (urgent=4, high=3, normal=2, low=1)
- Performance ranking
- Ticket subjects for context

**Usage:**
Use get_agent_performance tool with optional 'days' parameter (default: 7 days)

**Example Analysis Questions:**
- Who is the best performing agent this week?
- Which agents handled the most urgent tickets?
- Show me agent performance for the last 30 days
- Who solved the most tickets yesterday? (days: 1)

**Output includes:**
- Top 10 performing agents
- Agent names and contact info
- Ticket counts and priority scores
- Summary statistics

This tool is optimized for performance analysis with minimal data to avoid overwhelming responses.
"""

# Prompt configurations
PROMPTS = {
    "analytics-dashboard": ANALYTICS_DASHBOARD_TEMPLATE,
    "search-tickets": TICKET_SEARCH_TEMPLATE,
    "analyze-user-workload": USER_WORKLOAD_TEMPLATE,
    "agent-performance": AGENT_PERFORMANCE_TEMPLATE
}


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
        ),
        types.Prompt(
            name="agent-performance",
            description="Analyze support agent performance metrics over a specified time period",
            arguments=[
                types.PromptArgument(
                    name="days",
                    description="Number of days to analyze (default: 7)",
                    required=False,
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

        elif name == "agent-performance":
            days = int(arguments.get("days", 7)) if arguments and "days" in arguments else 7
            prompt = AGENT_PERFORMANCE_TEMPLATE
            description = f"Agent performance analysis prompt for {days} days"

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
            description="Retrieve comments for a Zendesk ticket with data limits to avoid conversation overflow",
            inputSchema={
                "type": "object",
                "properties": {
                    "ticket_id": {
                        "type": "integer",
                        "description": "The ID of the ticket to get comments for"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of comments to return (default: 10, reduces conversation limits)"
                    },
                    "include_body": {
                        "type": "boolean",
                        "description": "Whether to include comment content (default: true)"
                    },
                    "max_body_length": {
                        "type": "integer",
                        "description": "Maximum length of comment content (default: 300)"
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
            description="Search for tickets using Zendesk query syntax. Optimized for chat length limits with compact results by default.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query (e.g., 'status:open', 'priority:urgent', 'created>7days')"
                    },
                    "sort_by": {
                        "type": "string", 
                        "description": "Field to sort by (created_at, updated_at, priority, status)",
                        "default": "created_at"
                    },
                    "sort_order": {
                        "type": "string",
                        "description": "Sort order (asc or desc)", 
                        "default": "desc"
                    },
                    "compact": {
                        "type": "boolean",
                        "description": "Return minimal data without descriptions for better performance (default: true)"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of tickets to return (default: 10, max: 20)"
                    },
                    "summarize": {
                        "type": "boolean",
                        "description": "Return summary statistics instead of full ticket list (default: false)"
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
            description="Get ticket metrics and analytics data. Returns key numbers only by default to prevent large responses.",
            inputSchema={
                "type": "object",
                "properties": {
                    "ticket_id": {
                        "type": "integer",
                        "description": "Optional: ID of specific ticket to get metrics for. If not provided, returns aggregate metrics"
                    },
                    "summarize": {
                        "type": "boolean",
                        "description": "Return key numbers only (default: true)"
                    }
                },
                "required": []
            }
        ),
        types.Tool(
            name="get_user_tickets",
            description="Get tickets for a specific user (requested, assigned, or CC'd). Returns compact results by default.",
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
                    },
                    "compact": {
                        "type": "boolean",
                        "description": "Return minimal data for better performance (default: true)"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of tickets to return (default: 10, max: 20)"
                    },
                    "summarize": {
                        "type": "boolean",
                        "description": "Return summary statistics instead of full ticket list (default: false)"
                    }
                },
                "required": ["user_id"]
            }
        ),
        types.Tool(
            name="get_organization_tickets",
            description="Get all tickets for a specific organization. Returns compact results by default.",
            inputSchema={
                "type": "object",
                "properties": {
                    "organization_id": {
                        "type": "integer",
                        "description": "The ID of the organization"
                    },
                    "compact": {
                        "type": "boolean",
                        "description": "Return minimal data for better performance (default: true)"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of tickets to return (default: 10, max: 20)"
                    },
                    "summarize": {
                        "type": "boolean",
                        "description": "Return summary statistics instead of full ticket list (default: false)"
                    }
                },
                "required": ["organization_id"]
            }
        ),
        types.Tool(
            name="get_satisfaction_ratings",
            description="Get customer satisfaction ratings with score distribution",
            inputSchema={
                "type": "object", 
                "properties": {
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of ratings to retrieve (default: 100)"
                    }
                }
            }
        ),
        types.Tool(
            name="get_agent_performance",
            description="Get agent performance metrics for a specified time period. Returns minimal data optimized for analysis.",
            inputSchema={
                "type": "object", 
                "properties": {
                    "days": {
                        "type": "integer",
                        "description": "Number of days to analyze (default: 7)",
                        "minimum": 1,
                        "maximum": 90
                    }
                }
            }
        ),
        types.Tool(
            name="get_user_by_id",
            description="Get detailed user information by user ID. Useful for resolving agent IDs to names.",
            inputSchema={
                "type": "object", 
                "properties": {
                    "user_id": {
                        "type": "integer",
                        "description": "The ID of the user to retrieve information for"
                    }
                },
                "required": ["user_id"]
            }
        ),
        # Enterprise Performance Analytics
        types.Tool(
            name="get_agent_performance_metrics",
            description="Get comprehensive agent performance metrics. Returns summary statistics by default to prevent large responses.",
            inputSchema={
                "type": "object", 
                "properties": {
                    "agent_id": {
                        "type": "integer",
                        "description": "Agent ID to analyze (optional - if not provided, analyzes all agents)"
                    },
                    "start_date": {
                        "type": "string",
                        "description": "Start date for analysis (YYYY-MM-DD format, default: 30 days ago)"
                    },
                    "end_date": {
                        "type": "string", 
                        "description": "End date for analysis (YYYY-MM-DD format, default: today)"
                    },
                    "include_satisfaction": {
                        "type": "boolean",
                        "description": "Include customer satisfaction data (default: true)"
                    },
                    "summarize": {
                        "type": "boolean",
                        "description": "Return summary format instead of raw data (default: true)"
                    }
                }
            }
        ),
        types.Tool(
            name="get_team_performance_dashboard",
            description="Generate team-wide performance dashboard. Returns rankings summary by default to prevent large responses.",
            inputSchema={
                "type": "object",
                "properties": {
                    "team_id": {
                        "type": "integer",
                        "description": "Team/group ID to analyze (optional)"
                    },
                    "period": {
                        "type": "string",
                        "description": "Time period for analysis (week, month, quarter, default: week)"
                    },
                    "summarize": {
                        "type": "boolean",
                        "description": "Return summary format instead of full dashboard (default: true)"
                    }
                }
            }
        ),
        types.Tool(
            name="generate_agent_scorecard",
            description="Create detailed agent scorecard with performance vs targets and improvement areas.",
            inputSchema={
                "type": "object",
                "properties": {
                    "agent_id": {
                        "type": "integer",
                        "description": "Agent ID to generate scorecard for"
                    },
                    "period": {
                        "type": "string",
                        "description": "Time period for scorecard (week, month, quarter, default: month)"
                    }
                },
                "required": ["agent_id"]
            }
        ),

        # Workload Management
        types.Tool(
            name="get_agent_workload_analysis",
            description="Analyze current workload distribution across agents with capacity utilization and imbalance alerts.",
            inputSchema={
                "type": "object",
                "properties": {
                    "include_pending": {
                        "type": "boolean",
                        "description": "Include pending tickets in analysis (default: true)"
                    },
                    "include_open": {
                        "type": "boolean",
                        "description": "Include open tickets in analysis (default: true)"
                    }
                }
            }
        ),
        types.Tool(
            name="suggest_ticket_reassignment",
            description="Suggest ticket reassignments to balance workload or match agent expertise.",
            inputSchema={
                "type": "object",
                "properties": {
                    "criteria": {
                        "type": "string",
                        "description": "Reassignment criteria (workload_balance, expertise, availability, default: workload_balance)"
                    }
                }
            }
        ),

        # SLA Monitoring
        types.Tool(
            name="get_sla_compliance_report",
            description="Generate SLA compliance report with first response and resolution time compliance.",
            inputSchema={
                "type": "object",
                "properties": {
                    "start_date": {
                        "type": "string",
                        "description": "Start date for report (YYYY-MM-DD format)"
                    },
                    "end_date": {
                        "type": "string",
                        "description": "End date for report (YYYY-MM-DD format)"
                    },
                    "agent_id": {
                        "type": "integer",
                        "description": "Filter by specific agent ID (optional)"
                    }
                }
            }
        ),
        types.Tool(
            name="get_at_risk_tickets",
            description="Identify tickets at risk of SLA breach with time remaining and escalation recommendations.",
            inputSchema={
                "type": "object",
                "properties": {
                    "time_horizon": {
                        "type": "integer",
                        "description": "Time horizon in hours to check for SLA breach risk (default: 24)"
                    }
                }
            }
        ),

        # Advanced Automation
        types.Tool(
            name="bulk_update_tickets",
            description="Perform bulk updates on multiple tickets (status, priority, tags, assignments).",
            inputSchema={
                "type": "object",
                "properties": {
                    "ticket_ids": {
                        "type": "array",
                        "items": {"type": "integer"},
                        "description": "List of ticket IDs to update"
                    },
                    "updates": {
                        "type": "object",
                        "description": "Object containing updates to apply (status, priority, tags, assignee_id, etc.)"
                    },
                    "reason": {
                        "type": "string",
                        "description": "Optional reason for bulk update"
                    }
                },
                "required": ["ticket_ids", "updates"]
            }
        ),
        types.Tool(
            name="auto_categorize_tickets",
            description="Automatically categorize tickets based on content analysis and historical patterns.",
            inputSchema={
                "type": "object",
                "properties": {
                    "ticket_ids": {
                        "type": "array",
                        "items": {"type": "integer"},
                        "description": "List of ticket IDs to categorize (optional - if not provided, categorizes recent untagged tickets)"
                    },
                    "use_ml": {
                        "type": "boolean",
                        "description": "Use machine learning models for categorization (default: true)"
                    }
                }
            }
        ),
        types.Tool(
            name="escalate_ticket",
            description="Escalate tickets with proper notifications and tracking.",
            inputSchema={
                "type": "object",
                "properties": {
                    "ticket_id": {
                        "type": "integer",
                        "description": "Ticket ID to escalate"
                    },
                    "escalation_level": {
                        "type": "string",
                        "description": "Escalation level (manager, senior_agent, external)"
                    },
                    "reason": {
                        "type": "string",
                        "description": "Reason for escalation"
                    },
                    "notify_stakeholders": {
                        "type": "boolean",
                        "description": "Send notifications to stakeholders (default: true)"
                    }
                },
                "required": ["ticket_id", "escalation_level", "reason"]
            }
        ),

        # MACROS AND TEMPLATES MANAGEMENT
        types.Tool(
            name="get_macros",
            description="Get all available macros for agents with usage statistics.",
            inputSchema={"type": "object", "properties": {}}
        ),
        types.Tool(
            name="apply_macro_to_ticket",
            description="Apply a macro to a specific ticket.",
            inputSchema={
                "type": "object",
                "properties": {
                    "ticket_id": {
                        "type": "integer",
                        "description": "The ID of the ticket to apply macro to"
                    },
                    "macro_id": {
                        "type": "integer", 
                        "description": "The ID of the macro to apply"
                    }
                },
                "required": ["ticket_id", "macro_id"]
            }
        ),
        types.Tool(
            name="get_ticket_forms",
            description="Get all ticket forms and their field configurations.",
            inputSchema={"type": "object", "properties": {}}
        ),

        # ADVANCED TICKET OPERATIONS
        types.Tool(
            name="merge_tickets",
            description="Merge multiple source tickets into one target ticket.",
            inputSchema={
                "type": "object",
                "properties": {
                    "source_ticket_ids": {
                        "type": "array",
                        "items": {"type": "integer"},
                        "description": "List of ticket IDs to merge from"
                    },
                    "target_ticket_id": {
                        "type": "integer",
                        "description": "The ticket ID to merge into"
                    }
                },
                "required": ["source_ticket_ids", "target_ticket_id"]
            }
        ),
        types.Tool(
            name="clone_ticket",
            description="Clone a ticket with optional comments.",
            inputSchema={
                "type": "object",
                "properties": {
                    "ticket_id": {
                        "type": "integer",
                        "description": "The ticket ID to clone"
                    },
                    "include_comments": {
                        "type": "boolean",
                        "description": "Whether to include comments in the clone (default: false)"
                    }
                },
                "required": ["ticket_id"]
            }
        ),
        types.Tool(
            name="add_ticket_tags",
            description="Add tags to a ticket.",
            inputSchema={
                "type": "object",
                "properties": {
                    "ticket_id": {
                        "type": "integer",
                        "description": "The ticket ID"
                    },
                    "tags": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of tags to add"
                    }
                },
                "required": ["ticket_id", "tags"]
            }
        ),
        types.Tool(
            name="remove_ticket_tags",
            description="Remove specific tags from a ticket.",
            inputSchema={
                "type": "object",
                "properties": {
                    "ticket_id": {
                        "type": "integer",
                        "description": "The ticket ID"
                    },
                    "tags": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of tags to remove"
                    }
                },
                "required": ["ticket_id", "tags"]
            }
        ),
        types.Tool(
            name="get_ticket_related_tickets",
            description="Get tickets related to the current ticket.",
            inputSchema={
                "type": "object",
                "properties": {
                    "ticket_id": {
                        "type": "integer",
                        "description": "The ticket ID to find related tickets for"
                    }
                },
                "required": ["ticket_id"]
            }
        ),

        # ORGANIZATION MANAGEMENT
        types.Tool(
            name="get_organizations",
            description="Get organizations with optional filtering. Returns compact results by default.",
            inputSchema={
                "type": "object",
                "properties": {
                    "external_id": {
                        "type": "string",
                        "description": "Filter by external ID"
                    },
                    "name": {
                        "type": "string",
                        "description": "Filter by organization name"
                    },
                    "compact": {
                        "type": "boolean",
                        "description": "Return minimal data for better performance (default: true)"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of organizations to return (default: 10, max: 20)"
                    }
                }
            }
        ),
        types.Tool(
            name="get_organization_details",
            description="Get detailed organization information including custom fields.",
            inputSchema={
                "type": "object",
                "properties": {
                    "org_id": {
                        "type": "integer",
                        "description": "Organization ID to get details for"
                    }
                },
                "required": ["org_id"]
            }
        ),
        types.Tool(
            name="update_organization",
            description="Update organization details.",
            inputSchema={
                "type": "object",
                "properties": {
                    "org_id": {
                        "type": "integer",
                        "description": "Organization ID to update"
                    },
                    "name": {
                        "type": "string",
                        "description": "New organization name"
                    },
                    "details": {
                        "type": "string",
                        "description": "Organization details"
                    },
                    "notes": {
                        "type": "string",
                        "description": "Organization notes"
                    }
                },
                "required": ["org_id"]
            }
        ),
        types.Tool(
            name="get_organization_users",
            description="Get all users in an organization.",
            inputSchema={
                "type": "object",
                "properties": {
                    "org_id": {
                        "type": "integer",
                        "description": "Organization ID to get users for"
                    }
                },
                "required": ["org_id"]
            }
        ),

        # ADVANCED USER MANAGEMENT
        types.Tool(
            name="create_user",
            description="Create a new user.",
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "User's full name"
                    },
                    "email": {
                        "type": "string",
                        "description": "User's email address"
                    },
                    "role": {
                        "type": "string",
                        "description": "User role (end-user, agent, admin, default: end-user)"
                    },
                    "organization_id": {
                        "type": "integer",
                        "description": "Optional organization ID"
                    }
                },
                "required": ["name", "email"]
            }
        ),
        types.Tool(
            name="update_user",
            description="Update user information.",
            inputSchema={
                "type": "object",
                "properties": {
                    "user_id": {
                        "type": "integer",
                        "description": "User ID to update"
                    },
                    "name": {
                        "type": "string",
                        "description": "New name"
                    },
                    "email": {
                        "type": "string",
                        "description": "New email"
                    },
                    "role": {
                        "type": "string",
                        "description": "New role"
                    }
                },
                "required": ["user_id"]
            }
        ),
        types.Tool(
            name="suspend_user",
            description="Suspend a user account.",
            inputSchema={
                "type": "object",
                "properties": {
                    "user_id": {
                        "type": "integer",
                        "description": "User ID to suspend"
                    },
                    "reason": {
                        "type": "string",
                        "description": "Optional reason for suspension"
                    }
                },
                "required": ["user_id"]
            }
        ),
        types.Tool(
            name="search_users",
            description="Search for users with advanced filters.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query string"
                    },
                    "role": {
                        "type": "string",
                        "description": "Filter by role"
                    },
                    "organization_id": {
                        "type": "integer",
                        "description": "Filter by organization"
                    }
                },
                "required": ["query"]
            }
        ),
        types.Tool(
            name="get_user_identities",
            description="Get user identity information (email addresses, phone numbers, etc.).",
            inputSchema={
                "type": "object",
                "properties": {
                    "user_id": {
                        "type": "integer",
                        "description": "User ID to get identities for"
                    }
                },
                "required": ["user_id"]
            }
        ),

        # GROUPS AND AGENT MANAGEMENT
        types.Tool(
            name="get_groups",
            description="Get all support groups.",
            inputSchema={"type": "object", "properties": {}}
        ),
        types.Tool(
            name="get_group_memberships",
            description="Get group memberships.",
            inputSchema={
                "type": "object",
                "properties": {
                    "group_id": {
                        "type": "integer",
                        "description": "Filter by specific group"
                    },
                    "user_id": {
                        "type": "integer",
                        "description": "Filter by specific user"
                    }
                }
            }
        ),
        types.Tool(
            name="assign_agent_to_group",
            description="Assign an agent to a group.",
            inputSchema={
                "type": "object",
                "properties": {
                    "user_id": {
                        "type": "integer",
                        "description": "Agent user ID"
                    },
                    "group_id": {
                        "type": "integer",
                        "description": "Group ID"
                    },
                    "is_default": {
                        "type": "boolean",
                        "description": "Whether this is the agent's default group (default: false)"
                    }
                },
                "required": ["user_id", "group_id"]
            }
        ),
        types.Tool(
            name="remove_agent_from_group",
            description="Remove an agent from a group.",
            inputSchema={
                "type": "object",
                "properties": {
                    "user_id": {
                        "type": "integer",
                        "description": "Agent user ID"
                    },
                    "group_id": {
                        "type": "integer",
                        "description": "Group ID"
                    }
                },
                "required": ["user_id", "group_id"]
            }
        ),

        # CUSTOM FIELDS AND TICKET FIELDS
        types.Tool(
            name="get_ticket_fields",
            description="Get all ticket fields including custom fields with their configurations.",
            inputSchema={"type": "object", "properties": {}}
        ),
        types.Tool(
            name="get_user_fields",
            description="Get all user fields including custom fields.",
            inputSchema={"type": "object", "properties": {}}
        ),
        types.Tool(
            name="get_organization_fields",
            description="Get all organization fields including custom fields.",
            inputSchema={"type": "object", "properties": {}}
        ),

        # ADVANCED SEARCH AND FILTERING
        types.Tool(
            name="advanced_search",
            description="Advanced search across different object types.",
            inputSchema={
                "type": "object",
                "properties": {
                    "search_type": {
                        "type": "string",
                        "description": "Type to search (tickets, users, organizations)"
                    },
                    "query": {
                        "type": "string",
                        "description": "Search query string"
                    },
                    "sort_by": {
                        "type": "string",
                        "description": "Field to sort by"
                    },
                    "sort_order": {
                        "type": "string",
                        "description": "Sort order (asc, desc, default: desc)"
                    }
                },
                "required": ["search_type", "query"]
            }
        ),
        types.Tool(
            name="export_search_results",
            description="Export search results for bulk processing.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query"
                    },
                    "object_type": {
                        "type": "string",
                        "description": "Type of objects to export (default: ticket)"
                    }
                },
                "required": ["query"]
            }
        ),

        # AUTOMATION AND BUSINESS RULES
        types.Tool(
            name="get_automations",
            description="Get all automations with their conditions and actions.",
            inputSchema={"type": "object", "properties": {}}
        ),
        types.Tool(
            name="get_triggers",
            description="Get all triggers with their conditions and actions.",
            inputSchema={"type": "object", "properties": {}}
        ),
        types.Tool(
            name="get_sla_policies",
            description="Get all SLA policies and their configurations.",
            inputSchema={"type": "object", "properties": {}}
        ),

        # KNOWLEDGE BASE INTEGRATION
        types.Tool(
            name="check_help_center_status",
            description="Check if Help Center is available and accessible (diagnostic tool).",
            inputSchema={"type": "object", "properties": {}}
        ),
        types.Tool(
            name="search_help_center",
            description="Search help center articles.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query"
                    },
                    "locale": {
                        "type": "string",
                        "description": "Language locale (default: en-us)"
                    },
                    "category_id": {
                        "type": "integer",
                        "description": "Optional category filter"
                    }
                },
                "required": ["query"]
            }
        ),
        types.Tool(
            name="get_help_center_articles",
            description="Get help center articles.",
            inputSchema={
                "type": "object",
                "properties": {
                    "section_id": {
                        "type": "integer",
                        "description": "Filter by section"
                    },
                    "category_id": {
                        "type": "integer",
                        "description": "Filter by category"
                    }
                }
            }
        ),

        # TICKET EVENTS AND AUDIT LOG
        types.Tool(
            name="get_ticket_audits",
            description="Get recent audit events for a ticket with data limits to prevent conversation overflow.",
            inputSchema={
                "type": "object",
                "properties": {
                    "ticket_id": {
                        "type": "integer",
                        "description": "Ticket ID to get audits for"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of audit records to return (default: 20)"
                    },
                    "include_metadata": {
                        "type": "boolean",
                        "description": "Whether to include metadata (can be large, default: false)"
                    }
                },
                "required": ["ticket_id"]
            }
        ),
        types.Tool(
            name="get_ticket_events",
            description="Get all events for a ticket including system events.",
            inputSchema={
                "type": "object",
                "properties": {
                    "ticket_id": {
                        "type": "integer",
                        "description": "Ticket ID to get events for"
                    }
                },
                "required": ["ticket_id"]
            }
        ),

        # COLLABORATION FEATURES
        types.Tool(
            name="add_ticket_collaborators",
            description="Add collaborators (CC) to a ticket.",
            inputSchema={
                "type": "object",
                "properties": {
                    "ticket_id": {
                        "type": "integer",
                        "description": "The ticket ID"
                    },
                    "email_addresses": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of email addresses to add as collaborators"
                    }
                },
                "required": ["ticket_id", "email_addresses"]
            }
        ),
        types.Tool(
            name="get_ticket_collaborators",
            description="Get all collaborators on a ticket.",
            inputSchema={
                "type": "object",
                "properties": {
                    "ticket_id": {
                        "type": "integer",
                        "description": "Ticket ID to get collaborators for"
                    }
                },
                "required": ["ticket_id"]
            }
        ),
        types.Tool(
            name="remove_ticket_collaborators",
            description="Remove collaborators from a ticket.",
            inputSchema={
                "type": "object",
                "properties": {
                    "ticket_id": {
                        "type": "integer",
                        "description": "The ticket ID"
                    },
                    "user_ids": {
                        "type": "array",
                        "items": {"type": "integer"},
                        "description": "List of user IDs to remove as collaborators"
                    }
                },
                "required": ["ticket_id", "user_ids"]
            }
        ),
        types.Tool(
            name="get_data_limits_info",
            description="Get information about data limits and how to access full data when needed. Explains options for getting complete, untruncated data.",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            }
        ),

        # ADVANCED REPORTING
        types.Tool(
            name="get_incremental_tickets",
            description="Get tickets incrementally for data synchronization.",
            inputSchema={
                "type": "object",
                "properties": {
                    "start_time": {
                        "type": "integer",
                        "description": "Unix timestamp to start from"
                    },
                    "cursor": {
                        "type": "string",
                        "description": "Pagination cursor for next page"
                    }
                },
                "required": ["start_time"]
            }
        ),
        types.Tool(
            name="get_ticket_metrics_detailed",
            description="Get detailed metrics for a specific ticket including SLA data.",
            inputSchema={
                "type": "object",
                "properties": {
                    "ticket_id": {
                        "type": "integer",
                        "description": "Ticket ID to get detailed metrics for"
                    }
                },
                "required": ["ticket_id"]
            }
        ),
        types.Tool(
            name="generate_agent_activity_report",
            description="Generate detailed activity report for an agent.",
            inputSchema={
                "type": "object",
                "properties": {
                    "agent_id": {
                        "type": "integer",
                        "description": "Agent user ID"
                    },
                    "start_date": {
                        "type": "string",
                        "description": "Start date (YYYY-MM-DD)"
                    },
                    "end_date": {
                        "type": "string",
                        "description": "End date (YYYY-MM-DD)"
                    }
                },
                "required": ["agent_id", "start_date", "end_date"]
            }
        ),

        # FULL DATA ACCESS TOOLS (WARNING: May return large responses)
        types.Tool(
            name="get_ticket_comments_full",
            description="Get full, untruncated comments for a ticket. WARNING: May return large amounts of data - use only when you need complete comment content.",
            inputSchema={
                "type": "object",
                "properties": {
                    "ticket_id": {
                        "type": "integer",
                        "description": "The ID of the ticket to get full comments for"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of comments to return (optional, returns all if not specified)"
                    }
                },
                "required": ["ticket_id"]
            }
        ),
        types.Tool(
            name="get_ticket_audits_full",
            description="Get full, untruncated audit history for a ticket. WARNING: May return large amounts of data - use only when you need complete audit details.",
            inputSchema={
                "type": "object",
                "properties": {
                    "ticket_id": {
                        "type": "integer",
                        "description": "Ticket ID to get full audits for"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of audit records to return (optional, returns all if not specified)"
                    }
                },
                "required": ["ticket_id"]
            }
        ),
        types.Tool(
            name="search_tickets_full",
            description="Search for tickets with full, untruncated data including complete descriptions. WARNING: May return large amounts of data - use only when you need complete ticket details.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query (e.g., 'status:open', 'priority:urgent')"
                    },
                    "sort_by": {
                        "type": "string",
                        "description": "Field to sort by (created_at, updated_at, priority, status)",
                        "default": "created_at"
                    },
                    "sort_order": {
                        "type": "string",
                        "description": "Sort order (asc or desc)",
                        "default": "desc"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of tickets to return (default: 50)",
                        "default": 50
                    }
                },
                "required": ["query"]
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
            
            # Support data limit parameters
            limit = arguments.get("limit", 10)
            include_body = arguments.get("include_body", True)
            max_body_length = arguments.get("max_body_length", 300)
            
            comments = zendesk_client.get_ticket_comments(
                ticket_id=arguments["ticket_id"],
                limit=limit,
                include_body=include_body,
                max_body_length=max_body_length
            )
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
            
            result = zendesk_client.search_tickets(
                query=arguments["query"],
                sort_by=arguments.get("sort_by", "created_at"),
                sort_order=arguments.get("sort_order", "desc"),
                compact=arguments.get("compact", True),
                limit=arguments.get("limit"),
                summarize=arguments.get("summarize", False)
            )
            
            # Use response size limiting
            response_text = zendesk_client._limit_response_size(result)
            return [types.TextContent(type="text", text=response_text)]

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
            summarize = arguments.get("summarize", True) if arguments else True
            
            result = zendesk_client.get_ticket_metrics(
                ticket_id=ticket_id,
                summarize=summarize
            )
            
            response_text = zendesk_client._limit_response_size(result)
            return [types.TextContent(type="text", text=response_text)]

        elif name == "get_user_tickets":
            if not arguments or "user_id" not in arguments:
                raise ValueError("Missing required argument: user_id")
            
            result = zendesk_client.get_user_tickets(
                user_id=arguments["user_id"],
                ticket_type=arguments.get("ticket_type", "requested"),
                compact=arguments.get("compact", True),
                limit=arguments.get("limit"),
                summarize=arguments.get("summarize", False)
            )
            
            response_text = zendesk_client._limit_response_size(result)
            return [types.TextContent(type="text", text=response_text)]

        elif name == "get_organization_tickets":
            if not arguments or "organization_id" not in arguments:
                raise ValueError("Missing required argument: organization_id")
            
            result = zendesk_client.get_organization_tickets(
                org_id=arguments["organization_id"],
                compact=arguments.get("compact", True),
                limit=arguments.get("limit"),
                summarize=arguments.get("summarize", False)
            )
            
            response_text = zendesk_client._limit_response_size(result)
            return [types.TextContent(type="text", text=response_text)]

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

        elif name == "get_agent_performance":
            days = arguments.get("days", 7) if arguments else 7
            performance_data = zendesk_client.get_agent_performance(days)
            
            # Use summarization for better response management
            summary = zendesk_client.summarize_agent_performance(performance_data)
            response_text = zendesk_client._limit_response_size(summary)
            return [types.TextContent(type="text", text=response_text)]

        elif name == "get_user_by_id":
            if not arguments or "user_id" not in arguments:
                raise ValueError("Missing required argument: user_id")
            user_id = arguments["user_id"]
            user_info = zendesk_client.get_user_by_id(user_id)
            return [types.TextContent(
                type="text",
                text=json.dumps(user_info, indent=2)
            )]

        elif name == "get_agent_performance_metrics":
            agent_id = arguments.get("agent_id") if arguments else None
            start_date = arguments.get("start_date") if arguments else None
            end_date = arguments.get("end_date") if arguments else None
            include_satisfaction = arguments.get("include_satisfaction", True) if arguments else True
            summarize = arguments.get("summarize", True) if arguments else True
            
            result = zendesk_client.get_agent_performance_metrics(
                agent_id=agent_id,
                start_date=start_date,
                end_date=end_date,
                include_satisfaction=include_satisfaction,
                summarize=summarize
            )
            
            response_text = zendesk_client._limit_response_size(result)
            return [types.TextContent(type="text", text=response_text)]

        elif name == "get_team_performance_dashboard":
            team_id = arguments.get("team_id") if arguments else None
            period = arguments.get("period", "week") if arguments else "week"
            summarize = arguments.get("summarize", True) if arguments else True
            
            result = zendesk_client.get_team_performance_dashboard(
                team_id=team_id,
                period=period,
                summarize=summarize
            )
            
            response_text = zendesk_client._limit_response_size(result)
            return [types.TextContent(type="text", text=response_text)]

        elif name == "generate_agent_scorecard":
            if not arguments or "agent_id" not in arguments:
                raise ValueError("Missing required argument: agent_id")
            agent_id = arguments["agent_id"]
            period = arguments.get("period", "month") if arguments else "month"
            
            scorecard = zendesk_client.generate_agent_scorecard(
                agent_id=agent_id,
                period=period
            )
            return [types.TextContent(
                type="text",
                text=json.dumps(scorecard, indent=2)
            )]

        elif name == "get_agent_workload_analysis":
            include_pending = arguments.get("include_pending", True) if arguments else True
            include_open = arguments.get("include_open", True) if arguments else True
            
            analysis = zendesk_client.get_agent_workload_analysis(
                include_pending=include_pending,
                include_open=include_open
            )
            
            # Use summarization for better response management
            summary = zendesk_client.summarize_workload(analysis)
            response_text = zendesk_client._limit_response_size(summary)
            return [types.TextContent(type="text", text=response_text)]

        elif name == "suggest_ticket_reassignment":
            criteria = arguments.get("criteria", "workload_balance") if arguments else "workload_balance"
            
            suggestions = zendesk_client.suggest_ticket_reassignment(criteria=criteria)
            return [types.TextContent(
                type="text",
                text=json.dumps(suggestions, indent=2)
            )]

        elif name == "get_sla_compliance_report":
            start_date = arguments.get("start_date") if arguments else None
            end_date = arguments.get("end_date") if arguments else None
            agent_id = arguments.get("agent_id") if arguments else None
            
            report = zendesk_client.get_sla_compliance_report(
                start_date=start_date,
                end_date=end_date,
                agent_id=agent_id
            )
            return [types.TextContent(
                type="text",
                text=json.dumps(report, indent=2)
            )]

        elif name == "get_at_risk_tickets":
            time_horizon = arguments.get("time_horizon", 24) if arguments else 24
            
            at_risk_tickets = zendesk_client.get_at_risk_tickets(time_horizon=time_horizon)
            return [types.TextContent(
                type="text",
                text=json.dumps(at_risk_tickets, indent=2)
            )]

        elif name == "bulk_update_tickets":
            if not arguments or "ticket_ids" not in arguments or "updates" not in arguments:
                raise ValueError("Missing required arguments: ticket_ids and updates")
            ticket_ids = arguments["ticket_ids"]
            updates = arguments["updates"]
            reason = arguments.get("reason")
            
            results = zendesk_client.bulk_update_tickets(
                ticket_ids=ticket_ids,
                updates=updates,
                reason=reason
            )
            return [types.TextContent(
                type="text",
                text=json.dumps(results, indent=2)
            )]

        elif name == "auto_categorize_tickets":
            ticket_ids = arguments.get("ticket_ids") if arguments else None
            use_ml = arguments.get("use_ml", True) if arguments else True
            
            categorized_tickets = zendesk_client.auto_categorize_tickets(
                ticket_ids=ticket_ids,
                use_ml=use_ml
            )
            return [types.TextContent(
                type="text",
                text=json.dumps(categorized_tickets, indent=2)
            )]

        elif name == "escalate_ticket":
            if not arguments or "ticket_id" not in arguments or "escalation_level" not in arguments or "reason" not in arguments:
                raise ValueError("Missing required arguments: ticket_id, escalation_level, and reason")
            ticket_id = arguments["ticket_id"]
            escalation_level = arguments["escalation_level"]
            reason = arguments["reason"]
            notify_stakeholders = arguments.get("notify_stakeholders", True) if arguments else True
            
            escalated_ticket = zendesk_client.escalate_ticket(
                ticket_id=ticket_id,
                escalation_level=escalation_level,
                reason=reason,
                notify_stakeholders=notify_stakeholders
            )
            return [types.TextContent(
                type="text",
                text=json.dumps(escalated_ticket, indent=2)
            )]

        elif name == "get_macros":
            macros = zendesk_client.get_macros()
            return [types.TextContent(
                type="text",
                text=json.dumps(macros, indent=2)
            )]

        elif name == "apply_macro_to_ticket":
            if not arguments or "ticket_id" not in arguments or "macro_id" not in arguments:
                raise ValueError("Missing required arguments: ticket_id and macro_id")
            ticket_id = arguments["ticket_id"]
            macro_id = arguments["macro_id"]
            result = zendesk_client.apply_macro_to_ticket(ticket_id=ticket_id, macro_id=macro_id)
            return [types.TextContent(
                type="text",
                text=json.dumps(result, indent=2)
            )]

        elif name == "get_ticket_forms":
            forms = zendesk_client.get_ticket_forms()
            return [types.TextContent(
                type="text",
                text=json.dumps(forms, indent=2)
            )]

        elif name == "merge_tickets":
            if not arguments or "source_ticket_ids" not in arguments or "target_ticket_id" not in arguments:
                raise ValueError("Missing required arguments: source_ticket_ids and target_ticket_id")
            source_ticket_ids = arguments["source_ticket_ids"]
            target_ticket_id = arguments["target_ticket_id"]
            result = zendesk_client.merge_tickets(source_ticket_ids=source_ticket_ids, target_ticket_id=target_ticket_id)
            return [types.TextContent(
                type="text",
                text=json.dumps(result, indent=2)
            )]

        elif name == "clone_ticket":
            if not arguments or "ticket_id" not in arguments:
                raise ValueError("Missing required argument: ticket_id")
            ticket_id = arguments["ticket_id"]
            include_comments = arguments.get("include_comments", False) if arguments else False
            result = zendesk_client.clone_ticket(ticket_id=ticket_id, include_comments=include_comments)
            return [types.TextContent(
                type="text",
                text=json.dumps(result, indent=2)
            )]

        elif name == "add_ticket_tags":
            if not arguments or "ticket_id" not in arguments or "tags" not in arguments:
                raise ValueError("Missing required arguments: ticket_id and tags")
            ticket_id = arguments["ticket_id"]
            tags = arguments["tags"]
            result = zendesk_client.add_ticket_tags(ticket_id=ticket_id, tags=tags)
            return [types.TextContent(
                type="text",
                text=json.dumps(result, indent=2)
            )]

        elif name == "remove_ticket_tags":
            if not arguments or "ticket_id" not in arguments or "tags" not in arguments:
                raise ValueError("Missing required arguments: ticket_id and tags")
            ticket_id = arguments["ticket_id"]
            tags = arguments["tags"]
            result = zendesk_client.remove_ticket_tags(ticket_id=ticket_id, tags=tags)
            return [types.TextContent(
                type="text",
                text=json.dumps(result, indent=2)
            )]

        elif name == "get_ticket_related_tickets":
            if not arguments or "ticket_id" not in arguments:
                raise ValueError("Missing required argument: ticket_id")
            ticket_id = arguments["ticket_id"]
            related_tickets = zendesk_client.get_ticket_related_tickets(ticket_id=ticket_id)
            return [types.TextContent(
                type="text",
                text=json.dumps(related_tickets, indent=2)
            )]

        elif name == "get_organizations":
            external_id = arguments.get("external_id") if arguments else None
            name = arguments.get("name") if arguments else None
            compact = arguments.get("compact", True) if arguments else True
            limit = arguments.get("limit") if arguments else None
            
            result = zendesk_client.get_organizations(
                external_id=external_id, 
                name=name,
                compact=compact,
                limit=limit
            )
            
            response_text = zendesk_client._limit_response_size(result)
            return [types.TextContent(type="text", text=response_text)]

        elif name == "get_organization_details":
            if not arguments or "org_id" not in arguments:
                raise ValueError("Missing required argument: org_id")
            org_id = arguments["org_id"]
            org_details = zendesk_client.get_organization_details(org_id=org_id)
            return [types.TextContent(
                type="text",
                text=json.dumps(org_details, indent=2)
            )]

        elif name == "update_organization":
            if not arguments or "org_id" not in arguments:
                raise ValueError("Missing required argument: org_id")
            org_id = arguments["org_id"]
            name = arguments.get("name") if arguments else None
            details = arguments.get("details") if arguments else None
            notes = arguments.get("notes") if arguments else None
            result = zendesk_client.update_organization(org_id=org_id, name=name, details=details, notes=notes)
            return [types.TextContent(
                type="text",
                text=json.dumps(result, indent=2)
            )]

        elif name == "get_organization_users":
            if not arguments or "org_id" not in arguments:
                raise ValueError("Missing required argument: org_id")
            org_id = arguments["org_id"]
            users = zendesk_client.get_organization_users(org_id=org_id)
            return [types.TextContent(
                type="text",
                text=json.dumps(users, indent=2)
            )]

        elif name == "create_user":
            if not arguments or "name" not in arguments or "email" not in arguments:
                raise ValueError("Missing required arguments: name and email")
            name = arguments["name"]
            email = arguments["email"]
            role = arguments.get("role", "end-user") if arguments else "end-user"
            organization_id = arguments.get("organization_id") if arguments else None
            result = zendesk_client.create_user(name=name, email=email, role=role, organization_id=organization_id)
            return [types.TextContent(
                type="text",
                text=json.dumps(result, indent=2)
            )]

        elif name == "update_user":
            if not arguments or "user_id" not in arguments:
                raise ValueError("Missing required argument: user_id")
            user_id = arguments["user_id"]
            name = arguments.get("name") if arguments else None
            email = arguments.get("email") if arguments else None
            role = arguments.get("role") if arguments else None
            result = zendesk_client.update_user(user_id=user_id, name=name, email=email, role=role)
            return [types.TextContent(
                type="text",
                text=json.dumps(result, indent=2)
            )]

        elif name == "suspend_user":
            if not arguments or "user_id" not in arguments:
                raise ValueError("Missing required argument: user_id")
            user_id = arguments["user_id"]
            reason = arguments.get("reason") if arguments else None
            result = zendesk_client.suspend_user(user_id=user_id, reason=reason)
            return [types.TextContent(
                type="text",
                text=json.dumps(result, indent=2)
            )]

        elif name == "search_users":
            query = arguments.get("query") if arguments else None
            role = arguments.get("role") if arguments else None
            organization_id = arguments.get("organization_id") if arguments else None
            users = zendesk_client.search_users(query=query, role=role, organization_id=organization_id)
            return [types.TextContent(
                type="text",
                text=json.dumps(users, indent=2)
            )]

        elif name == "get_user_identities":
            if not arguments or "user_id" not in arguments:
                raise ValueError("Missing required argument: user_id")
            user_id = arguments["user_id"]
            identities = zendesk_client.get_user_identities(user_id=user_id)
            return [types.TextContent(
                type="text",
                text=json.dumps(identities, indent=2)
            )]

        elif name == "get_groups":
            groups = zendesk_client.get_groups()
            return [types.TextContent(
                type="text",
                text=json.dumps(groups, indent=2)
            )]

        elif name == "get_group_memberships":
            group_id = arguments.get("group_id") if arguments else None
            user_id = arguments.get("user_id") if arguments else None
            memberships = zendesk_client.get_group_memberships(group_id=group_id, user_id=user_id)
            return [types.TextContent(
                type="text",
                text=json.dumps(memberships, indent=2)
            )]

        elif name == "assign_agent_to_group":
            if not arguments or "user_id" not in arguments or "group_id" not in arguments:
                raise ValueError("Missing required arguments: user_id and group_id")
            user_id = arguments["user_id"]
            group_id = arguments["group_id"]
            is_default = arguments.get("is_default", False) if arguments else False
            result = zendesk_client.assign_agent_to_group(user_id=user_id, group_id=group_id, is_default=is_default)
            return [types.TextContent(
                type="text",
                text=json.dumps(result, indent=2)
            )]

        elif name == "remove_agent_from_group":
            if not arguments or "user_id" not in arguments or "group_id" not in arguments:
                raise ValueError("Missing required arguments: user_id and group_id")
            user_id = arguments["user_id"]
            group_id = arguments["group_id"]
            result = zendesk_client.remove_agent_from_group(user_id=user_id, group_id=group_id)
            return [types.TextContent(
                type="text",
                text=json.dumps(result, indent=2)
            )]

        elif name == "get_ticket_fields":
            fields = zendesk_client.get_ticket_fields()
            return [types.TextContent(
                type="text",
                text=json.dumps(fields, indent=2)
            )]

        elif name == "get_user_fields":
            fields = zendesk_client.get_user_fields()
            return [types.TextContent(
                type="text",
                text=json.dumps(fields, indent=2)
            )]

        elif name == "get_organization_fields":
            fields = zendesk_client.get_organization_fields()
            return [types.TextContent(
                type="text",
                text=json.dumps(fields, indent=2)
            )]

        elif name == "advanced_search":
            search_type = arguments.get("search_type") if arguments else None
            query = arguments.get("query") if arguments else None
            sort_by = arguments.get("sort_by") if arguments else None
            sort_order = arguments.get("sort_order") if arguments else None
            results = zendesk_client.advanced_search(search_type=search_type, query=query, sort_by=sort_by, sort_order=sort_order)
            return [types.TextContent(
                type="text",
                text=json.dumps(results, indent=2)
            )]

        elif name == "export_search_results":
            query = arguments.get("query") if arguments else None
            object_type = arguments.get("object_type", "ticket") if arguments else "ticket"
            results = zendesk_client.export_search_results(query=query, object_type=object_type)
            return [types.TextContent(
                type="text",
                text=json.dumps(results, indent=2)
            )]

        elif name == "get_automations":
            automations = zendesk_client.get_automations()
            return [types.TextContent(
                type="text",
                text=json.dumps(automations, indent=2)
            )]

        elif name == "get_triggers":
            triggers = zendesk_client.get_triggers()
            return [types.TextContent(
                type="text",
                text=json.dumps(triggers, indent=2)
            )]

        elif name == "get_sla_policies":
            sla_policies = zendesk_client.get_sla_policies()
            return [types.TextContent(
                type="text",
                text=json.dumps(sla_policies, indent=2)
            )]

        elif name == "check_help_center_status":
            status = zendesk_client.check_help_center_status()
            return [types.TextContent(
                type="text",
                text=json.dumps(status, indent=2)
            )]

        elif name == "search_help_center":
            query = arguments.get("query") if arguments else None
            locale = arguments.get("locale", "en-us") if arguments else "en-us"
            category_id = arguments.get("category_id") if arguments else None
            articles = zendesk_client.search_help_center(query=query, locale=locale, category_id=category_id)
            return [types.TextContent(
                type="text",
                text=json.dumps(articles, indent=2)
            )]

        elif name == "get_help_center_articles":
            section_id = arguments.get("section_id") if arguments else None
            category_id = arguments.get("category_id") if arguments else None
            articles = zendesk_client.get_help_center_articles(section_id=section_id, category_id=category_id)
            return [types.TextContent(
                type="text",
                text=json.dumps(articles, indent=2)
            )]

        elif name == "get_ticket_audits":
            if not arguments or "ticket_id" not in arguments:
                raise ValueError("Missing required argument: ticket_id")
            ticket_id = arguments["ticket_id"]
            
            # Support data limit parameters
            limit = arguments.get("limit", 20)
            include_metadata = arguments.get("include_metadata", False)
            
            audits = zendesk_client.get_ticket_audits(
                ticket_id=ticket_id,
                limit=limit,
                include_metadata=include_metadata
            )
            return [types.TextContent(
                type="text",
                text=json.dumps(audits, indent=2)
            )]

        elif name == "get_ticket_events":
            if not arguments or "ticket_id" not in arguments:
                raise ValueError("Missing required argument: ticket_id")
            ticket_id = arguments["ticket_id"]
            events = zendesk_client.get_ticket_events(ticket_id=ticket_id)
            return [types.TextContent(
                type="text",
                text=json.dumps(events, indent=2)
            )]

        elif name == "add_ticket_collaborators":
            if not arguments or "ticket_id" not in arguments or "email_addresses" not in arguments:
                raise ValueError("Missing required arguments: ticket_id and email_addresses")
            ticket_id = arguments["ticket_id"]
            email_addresses = arguments["email_addresses"]
            result = zendesk_client.add_ticket_collaborators(ticket_id=ticket_id, email_addresses=email_addresses)
            return [types.TextContent(
                type="text",
                text=json.dumps(result, indent=2)
            )]

        elif name == "get_ticket_collaborators":
            if not arguments or "ticket_id" not in arguments:
                raise ValueError("Missing required argument: ticket_id")
            ticket_id = arguments["ticket_id"]
            collaborators = zendesk_client.get_ticket_collaborators(ticket_id=ticket_id)
            return [types.TextContent(
                type="text",
                text=json.dumps(collaborators, indent=2)
            )]

        elif name == "remove_ticket_collaborators":
            if not arguments or "ticket_id" not in arguments or "user_ids" not in arguments:
                raise ValueError("Missing required arguments: ticket_id and user_ids")
            ticket_id = arguments["ticket_id"]
            user_ids = arguments["user_ids"]
            result = zendesk_client.remove_ticket_collaborators(ticket_id=ticket_id, user_ids=user_ids)
            return [types.TextContent(
                type="text",
                text=json.dumps(result, indent=2)
            )]

        elif name == "get_incremental_tickets":
            start_time = arguments.get("start_time") if arguments else None
            cursor = arguments.get("cursor") if arguments else None
            tickets = zendesk_client.get_incremental_tickets(start_time=start_time, cursor=cursor)
            return [types.TextContent(
                type="text",
                text=json.dumps(tickets, indent=2)
            )]

        elif name == "get_ticket_metrics_detailed":
            if not arguments or "ticket_id" not in arguments:
                raise ValueError("Missing required argument: ticket_id")
            ticket_id = arguments["ticket_id"]
            metrics = zendesk_client.get_ticket_metrics_detailed(ticket_id=ticket_id)
            return [types.TextContent(
                type="text",
                text=json.dumps(metrics, indent=2)
            )]

        elif name == "generate_agent_activity_report":
            if not arguments or "agent_id" not in arguments or "start_date" not in arguments or "end_date" not in arguments:
                raise ValueError("Missing required arguments: agent_id, start_date, and end_date")
            agent_id = arguments["agent_id"]
            start_date = arguments["start_date"]
            end_date = arguments["end_date"]
            report = zendesk_client.generate_agent_activity_report(agent_id=agent_id, start_date=start_date, end_date=end_date)
            return [types.TextContent(
                type="text",
                text=json.dumps(report, indent=2)
            )]

        elif name == "get_ticket_comments_full":
            ticket_id = arguments.get("ticket_id") if arguments else None
            limit = arguments.get("limit") if arguments else None
            if not ticket_id:
                raise ValueError("Missing required argument: ticket_id")
            comments = zendesk_client.get_ticket_comments_full(ticket_id=ticket_id, limit=limit)
            return [types.TextContent(
                type="text",
                text=json.dumps(comments, indent=2)
            )]

        elif name == "get_ticket_audits_full":
            ticket_id = arguments.get("ticket_id") if arguments else None
            limit = arguments.get("limit") if arguments else None
            if not ticket_id:
                raise ValueError("Missing required argument: ticket_id")
            audits = zendesk_client.get_ticket_audits_full(ticket_id=ticket_id, limit=limit)
            return [types.TextContent(
                type="text",
                text=json.dumps(audits, indent=2)
            )]

        elif name == "search_tickets_full":
            query = arguments.get("query") if arguments else None
            sort_by = arguments.get("sort_by", "created_at") if arguments else "created_at"
            sort_order = arguments.get("sort_order", "desc") if arguments else "desc"
            limit = arguments.get("limit", 50) if arguments else 50
            if not query:
                raise ValueError("Missing required argument: query")
            tickets = zendesk_client.search_tickets_full(query=query, sort_by=sort_by, sort_order=sort_order, limit=limit)
            return [types.TextContent(
                type="text",
                text=json.dumps(tickets, indent=2)
            )]

        elif name == "get_data_limits_info":
            info = zendesk_client.get_data_limits_info()
            return [types.TextContent(
                type="text",
                text=json.dumps(info, indent=2)
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