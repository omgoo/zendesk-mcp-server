# Zendesk MCP Server - Comprehensive Usage Examples

This document provides detailed examples for all tools and features in the enterprise Zendesk MCP server.

## 🎯 **Agent Performance Analytics**

### Get Comprehensive Agent Performance Metrics
```
Request: get_agent_performance_metrics
Arguments: {
  "agent_id": 386646129318,
  "start_date": "2025-01-01",
  "end_date": "2025-01-31",
  "include_satisfaction": true
}
```
**Use Case**: Analyze specific agent's performance for the month of January including customer satisfaction data.

### Get All Agents Performance (Team Overview)
```
Request: get_agent_performance_metrics
Arguments: {
  "start_date": "2025-01-15",
  "end_date": "2025-01-22"
}
```
**Use Case**: Weekly team performance review - analyze all agents' metrics for the past week.

### Generate Team Performance Dashboard
```
Request: get_team_performance_dashboard
Arguments: {
  "period": "month"
}
```
**Use Case**: Monthly team meeting - get comprehensive dashboard with rankings, workload distribution, and bottlenecks.

### Generate Quarterly Team Dashboard
```
Request: get_team_performance_dashboard
Arguments: {
  "period": "quarter"
}
```
**Use Case**: Quarterly business review - comprehensive 90-day team performance analysis.

### Generate Individual Agent Scorecard
```
Request: generate_agent_scorecard
Arguments: {
  "agent_id": 386646129318,
  "period": "month"
}
```
**Use Case**: Monthly performance review - detailed scorecard with targets, strengths, and improvement recommendations.

### Generate Weekly Agent Scorecard
```
Request: generate_agent_scorecard
Arguments: {
  "agent_id": 386646129318,
  "period": "week"
}
```
**Use Case**: Weekly check-in - quick performance assessment with actionable feedback.

## ⚖️ **Workload Management & Distribution**

### Analyze Current Team Workload
```
Request: get_agent_workload_analysis
Arguments: {
  "include_pending": true,
  "include_open": true
}
```
**Use Case**: Daily standup - get real-time view of team workload distribution and identify bottlenecks.

### Analyze Open Tickets Only
```
Request: get_agent_workload_analysis
Arguments: {
  "include_pending": false,
  "include_open": true
}
```
**Use Case**: Focus on active work - exclude pending/hold tickets to see current active workload.

### Get Workload Balance Suggestions
```
Request: suggest_ticket_reassignment
Arguments: {
  "criteria": "workload_balance"
}
```
**Use Case**: Load balancing - get AI suggestions to redistribute tickets from overloaded to underloaded agents.

### Get Urgent Priority Redistribution Suggestions
```
Request: suggest_ticket_reassignment
Arguments: {
  "criteria": "urgent_priority"
}
```
**Use Case**: Emergency response - redistribute urgent tickets to agents with capacity.

## 📊 **SLA Monitoring & Compliance**

### Generate Monthly SLA Compliance Report
```
Request: get_sla_compliance_report
Arguments: {
  "start_date": "2025-01-01",
  "end_date": "2025-01-31"
}
```
**Use Case**: Monthly compliance review - comprehensive SLA performance analysis by priority level.

### Get Agent-Specific SLA Performance
```
Request: get_sla_compliance_report
Arguments: {
  "start_date": "2025-01-15",
  "end_date": "2025-01-22",
  "agent_id": 386646129318
}
```
**Use Case**: Individual performance review - specific agent's SLA compliance for performance evaluation.

### Get Current SLA Compliance (Last 30 Days)
```
Request: get_sla_compliance_report
Arguments: {}
```
**Use Case**: Quick compliance check - default 30-day rolling SLA performance overview.

### Identify Tickets at Risk (Next 24 Hours)
```
Request: get_at_risk_tickets
Arguments: {
  "time_horizon": 24
}
```
**Use Case**: Daily SLA monitoring - identify tickets that might breach SLA in the next 24 hours.

### Extended Risk Analysis (Next 48 Hours)
```
Request: get_at_risk_tickets
Arguments: {
  "time_horizon": 48
}
```
**Use Case**: Weekend planning - identify tickets that need attention before the weekend.

### Critical Risk Analysis (Next 4 Hours)
```
Request: get_at_risk_tickets
Arguments: {
  "time_horizon": 4
}
```
**Use Case**: Emergency response - immediate action needed for imminent SLA breaches.

## 🤖 **Advanced Ticket Management & Automation**

### Bulk Status Update with Reason
```
Request: bulk_update_tickets
Arguments: {
  "ticket_ids": [12345, 12346, 12347],
  "updates": {
    "status": "pending",
    "priority": "high"
  },
  "reason": "System maintenance - escalating priority for affected tickets"
}
```
**Use Case**: System maintenance - bulk update affected tickets with proper documentation.

### Bulk Assignment to Specific Agent
```
Request: bulk_update_tickets
Arguments: {
  "ticket_ids": [12345, 12346, 12347, 12348],
  "updates": {
    "assignee_id": 386646129318,
    "status": "open"
  },
  "reason": "Specialized technical issue requiring expert attention"
}
```
**Use Case**: Expert assignment - bulk assign complex tickets to specialized agent.

### Bulk Tag Management (Add Tags)
```
Request: bulk_update_tickets
Arguments: {
  "ticket_ids": [12345, 12346, 12347],
  "updates": {
    "tags": {
      "action": "add",
      "values": ["urgent", "escalated", "system_outage"]
    }
  },
  "reason": "Critical system outage affecting multiple customers"
}
```
**Use Case**: Emergency response - tag all related tickets for incident tracking.

### Bulk Tag Management (Remove Tags)
```
Request: bulk_update_tickets
Arguments: {
  "ticket_ids": [12345, 12346, 12347],
  "updates": {
    "tags": {
      "action": "remove",
      "values": ["pending_customer", "waiting"]
    }
  },
  "reason": "Customer responses received - removing waiting tags"
}
```
**Use Case**: Process update - clean up tags after customer responses.

### Auto-Categorize Recent Untagged Tickets
```
Request: auto_categorize_tickets
Arguments: {
  "use_ml": true
}
```
**Use Case**: Daily maintenance - automatically categorize and tag recent tickets for better organization.

### Auto-Categorize Specific Tickets
```
Request: auto_categorize_tickets
Arguments: {
  "ticket_ids": [12345, 12346, 12347, 12348, 12349],
  "use_ml": true
}
```
**Use Case**: Ticket triage - categorize specific tickets that need classification.

### Auto-Categorize Without ML (Rule-Based Only)
```
Request: auto_categorize_tickets
Arguments: {
  "ticket_ids": [12345, 12346, 12347],
  "use_ml": false
}
```
**Use Case**: Simple categorization - use only keyword-based rules for basic tagging.

### Escalate to Manager
```
Request: escalate_ticket
Arguments: {
  "ticket_id": 12345,
  "escalation_level": "manager",
  "reason": "Customer complaint escalated to senior management level",
  "notify_stakeholders": true
}
```
**Use Case**: Management escalation - serious issue requiring manager attention.

### Escalate to Senior Agent
```
Request: escalate_ticket
Arguments: {
  "ticket_id": 12346,
  "escalation_level": "senior_agent",
  "reason": "Complex technical issue requiring advanced expertise",
  "notify_stakeholders": true
}
```
**Use Case**: Technical escalation - complex issue needing senior technical skills.

### External Escalation
```
Request: escalate_ticket
Arguments: {
  "ticket_id": 12347,
  "escalation_level": "external",
  "reason": "Issue requires third-party vendor involvement",
  "notify_stakeholders": true
}
```
**Use Case**: Vendor escalation - issue requiring external partner assistance.

## 🔍 **Enhanced Search & Analytics**

### Performance-Optimized Search (Compact Mode)
```
Request: search_tickets
Arguments: {
  "query": "status:open created>7days",
  "sort_by": "created_at",
  "sort_order": "desc",
  "compact": true
}
```
**Use Case**: Large dataset analysis - use compact mode to prevent overwhelming responses.

### Detailed Search (Full Information)
```
Request: search_tickets
Arguments: {
  "query": "priority:urgent status:open",
  "sort_by": "created_at",
  "sort_order": "asc",
  "compact": false
}
```
**Use Case**: Detailed investigation - get full ticket information for thorough analysis.

### Agent Performance Search
```
Request: search_tickets
Arguments: {
  "query": "assignee:386646129318 status:solved created>30days",
  "compact": true
}
```
**Use Case**: Agent productivity analysis - review solved tickets for specific agent.

### SLA Risk Analysis Search
```
Request: search_tickets
Arguments: {
  "query": "status:new created>4hours priority:urgent",
  "sort_by": "created_at",
  "sort_order": "asc",
  "compact": true
}
```
**Use Case**: SLA breach prevention - find urgent tickets without first response.

## 📊 **Core Analytics & Reporting**

### Get Overall Ticket Statistics
```
Request: get_ticket_counts
Arguments: {}
```
**Use Case**: Daily dashboard - quick overview of ticket volume and distribution.

### Get Agent Performance Overview (Legacy)
```
Request: get_agent_performance
Arguments: {
  "days": 7
}
```
**Use Case**: Quick weekly check - simplified agent performance for the past week.

### Get Monthly Agent Performance (Legacy)
```
Request: get_agent_performance
Arguments: {
  "days": 30
}
```
**Use Case**: Monthly review - 30-day agent performance summary.

### Get Customer Satisfaction Overview
```
Request: get_satisfaction_ratings
Arguments: {
  "limit": 50
}
```
**Use Case**: Customer satisfaction review - recent satisfaction ratings and trends.

### Get Extended Satisfaction Analysis
```
Request: get_satisfaction_ratings
Arguments: {
  "limit": 200
}
```
**Use Case**: Comprehensive satisfaction analysis - larger dataset for trend analysis.

## 👤 **User & Organization Management**

### Get Detailed User Information
```
Request: get_user_by_id
Arguments: {
  "user_id": 386646129318
}
```
**Use Case**: Agent profile lookup - get complete agent information for performance analysis.

### Get User Tickets (Requested)
```
Request: get_user_tickets
Arguments: {
  "user_id": 123456789,
  "ticket_type": "requested"
}
```
**Use Case**: Customer history - see all tickets submitted by a specific customer.

### Get User Tickets (Assigned)
```
Request: get_user_tickets
Arguments: {
  "user_id": 386646129318,
  "ticket_type": "assigned"
}
```
**Use Case**: Agent workload - see all tickets currently assigned to an agent.

### Get Organization Tickets
```
Request: get_organization_tickets
Arguments: {
  "organization_id": 987654321
}
```
**Use Case**: Account management - review all tickets for a specific organization.

## 🎭 **Common Workflow Examples**

### Daily Team Standup Workflow
1. **Check current workload**: `get_agent_workload_analysis`
2. **Identify at-risk tickets**: `get_at_risk_tickets` (24 hours)
3. **Review urgent tickets**: `search_tickets` with "priority:urgent status:open"
4. **Balance workload if needed**: `suggest_ticket_reassignment`

### Weekly Performance Review
1. **Generate team dashboard**: `get_team_performance_dashboard` (week)
2. **Individual scorecards**: `generate_agent_scorecard` for each agent
3. **SLA compliance check**: `get_sla_compliance_report` (7 days)
4. **Satisfaction review**: `get_satisfaction_ratings`

### Monthly Management Review
1. **Team performance**: `get_team_performance_dashboard` (month)
2. **SLA compliance**: `get_sla_compliance_report` (30 days)
3. **Individual performance**: `get_agent_performance_metrics` per agent
4. **Workload trends**: `get_agent_workload_analysis`

### Emergency Response Workflow
1. **Identify critical tickets**: `get_at_risk_tickets` (4 hours)
2. **Bulk escalate if needed**: `bulk_update_tickets` with priority increase
3. **Escalate specific tickets**: `escalate_ticket` to appropriate level
4. **Redistribute workload**: `suggest_ticket_reassignment` (urgent_priority)

### System Maintenance Workflow
1. **Identify affected tickets**: `search_tickets` with relevant criteria
2. **Bulk update status**: `bulk_update_tickets` with maintenance reason
3. **Add tracking tags**: `bulk_update_tickets` with tag additions
4. **Monitor during maintenance**: `get_at_risk_tickets` for new issues

## 🔧 **Troubleshooting Examples**

### Handle "Maximum Length" Errors
```
# Instead of this (might be too large):
Request: search_tickets
Arguments: {"query": "created>30days"}

# Use this (compact mode):
Request: search_tickets
Arguments: {
  "query": "created>30days",
  "compact": true
}
```

### Performance Optimization
```
# For large datasets, use specific filters:
Request: get_agent_performance_metrics
Arguments: {
  "agent_id": 386646129318,  # Specific agent only
  "start_date": "2025-01-15", # Limited date range
  "end_date": "2025-01-22"
}
```

### Gradual Data Analysis
```
# Step 1: Get overview
Request: get_team_performance_dashboard
Arguments: {"period": "week"}

# Step 2: Drill down on specific agents
Request: generate_agent_scorecard
Arguments: {"agent_id": [top_performer_id], "period": "week"}

# Step 3: Detailed analysis
Request: get_agent_performance_metrics
Arguments: {"agent_id": [specific_agent], "start_date": "2025-01-15"}
```

## 🚀 **Advanced Use Cases**

### AI-Powered Support Optimization
1. **Auto-categorize**: `auto_categorize_tickets` for better organization
2. **Balance workloads**: `suggest_ticket_reassignment` for optimal distribution
3. **Monitor SLA**: `get_at_risk_tickets` for proactive management
4. **Performance coaching**: `generate_agent_scorecard` for targeted improvements

### Data-Driven Decision Making
1. **Trend analysis**: `get_team_performance_dashboard` across different periods
2. **Capacity planning**: `get_agent_workload_analysis` for resource allocation
3. **Quality assurance**: `get_sla_compliance_report` for process improvement
4. **Customer satisfaction**: `get_satisfaction_ratings` for service quality

### Automated Workflows
1. **Bulk operations**: `bulk_update_tickets` for mass changes
2. **Smart escalation**: `escalate_ticket` with proper notifications
3. **Intelligent categorization**: `auto_categorize_tickets` with ML
4. **Proactive monitoring**: `get_at_risk_tickets` for prevention

---

**🎯 These examples cover all enterprise features and provide practical guidance for every tool in your comprehensive Zendesk MCP server!** 