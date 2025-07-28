# Zendesk MCP Server

A Model Context Protocol (MCP) server that provides comprehensive access to Zendesk Support APIs, including advanced ticket search, analytics, and customer satisfaction data.

## Features

### Core Ticket Management
- **get_ticket**: Retrieve detailed ticket information by ID
- **get_ticket_comments**: Get all comments for a specific ticket
- **create_ticket_comment**: Add new comments to existing tickets

### Advanced Search & Discovery
- **search_tickets**: Powerful ticket search using Zendesk's query syntax
  - Search by status: `status:open`, `status:pending`
  - Search by priority: `priority:high`, `priority:urgent`
  - Search by assignee: `assignee:me`, `assignee:john@company.com`
  - Search by date ranges: `created>2024-01-01`, `updated<2024-12-31`
  - Search by custom fields and tags
  - Combine multiple criteria: `status:open priority:high created>7days`

### Analytics & Statistics
- **get_ticket_counts**: Get comprehensive ticket counts by status and priority
- **get_ticket_metrics**: Analyze ticket performance metrics
  - Individual ticket metrics (response times, reopens, replies)
  - Aggregate metrics across recent tickets
  - Resolution time analysis
- **get_satisfaction_ratings**: Customer satisfaction (CSAT) data with score distribution

### User & Organization Analysis
- **get_user_tickets**: Get tickets for specific users
  - Requested tickets (customer tickets)
  - Assigned tickets (agent workload)
  - CC'd tickets (collaborative tickets)
- **get_organization_tickets**: Analyze tickets by organization/company

### Knowledge Base Integration
- Access to Help Center articles and sections
- Cached knowledge base for fast retrieval

### Analytics and Performance Tools

- **`get_ticket_counts`**: Get overall ticket statistics
  ```
  Request: {}
  ```

- **`get_ticket_metrics`**: Get performance metrics for specific ticket or aggregate data
  ```
  Request: {"ticket_id": 12345}  // Optional
  ```

- **`get_satisfaction_ratings`**: Get customer satisfaction data with score distribution
  ```
  Request: {"limit": 50}  // Optional, default 100
  ```

- **`get_agent_performance`**: Get agent performance metrics optimized for analysis ⭐ **NEW**
  ```
  Request: {"days": 7}  // Optional, default 7, max 90
  ```
  
  Returns minimal data specifically for performance analysis:
  - Top 10 performing agents by tickets solved
  - Agent names and contact information
  - Priority score analysis (urgent=4, high=3, normal=2, low=1)
  - Ticket subjects for context (truncated)
  - Summary statistics
  
  **Perfect for**: "Who is the best performing agent this week?"

### Search and Query Tools

- **`search_tickets`**: Advanced search with Zendesk query syntax
  ```
  Request: {
    "query": "status:open priority:high",
    "sort_by": "created_at",     // Optional: created_at, updated_at, priority, status
    "sort_order": "desc",        // Optional: asc or desc
    "compact": false             // Optional: true for minimal data, better performance
  }
  ```
  
  **Compact Mode** ⭐ **NEW**: Set `"compact": true` to get minimal data without descriptions for performance analysis and to avoid overwhelming responses with large datasets.

### User and Organization Analysis Tools

- **`get_user_tickets`**: Get tickets for a specific user (requested, assigned, or CC'd)
  ```
  Request: {"user_id": 123, "ticket_type": "assigned"}
  ```

- **`get_organization_tickets`**: Get all tickets for an organization
  ```
  Request: {"organization_id": 456}
  ```

- **`get_user_by_id`**: Get detailed user information by ID ⭐ **NEW**
  ```
  Request: {"user_id": 386646129318}
  ```
  
  Returns comprehensive user details:
  - Name, email, role, active status
  - Creation date, last login, timezone
  - Organization association
  - **Perfect for**: Resolving agent IDs to names in performance analysis

## Installation

1. Clone this repository
2. Install dependencies:
   ```bash
   uv sync
   ```
3. Set up environment variables in a `.env` file:
   ```bash
   ZENDESK_SUBDOMAIN=your-subdomain
   ZENDESK_EMAIL=your-email@company.com
   ZENDESK_API_KEY=your-api-key
   ```

## Testing the Installation

You can test that the server is working correctly:

```bash
# Show help information
uv run zendesk --help

# Test the server starts (will wait for MCP input)
uv run zendesk
```

## Configuration

Add to your Claude Desktop configuration (`~/Library/Application Support/Claude/claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "zendesk": {
      "command": "uv",
      "args": [
        "--directory",
        "/ABSOLUTE/PATH/TO/zendesk-mcp-server",
        "run",
        "zendesk"
      ],
      "env": {
        "ZENDESK_SUBDOMAIN": "your-subdomain",
        "ZENDESK_EMAIL": "your-email@company.com",
        "ZENDESK_API_KEY": "your-api-key"
      }
    }
  }
}
```

**Important**: Replace `/ABSOLUTE/PATH/TO/zendesk-mcp-server` with the actual path to your cloned repository.

**Configuration Notes:**
- `ZENDESK_SUBDOMAIN` should be just your subdomain name (e.g., "mycompany"), **not** the full URL
- Your API token needs permissions for tickets, search, and user management
- You can set environment variables system-wide instead of in the config file

Alternatively, you can set environment variables system-wide instead of in the config file.

## Troubleshooting

### Common Issues

1. **SSL/Connection Errors**: 
   - Check that `ZENDESK_SUBDOMAIN` is just the subdomain name, not the full URL
   - Verify your network connection and firewall settings

2. **Authentication Errors**:
   - Verify your `ZENDESK_EMAIL` and `ZENDESK_API_KEY` are correct
   - Ensure your API token is active and not expired

3. **Permission Errors**:
   - Make sure your API token has the necessary permissions:
     - Read tickets
     - Search tickets
     - Read users and organizations
     - Read satisfaction ratings

4. **"Missing arguments" errors**:
   - Restart Claude Desktop after configuration changes
   - Check that the server path in config is correct

5. **"Result exceeds maximum length" errors**:
   - Use more specific search queries to limit results
   - Search returns are limited to 25 tickets to prevent overwhelming Claude
   - Use date ranges, specific statuses, or assignees to narrow results

### Search Best Practices

To get the most useful results without overwhelming the system:

- **Use specific queries**: Instead of `status:open`, try `status:open priority:high`
- **Add date ranges**: `status:open created>7days` for recent tickets
- **Filter by assignee**: `assignee:me status:pending` for your work
- **Combine criteria**: `priority:urgent status:open created>24hours` for urgent recent items

Examples of good queries:
- `status:open priority:high created>3days` - Recent high priority tickets
- `assignee:john@company.com status:pending` - John's pending work  
- `organization:"Important Client" status:open` - Open tickets for key client
- `status:solved created>7days` - Recently solved tickets

### Testing Your Configuration

Before using with Claude Desktop, test your credentials:

```bash
# Set your environment variables
export ZENDESK_SUBDOMAIN=your-subdomain
export ZENDESK_EMAIL=your-email@company.com  
export ZENDESK_API_KEY=your-api-key

# Test the connection
uv run python -c "
from zendesk_mcp_server.zendesk_client import ZendeskClient
import os
client = ZendeskClient(
    subdomain=os.getenv('ZENDESK_SUBDOMAIN'),
    email=os.getenv('ZENDESK_EMAIL'), 
    token=os.getenv('ZENDESK_API_KEY')
)
print('✅ Zendesk connection successful!')
"
```

## Usage Examples

### Search Tickets
```
Search for high priority open tickets:
"Search for tickets with status:open priority:high"

Find tickets assigned to me:
"Search for my assigned tickets"

Find recent urgent tickets:
"Show me urgent tickets created in the last 7 days"
```

### Analytics Queries
```
Get ticket statistics:
"Show me ticket counts by status and priority"

Analyze performance:
"Get ticket metrics for the last week"

Check customer satisfaction:
"Show me recent satisfaction ratings"
```

### User Analysis
```
Check agent workload:
"Show me all tickets assigned to user 12345"

Analyze customer tickets:
"Get all tickets requested by user 67890"

Organization overview:
"Show me all tickets for organization 111"
```

## Search Query Syntax

The `search_tickets` tool supports Zendesk's powerful query syntax:

### Basic Operators
- `status:open` - Tickets with open status
- `priority:high` - High priority tickets
- `type:incident` - Incident type tickets
- `assignee:me` - Tickets assigned to the authenticated user

### Date Searches
- `created>2024-01-01` - Created after date
- `updated<2024-12-31` - Updated before date
- `created>7days` - Created in last 7 days
- `solved<1week` - Solved more than a week ago

### Advanced Searches
- `requester:customer@example.com` - Tickets from specific requester
- `organization:"Acme Corp"` - Tickets from specific organization
- `tags:vip` - Tickets with VIP tag
- `subject:"urgent issue"` - Tickets with specific subject text

### Combining Criteria
```
status:open priority:high created>7days
assignee:me status:pending
organization:"Big Customer" status:open priority:urgent
```

## API Rate Limits

The server automatically handles Zendesk API rate limits. For high-volume usage:
- Ticket counts and metrics are cached for performance
- Search results are limited to reasonable sizes
- Bulk operations are batched appropriately

## Prompts

The server includes helpful prompts for common workflows:

- **analyze-ticket**: Comprehensive ticket analysis including comments and metrics
- **draft-ticket-response**: AI-assisted response drafting using ticket context and knowledge base

## Error Handling

All tools include comprehensive error handling:
- Invalid ticket IDs return clear error messages
- API timeouts are handled gracefully
- Permission errors are reported clearly
- Network issues include retry suggestions

## Development

To extend the server with additional Zendesk APIs:

1. Add new methods to `ZendeskClient` class
2. Register new tools in the `list_tools()` handler
3. Implement tool logic in `handle_call_tool()`
4. Update documentation

## Contributing

1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Submit a pull request

## License

MIT License - see LICENSE file for details.

### Agent Performance Analysis

For questions like "Who is the best performing support agent?":

1. **Use the optimized tool**: `get_agent_performance` instead of large search queries
2. **Follow up with details**: Use `get_user_by_id` to resolve agent names
3. **Adjust time period**: Use `days` parameter (1-90) to focus analysis
4. **Check user permissions**: Ensure API token can access user data

**Example workflow**:
```
"Who is the best performing agent this week?"
→ get_agent_performance (days: 7)
→ get_user_by_id (for top agent ID)
→ Complete analysis with names and contact info
```
