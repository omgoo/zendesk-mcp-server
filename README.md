# Zendesk MCP Server

A comprehensive **Model Context Protocol (MCP)** server for **Zendesk integration** that provides advanced support team management capabilities. This server enables AI assistants like Claude to interact with Zendesk through a rich set of tools for ticket management, analytics, automation, and team optimization.

## 🚀 **Enterprise Features**

### **🎯 Agent Performance Analytics**
- **Comprehensive metrics**: Response times, resolution rates, satisfaction scores
- **Team performance dashboards**: Rankings, workload distribution, bottleneck identification  
- **Individual scorecards**: Performance vs targets, strengths, improvement areas, personalized recommendations
- **Historical trends**: Performance tracking over time with multiple period options

### **⚖️ Workload Management**
- **Real-time workload analysis**: Capacity utilization, overdue tickets, imbalance alerts
- **Intelligent reassignment**: AI-powered suggestions for optimal ticket distribution
- **Automated load balancing**: Workload optimization recommendations
- **Capacity planning**: Agent availability and capacity management

### **📊 SLA Monitoring & Compliance**
- **Comprehensive SLA reporting**: First response and resolution time compliance by priority
- **At-risk ticket identification**: Proactive breach prevention with time-to-breach calculations
- **Performance targets**: Configurable SLA targets with compliance tracking
- **Escalation triggers**: Automatic alerts for SLA violations

### **🤖 Advanced Automation**
- **Bulk ticket operations**: Mass updates for status, priority, tags, and assignments
- **AI-powered categorization**: Automatic ticket tagging based on content analysis
- **Smart escalation**: Intelligent escalation with stakeholder notifications
- **Template management**: Automated response templates and macro suggestions

### **📈 Analytics & Insights**
- **Customer satisfaction tracking**: Score distribution and trend analysis
- **Knowledge base optimization**: Article effectiveness and usage analytics
- **Team performance insights**: Bottleneck identification and optimization recommendations
- **Predictive analytics**: Performance forecasting and capacity planning

## Installation

1. **Install dependencies**:
   ```bash
   uv sync
   ```

2. **Set up environment variables**:
   ```bash
   cp .env.example .env
   # Edit .env with your Zendesk credentials
   ```

3. **Configure Claude Desktop**:
   Add to your Claude Desktop configuration file:

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

## 🛠️ **Complete Tool Reference**

### **🎯 Performance Analytics Tools**

#### **`get_agent_performance_metrics`** - Comprehensive Agent Analysis
```json
{
  "agent_id": 123,                    // Optional: specific agent or all agents
  "start_date": "2025-01-01",        // Optional: analysis start date
  "end_date": "2025-01-31",          // Optional: analysis end date  
  "include_satisfaction": true        // Optional: include customer satisfaction data
}
```
**Returns**: Detailed performance metrics including response times, resolution rates, satisfaction scores, and performance scoring.

#### **`get_team_performance_dashboard`** - Team-Wide Analytics
```json
{
  "team_id": 456,                    // Optional: specific team analysis
  "period": "month"                  // week, month, quarter
}
```
**Returns**: Comprehensive team dashboard with agent rankings, workload distribution, trend analysis, and bottleneck identification.

#### **`generate_agent_scorecard`** - Individual Performance Reports
```json
{
  "agent_id": 123,                   // Required: agent to analyze
  "period": "month"                  // week, month, quarter
}
```
**Returns**: Detailed scorecard with performance vs targets, strengths, improvement areas, and personalized recommendations.

### **⚖️ Workload Management Tools**

#### **`get_agent_workload_analysis`** - Real-Time Workload Monitoring
```json
{
  "include_pending": true,           // Include pending/hold tickets
  "include_open": true               // Include open tickets
}
```
**Returns**: Complete workload analysis with capacity utilization, overdue tickets, imbalance alerts, and redistribution recommendations.

#### **`suggest_ticket_reassignment`** - Intelligent Load Balancing
```json
{
  "criteria": "workload_balance"     // workload_balance, urgent_priority
}
```
**Returns**: AI-powered reassignment suggestions with specific ticket recommendations and balancing rationale.

### **📊 SLA Monitoring Tools**

#### **`get_sla_compliance_report`** - Comprehensive SLA Analysis
```json
{
  "start_date": "2025-01-01",       // Optional: report start date
  "end_date": "2025-01-31",         // Optional: report end date
  "agent_id": 123                    // Optional: specific agent analysis
}
```
**Returns**: Detailed SLA compliance report with first response and resolution time analysis by priority level.

#### **`get_at_risk_tickets`** - Proactive SLA Management
```json
{
  "time_horizon": 24                 // Hours ahead to identify at-risk tickets
}
```
**Returns**: List of tickets at risk of SLA breach with time remaining, risk factors, and escalation recommendations.

### **🤖 Advanced Automation Tools**

#### **`bulk_update_tickets`** - Mass Ticket Operations
```json
{
  "ticket_ids": [123, 456, 789],
  "updates": {
    "status": "pending",
    "priority": "high",
    "assignee_id": 456,
    "tags": {
      "action": "add",               // add, remove, set
      "values": ["urgent", "escalated"]
    }
  },
  "reason": "Bulk escalation for system outage"
}
```
**Returns**: Detailed results of bulk update operation with success/failure tracking.

#### **`auto_categorize_tickets`** - AI-Powered Categorization
```json
{
  "ticket_ids": [123, 456],         // Optional: specific tickets or recent untagged
  "use_ml": true                     // Enable ML-based categorization
}
```
**Returns**: Categorization results with suggested tags, confidence levels, and application status.

#### **`escalate_ticket`** - Smart Escalation Management
```json
{
  "ticket_id": 123,                  // Required: ticket to escalate
  "escalation_level": "manager",     // manager, senior_agent, external
  "reason": "Complex technical issue requiring expertise",
  "notify_stakeholders": true        // Send notifications
}
```
**Returns**: Escalation tracking with applied updates, notifications sent, and next steps.

### **📋 Core Ticket Management Tools**

#### **`search_tickets`** - Advanced Search with Performance Optimization
```json
{
  "query": "status:open priority:high",
  "sort_by": "created_at",           // created_at, updated_at, priority, status
  "sort_order": "desc",              // asc, desc
  "compact": true                    // Minimal data for better performance
}
```

#### **`get_ticket_counts`** - Ticket Statistics Overview
```json
{}
```

#### **`get_user_by_id`** - User Information Resolution
```json
{
  "user_id": 123
}
```

## 🎭 **Guided Prompts & Templates**

The server includes intelligent prompt templates for common scenarios:

- **`analytics-dashboard`**: Generate comprehensive team performance reports
- **`search-tickets`**: Advanced ticket search with query assistance
- **`analyze-user-workload`**: User-specific workload analysis
- **`agent-performance`**: Individual agent performance evaluation

## 🔍 **Advanced Search Syntax**

### **Performance-Optimized Queries**
```
# Use compact mode for large datasets
"status:open priority:urgent" + compact: true

# Time-based analysis
"created>2025-01-01 updated<2025-01-31"

# Agent-specific performance
"assignee:agent@company.com status:solved"

# SLA monitoring
"created>24hours status:new"
```

### **Workload Management Queries**
```
# Overloaded agents
"assignee_id:123 (status:open OR status:pending)"

# Unassigned urgent tickets
"status:new priority:urgent assignee:none"

# Escalated tickets
"tags:escalated status:open"
```

## 📊 **Performance Optimization**

### **Handling Large Datasets**
- **Use compact mode**: Set `compact: true` for search operations
- **Limit time ranges**: Use focused date ranges for analytics
- **Batch operations**: Bulk updates process up to 100 tickets efficiently
- **Caching**: Automatic caching for knowledge base and user data

### **Rate Limit Management**
- **Automatic throttling**: Built-in rate limit handling
- **Optimized queries**: Efficient API usage patterns
- **Batch processing**: Grouped operations to minimize API calls

## 🚨 **Troubleshooting**

### **Performance Issues**
1. **"Result exceeds maximum length"**:
   - Use `compact: true` in search queries
   - Reduce time ranges for analytics
   - Use specific agent or team filters

2. **Slow response times**:
   - Enable caching for repeated queries
   - Use batch operations for multiple updates
   - Consider shorter analysis periods

### **Agent Performance Analysis**
For questions like "Who is the best performing support agent?":

1. **Use optimized tools**: `get_agent_performance` instead of large search queries
2. **Follow up with details**: Use `get_user_by_id` to resolve agent names
3. **Adjust time periods**: Use `days` parameter (1-90) to focus analysis
4. **Check permissions**: Ensure API token can access user and metrics data

### **SLA Monitoring**
For SLA compliance tracking:

1. **Regular monitoring**: Use `get_at_risk_tickets` for proactive management
2. **Historical analysis**: Use `get_sla_compliance_report` for trend analysis
3. **Automated alerts**: Set up regular checks for at-risk tickets
4. **Escalation workflows**: Use `escalate_ticket` for systematic escalation

## 🔧 **Advanced Configuration**

### **Custom SLA Targets**
The server includes configurable SLA targets:
- **Urgent**: 1h response, 4h resolution
- **High**: 2h response, 8h resolution  
- **Normal**: 8h response, 24h resolution
- **Low**: 24h response, 48h resolution

### **Performance Targets**
Default performance targets for scorecards:
- **Resolution Rate**: 85%
- **Response Time**: 2h average
- **Resolution Time**: 24h average
- **Satisfaction Score**: 4.0/5.0

## 🚀 **Next Steps**

1. **Restart Claude Desktop** to pick up the server changes
2. **Test with comprehensive queries**:
   - "Analyze our team's performance this month"
   - "Show me tickets at risk of SLA breach"
   - "What's the current workload distribution?"
3. **Explore automation features**:
   - "Categorize recent untagged tickets"
   - "Suggest ticket reassignments for better balance"
   - "Generate agent scorecards for the team"

## 📋 **License**

This project is licensed under the MIT License - see the LICENSE file for details.

---

**🎯 Ready to revolutionize your support team management with AI-powered insights and automation!**
