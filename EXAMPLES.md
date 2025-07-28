# Zendesk MCP Server - Usage Examples

This document provides practical examples of how to use the enhanced Zendesk MCP server with Claude Desktop.

## Quick Start Examples

### Basic Ticket Operations

```
"Get ticket details for #12345"
→ Uses get_ticket tool

"Show me all comments on ticket 12345"
→ Uses get_ticket_comments tool

"Add a comment to ticket 12345 saying 'Thanks for the update'"
→ Uses create_ticket_comment tool
```

## Advanced Search Examples

### Status-based Searches
```
"Search for all open tickets"
→ search_tickets with query: "status:open"

"Find all pending tickets assigned to me"
→ search_tickets with query: "status:pending assignee:me"

"Show me solved tickets from the last week"
→ search_tickets with query: "status:solved created>7days"
```

### Priority-based Searches
```
"Find all urgent tickets"
→ search_tickets with query: "priority:urgent"

"Show high and urgent priority tickets that are still open"
→ search_tickets with query: "priority:high OR priority:urgent status:open"

"Find all low priority tickets that have been open for more than 30 days"
→ search_tickets with query: "priority:low status:open created<30days"
```

### Date Range Searches
```
"Show me tickets created this week"
→ search_tickets with query: "created>7days"

"Find tickets updated in the last 24 hours"
→ search_tickets with query: "updated>24hours"

"Show tickets created between January 1st and January 31st, 2024"
→ search_tickets with query: "created>2024-01-01 created<2024-02-01"
```

### Complex Combined Searches
```
"Find urgent open tickets created in the last 3 days"
→ search_tickets with query: "priority:urgent status:open created>3days"

"Show me all tickets from VIP customers that are high priority"
→ search_tickets with query: "tags:vip priority:high"

"Find all incident tickets assigned to the support team"
→ search_tickets with query: "type:incident assignee:support-team@company.com"
```

## Analytics and Statistics

### Ticket Counts and Distribution
```
"Show me ticket statistics"
→ Uses get_ticket_counts tool
→ Returns counts by status and priority

"What's our current ticket volume?"
→ Uses get_ticket_counts tool
→ Shows total tickets and breakdown
```

### Performance Metrics
```
"Show me ticket performance metrics"
→ Uses get_ticket_metrics (without ticket_id)
→ Returns aggregate metrics for recent tickets

"Get metrics for ticket 12345"
→ Uses get_ticket_metrics with ticket_id: 12345
→ Returns specific ticket performance data

"How are we doing with response times?"
→ Uses get_ticket_metrics for aggregate analysis
```

### Customer Satisfaction
```
"Show me recent customer satisfaction ratings"
→ Uses get_satisfaction_ratings tool
→ Returns CSAT scores with distribution

"What's our customer satisfaction trend?"
→ Uses get_satisfaction_ratings with analysis
→ Includes score breakdown and insights
```

## User and Organization Analysis

### Agent Workload Analysis
```
"Show me all tickets assigned to user 456"
→ Uses get_user_tickets with user_id: 456, ticket_type: "assigned"

"What tickets has user 789 requested?"
→ Uses get_user_tickets with user_id: 789, ticket_type: "requested"

"Show me tickets where user 123 is CC'd"
→ Uses get_user_tickets with user_id: 123, ticket_type: "ccd"
```

### Organization Insights
```
"Show me all tickets for organization 555"
→ Uses get_organization_tickets with organization_id: 555

"What's the ticket volume for our biggest client?"
→ Uses get_organization_tickets for analysis
```

## Guided Prompts

### Analytics Dashboard
```
"Create an analytics dashboard"
→ Uses analytics-dashboard prompt
→ Automatically gathers:
  - Ticket counts by status/priority
  - Performance metrics
  - Satisfaction ratings
  - Key insights and recommendations
```

### Smart Ticket Search
```
"Search for high priority customer issues from this week"
→ Uses search-tickets prompt with search_criteria
→ AI translates to: "priority:high created>7days"
→ Provides guided search with results summary
```

### Workload Analysis
```
"Analyze workload for agent user 123"
→ Uses analyze-user-workload prompt
→ Comprehensive analysis including:
  - Assigned tickets by status
  - Priority distribution
  - Collaboration load (CC'd tickets)
  - Workload recommendations
```

### Ticket Analysis
```
"Analyze ticket 12345"
→ Uses analyze-ticket prompt
→ Deep dive analysis including:
  - Ticket details and history
  - Comments timeline
  - Performance metrics
  - Actionable insights
```

## Real-World Scenarios

### Weekly Team Meeting Prep
```
1. "Create an analytics dashboard" - Overall metrics
2. "Show me urgent tickets from this week" - Priority issues
3. "What's our customer satisfaction this week?" - CSAT check
4. "Analyze workload for each team member" - Resource planning
```

### Customer Escalation Investigation
```
1. "Search for all tickets from organization 555"
2. "Show me high priority tickets from the last month"
3. "Get satisfaction ratings for recent tickets"
4. "Analyze the pattern of escalated tickets"
```

### Agent Performance Review
```
1. "Analyze workload for user 123"
2. "Show tickets assigned to user 123"
3. "Get metrics for tickets handled by this agent"
4. "Check satisfaction ratings for their tickets"
```

### Incident Response
```
1. "Search for all incident tickets from today"
2. "Find critical priority tickets that are still open"
3. "Show me tickets with tag 'outage'"
4. "Get metrics to understand impact"
```

## Advanced Query Syntax Reference

### Operators
- `status:open` - Exact status match
- `priority:high` - Exact priority match
- `assignee:me` - Assigned to authenticated user
- `assignee:email@company.com` - Assigned to specific user
- `requester:customer@domain.com` - Requested by specific user
- `organization:"Company Name"` - From specific organization
- `type:incident` - Specific ticket type
- `tags:vip` - Has specific tag

### Date Operators
- `created>2024-01-01` - Created after date
- `created<2024-01-01` - Created before date
- `updated>7days` - Updated in last 7 days
- `solved<1week` - Solved more than a week ago

### Logical Operators
- `AND` - Both conditions (default)
- `OR` - Either condition
- `NOT` - Exclude condition
- Parentheses for grouping: `(status:open OR status:pending) AND priority:high`

### Text Search
- `subject:"exact phrase"` - Exact phrase in subject
- `description:keyword` - Keyword in description
- `comment:text` - Text in comments

## Tips for Effective Usage

1. **Start Broad, Then Narrow**: Begin with general searches and refine based on results
2. **Use Date Ranges**: Always consider time boundaries for relevant results
3. **Combine Tools**: Use search to find tickets, then analyze specific ones
4. **Monitor Trends**: Regular analytics help identify patterns
5. **Leverage Prompts**: Use guided prompts for complex analysis workflows

## Troubleshooting

### Common Issues
- **No results**: Check query syntax and date ranges
- **Too many results**: Add more specific criteria
- **Permission errors**: Ensure proper Zendesk API access
- **Rate limits**: Space out large queries

### Best Practices
- Use specific date ranges for performance
- Combine multiple tools for comprehensive analysis
- Regular analytics reviews for proactive management
- Document frequent search patterns for team use 