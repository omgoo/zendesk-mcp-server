# Zendesk MCP Server

A comprehensive Model Context Protocol (MCP) server that provides extensive Zendesk integration capabilities for Claude Desktop and other MCP-compatible clients. This server offers over **55 enterprise-grade tools** for complete support team management.

## 🚀 Features

### **Core Zendesk Operations**
- ✅ Retrieve individual tickets and comments
- ✅ Create ticket comments with public/private options
- ✅ Advanced ticket search with Zendesk query syntax
- ✅ Ticket metrics and analytics
- ✅ User and organization management
- ✅ Satisfaction ratings and agent performance tracking
- ✅ Knowledge base article retrieval

### **🏢 Enterprise Performance Analytics**
- ✅ **Agent Performance Metrics** - Comprehensive response times, resolution rates, satisfaction scores
- ✅ **Team Performance Dashboard** - Agent rankings, workload distribution, trend analysis
- ✅ **Agent Scorecards** - Performance vs targets, improvement areas, historical trends

### **⚖️ Workload Management**
- ✅ **Agent Workload Analysis** - Active tickets, capacity utilization, imbalance alerts
- ✅ **Ticket Reassignment Suggestions** - Balance workload, match expertise, optimize assignments
- ✅ **Agent Group Management** - Assign agents to groups, manage memberships

### **📊 SLA Monitoring & Compliance**
- ✅ **SLA Compliance Reports** - First response and resolution time compliance
- ✅ **At-Risk Ticket Identification** - Proactive SLA breach prevention
- ✅ **SLA Policy Management** - View and analyze SLA configurations

### **🤖 Advanced Automation**
- ✅ **Bulk Ticket Operations** - Mass updates for status, priority, tags, assignments
- ✅ **Auto-Categorization** - ML-based ticket categorization and tagging
- ✅ **Ticket Escalation** - Formalized escalation with notifications

### **🎯 Advanced Ticket Operations**
- ✅ **Ticket Merging** - Merge multiple tickets into one target ticket
- ✅ **Ticket Cloning** - Clone tickets with optional comments
- ✅ **Tag Management** - Add/remove tags from tickets
- ✅ **Related Tickets** - Find tickets from same requester or with similar tags

### **🏢 Organization & User Management**
- ✅ **Advanced Organization Tools** - Create, update, search organizations
- ✅ **User Management** - Create, update, suspend users with role management
- ✅ **User Identity Management** - Email addresses, phone numbers, verification
- ✅ **Advanced User Search** - Filter by role, organization, custom criteria

### **📋 Custom Fields & Configuration**
- ✅ **Ticket Fields** - View all ticket fields including custom configurations
- ✅ **User Fields** - Custom user field management
- ✅ **Organization Fields** - Custom organization field management
- ✅ **Ticket Forms** - View and manage ticket form configurations

### **🔍 Advanced Search & Export**
- ✅ **Multi-Object Search** - Search across tickets, users, organizations
- ✅ **Search Export** - Export search results for bulk processing
- ✅ **Advanced Filtering** - Sort options, custom date ranges

### **⚙️ Automation & Business Rules**
- ✅ **Automations Management** - View automation conditions and actions
- ✅ **Triggers Management** - View trigger configurations
- ✅ **Macro Management** - View and apply macros to tickets

### **📚 Knowledge Base Integration**
- ✅ **Help Center Search** - Search articles by content, category, locale
- ✅ **Article Management** - Retrieve articles by section or category
- ✅ **Multi-language Support** - Locale-specific content management

### **🔍 Audit & Compliance**
- ✅ **Ticket Audit Logs** - Complete change history for tickets
- ✅ **Ticket Events** - System events and user actions
- ✅ **Activity Tracking** - Comprehensive audit trails

### **👥 Collaboration Features**
- ✅ **Collaborator Management** - Add/remove CCs, manage ticket access
- ✅ **Stakeholder Notifications** - Automated stakeholder communication
- ✅ **User Creation** - Auto-create users for collaboration

### **📈 Advanced Reporting**
- ✅ **Incremental Data Sync** - Efficient data synchronization
- ✅ **Detailed Ticket Metrics** - Comprehensive SLA and performance data
- ✅ **Agent Activity Reports** - Detailed productivity and performance analysis

## 📦 Installation

### Prerequisites
- Python 3.8+
- [uv](https://docs.astral.sh/uv/) package manager
- Zendesk API credentials

### Setup

1. **Clone and install dependencies:**
```bash
git clone <repository-url>
cd zendesk-mcp-server
uv sync
```

2. **Configure environment variables:**
```bash
# Copy the example environment file
cp .env.example .env

# Edit .env with your Zendesk credentials
ZENDESK_SUBDOMAIN=your-subdomain
ZENDESK_EMAIL=your-email@company.com
ZENDESK_API_KEY=your-api-key
```

3. **Configure Claude Desktop:**

Add this configuration to your Claude Desktop settings file:

**Location:**
- **macOS:** `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Windows:** `%APPDATA%\Claude\claude_desktop_config.json`

**Configuration:**
```json
{
  "mcpServers": {
    "zendesk": {
      "command": "uv",
      "args": ["--directory", "/path/to/zendesk-mcp-server", "run", "zendesk"],
      "env": {
        "ZENDESK_SUBDOMAIN": "your-subdomain",
        "ZENDESK_EMAIL": "your-email@company.com", 
        "ZENDESK_API_KEY": "your-api-key"
      }
    }
  }
}
```

4. **Restart Claude Desktop** to load the new server.

## 🔧 Configuration

### Environment Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `ZENDESK_SUBDOMAIN` | Your Zendesk subdomain (without .zendesk.com) | `mycompany` |
| `ZENDESK_EMAIL` | Admin email for API access | `admin@company.com` |
| `ZENDESK_API_KEY` | API key from Zendesk Admin Center | `abc123...` |

### Getting Zendesk API Credentials

1. **Log in to Zendesk Admin Center**
2. **Navigate to:** Apps and integrations > APIs > Zendesk API
3. **Enable Token Access** (if not already enabled)
4. **Create API Key:** Click "+" next to "Active API Tokens"
5. **Copy the generated token** - this is your `ZENDESK_API_KEY`

## 📖 Usage Examples

### Basic Operations
```
# Get ticket information
"Show me ticket #12345"

# Search for tickets (Team plan optimized defaults)
"Find all high priority tickets created in the last week"
"Show me a detailed analysis of open tickets with user info"
"Search tickets with automatic categorization and enrichment"
"Get comprehensive ticket analysis with all context"

# Check agent performance  
"What's the performance of agent John Smith this month?"
```

### Enterprise Analytics
```
# Team performance analysis
"Generate a team performance dashboard for the last quarter"

# Workload analysis
"Show me the current workload distribution across all agents"

# SLA compliance
"Generate an SLA compliance report for last month"
```

### Advanced Operations
```
# Bulk operations
"Update all tickets tagged 'billing' to high priority"

# Agent management
"Assign user ID 12345 to the support group"

# Ticket operations
"Merge tickets 100, 101, 102 into ticket 99"
```

### Search and Analysis
```
# Advanced search
"Search for all users in organization 'Acme Corp' with agent role"

# Export data
"Export all tickets from last month for reporting"

# Knowledge base
"Search the help center for articles about password reset"
```

## 🔍 Search Query Syntax

The server supports Zendesk's powerful search syntax:

### Ticket Searches
```
# Basic search
status:open priority:high

# With categorization
status:open categorize:true

# With full details
status:open include_description:true compact:false

# Summary mode for large datasets
status:open summary_mode:true

# Advanced filtering
type:incident created>2024-01-01
assignee:john@company.com tags:billing
organization:"Acme Corp" updated<2024-12-01
```

### User Searches  
```
type:user role:agent
organization:12345 email:*@company.com
created>2024-01-01 active:true
```

### Advanced Filters
```
# Date ranges
created>=2024-01-01 created<=2024-12-31

# Multiple values
status:open OR status:pending
priority:high OR priority:urgent

# Exclusions  
-status:closed -tags:spam

# Wildcards
subject:*password* email:*@domain.com
```

## ⚡ Performance Features (Team Plan Optimized)

- **Team Plan Optimized:** Higher default limits and detailed responses for Claude Team plan users
- **Smart Size Management:** Intelligent response size handling (4KB default, up from 2KB)
- **Rich Metadata:** Comprehensive metadata about data availability and truncation
- **Dynamic Pagination:** Cursor-based pagination with configurable page sizes (25 default, up to 50)
- **Automatic Categorization:** ML-based ticket categorization enabled by default
- **Data Enrichment:** Optional user and organization details for comprehensive context
- **Comprehensive Analysis:** Multi-tool workflows for complete ticket investigation
- **Summary Mode:** Statistical summaries for large datasets when needed
- **Caching Benefits:** Leverages Claude Team plan caching for repeated data access
- **Rate Limiting:** Built-in Zendesk API rate limit compliance
- **Error Handling:** Comprehensive error handling and retry logic
- **Bulk Operations:** Efficient batch processing for large operations

## 🛠️ Available Tools

The server provides **55+ tools** organized by category:

### Core Operations (11 tools)
- `get_ticket`, `get_ticket_comments`, `create_ticket_comment`
- `search_tickets` - Team plan optimized: Detailed search with enrichment and categorization
- `comprehensive_ticket_analysis` - NEW: Complete multi-tool ticket analysis
- `get_ticket_counts`, `get_ticket_metrics`
- `get_user_tickets`, `get_organization_tickets`
- `get_satisfaction_ratings`, `get_agent_performance`, `get_user_by_id`

### Enterprise Analytics (3 tools)
- `get_agent_performance_metrics`, `get_team_performance_dashboard`
- `generate_agent_scorecard`

### Workload Management (2 tools)
- `get_agent_workload_analysis`, `suggest_ticket_reassignment`

### SLA Monitoring (2 tools)  
- `get_sla_compliance_report`, `get_at_risk_tickets`

### Advanced Automation (3 tools)
- `bulk_update_tickets`, `auto_categorize_tickets`, `escalate_ticket`

### Macros & Templates (3 tools)
- `get_macros`, `apply_macro_to_ticket`, `get_ticket_forms`

### Advanced Ticket Operations (5 tools)
- `merge_tickets`, `clone_ticket`, `add_ticket_tags`
- `remove_ticket_tags`, `get_ticket_related_tickets`

### Organization Management (4 tools)
- `get_organizations`, `get_organization_details`
- `update_organization`, `get_organization_users`

### User Management (5 tools)
- `create_user`, `update_user`, `suspend_user`
- `search_users`, `get_user_identities`

### Groups & Agents (4 tools)
- `get_groups`, `get_group_memberships`
- `assign_agent_to_group`, `remove_agent_from_group`

### Custom Fields (3 tools)
- `get_ticket_fields`, `get_user_fields`, `get_organization_fields`

### Advanced Search (2 tools)
- `advanced_search`, `export_search_results`

### Automation (3 tools)
- `get_automations`, `get_triggers`, `get_sla_policies`

### Knowledge Base (2 tools)
- `search_help_center`, `get_help_center_articles`

### Audit & Events (2 tools)
- `get_ticket_audits`, `get_ticket_events`

### Collaboration (3 tools)
- `add_ticket_collaborators`, `get_ticket_collaborators`
- `remove_ticket_collaborators`

### Advanced Reporting (3 tools)
- `get_incremental_tickets`, `get_ticket_metrics_detailed`
- `generate_agent_activity_report`

## 📊 API Rate Limits

Zendesk has API rate limits to ensure service stability:

- **Standard plans:** 200 requests per minute
- **Professional plans:** 400 requests per minute  
- **Enterprise plans:** 700 requests per minute

The server automatically handles rate limiting and implements exponential backoff for failed requests.

## 🐛 Troubleshooting

### Common Issues

1. **"Missing required Zendesk credentials"**
   - Verify your `.env` file has all required variables
   - Check that environment variables are properly set in Claude Desktop config

2. **"SSL/Connection errors"**
   - Verify your `ZENDESK_SUBDOMAIN` is correct (no `.zendesk.com` suffix)
   - Check your internet connection
   - Verify API credentials are valid

3. **"Permission denied" errors**
   - Ensure your API key has the necessary permissions
   - Check that your Zendesk user account has access to the requested resources

4. **"Rate limit exceeded"**
   - The server automatically handles rate limits
   - If persistent, reduce the frequency of requests

5. **"Tool not found" errors**
   - Restart Claude Desktop completely
   - Clear Claude Desktop cache:
     - **macOS:** `~/Library/Caches/Claude/`
     - **Windows:** `%LOCALAPPDATA%\Claude\Cache\`

### Debug Mode

To enable debug logging, set the environment variable:
```bash
export MCP_LOG_LEVEL=debug
```

### Verification Commands

Test your setup:
```bash
# Test server startup
uv run zendesk --help

# Test credentials  
uv run python -c "
from src.zendesk_mcp_server.zendesk_client import ZendeskClient
client = ZendeskClient()
print('✅ Zendesk connection successful')
"
```

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🔗 Related Resources

- [Zendesk API Documentation](https://developer.zendesk.com/api-reference/)
- [Model Context Protocol Specification](https://modelcontextprotocol.io/)
- [Claude Desktop Documentation](https://claude.ai/desktop)
- [uv Package Manager](https://docs.astral.sh/uv/)

---

**🎯 Transform your Zendesk support operations with comprehensive AI-powered management tools!**
