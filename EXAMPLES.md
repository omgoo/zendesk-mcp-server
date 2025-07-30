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
**Use Case**: Monthly 1:1 meetings - detailed scorecard showing performance vs targets and improvement areas.

### Generate Weekly Agent Scorecard
```
Request: generate_agent_scorecard
Arguments: {
  "agent_id": 386646129318,
  "period": "week"
}
```
**Use Case**: Weekly check-in - quick performance assessment with actionable feedback.

## ⚖️ **Workload Management**

### Analyze Current Agent Workload
```
Request: get_agent_workload_analysis
Arguments: {
  "include_pending": true,
  "include_open": true
}
```
**Use Case**: Daily team standup - check current workload distribution and identify overloaded agents.

### Get Workload Analysis (Active Tickets Only)
```
Request: get_agent_workload_analysis
Arguments: {
  "include_pending": false,
  "include_open": true
}
```
**Use Case**: Focus on active work - exclude tickets on hold to see true active workload.

### Suggest Ticket Reassignments for Balance
```
Request: suggest_ticket_reassignment
Arguments: {
  "criteria": "workload_balance"
}
```
**Use Case**: End of day workload balancing - redistribute tickets to even out agent workloads.

### Suggest Reassignments Based on Expertise
```
Request: suggest_ticket_reassignment
Arguments: {
  "criteria": "expertise"
}
```
**Use Case**: Complex ticket handling - reassign tickets to agents with relevant expertise.

## 📊 **SLA Monitoring**

### Generate SLA Compliance Report (All Agents)
```
Request: get_sla_compliance_report
Arguments: {
  "start_date": "2025-01-01",
  "end_date": "2025-01-31"
}
```
**Use Case**: Monthly SLA review - comprehensive compliance report for all agents and priorities.

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

### Identify At-Risk Tickets (Next 24 Hours)
```
Request: get_at_risk_tickets
Arguments: {
  "time_horizon": 24
}
```
**Use Case**: Daily morning standup - identify tickets that need immediate attention to avoid SLA breach.

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

## 🤖 **Advanced Automation**

### Bulk Update Multiple Tickets
```
Request: bulk_update_tickets
Arguments: {
  "ticket_ids": [12345, 12346, 12347, 12348],
  "updates": {
    "status": "pending",
    "priority": "high",
    "assignee_id": 386646129318,
    "tags": ["billing", "urgent"]
  },
  "reason": "Escalating billing issues to senior agent"
}
```
**Use Case**: Mass escalation - quickly update multiple related tickets with new status, priority, and assignment.

### Bulk Status Update
```
Request: bulk_update_tickets
Arguments: {
  "ticket_ids": [98765, 98766, 98767],
  "updates": {
    "status": "solved"
  },
  "reason": "Resolved by system maintenance"
}
```
**Use Case**: System maintenance completion - mark multiple tickets as solved after infrastructure fix.

### Auto-Categorize Recent Tickets
```
Request: auto_categorize_tickets
Arguments: {
  "use_ml": true
}
```
**Use Case**: Daily ticket management - automatically categorize and tag new untagged tickets using ML.

### Auto-Categorize Specific Tickets
```
Request: auto_categorize_tickets
Arguments: {
  "ticket_ids": [11111, 22222, 33333],
  "use_ml": true
}
```
**Use Case**: Manual categorization - categorize specific tickets that need proper classification.

### Escalate Ticket to Manager
```
Request: escalate_ticket
Arguments: {
  "ticket_id": 12345,
  "escalation_level": "manager",
  "reason": "Customer threatens to cancel contract, requires management attention",
  "notify_stakeholders": true
}
```
**Use Case**: High-stakes escalation - escalate critical customer issue to management with notifications.

### Escalate to Senior Agent
```
Request: escalate_ticket
Arguments: {
  "ticket_id": 67890,
  "escalation_level": "senior_agent",
  "reason": "Technical complexity beyond current agent expertise",
  "notify_stakeholders": false
}
```
**Use Case**: Technical escalation - move complex technical ticket to senior agent without external notifications.

## 🎭 **Macros and Templates Management**

### View All Available Macros
```
Request: get_macros
Arguments: {}
```
**Use Case**: Agent onboarding - show new agents all available macros sorted by usage frequency.

### Apply Standard Response Macro
```
Request: apply_macro_to_ticket
Arguments: {
  "ticket_id": 12345,
  "macro_id": 98765
}
```
**Use Case**: Standard response - quickly apply common resolution macro to ticket.

### Get Ticket Forms Configuration
```
Request: get_ticket_forms
Arguments: {}
```
**Use Case**: Form management - review all ticket forms and their field configurations for optimization.

## 🎫 **Advanced Ticket Operations**

### Merge Multiple Tickets into One
```
Request: merge_tickets
Arguments: {
  "source_ticket_ids": [12345, 12346, 12347],
  "target_ticket_id": 12344
}
```
**Use Case**: Duplicate resolution - merge multiple tickets about the same issue into one master ticket.

### Clone Important Ticket
```
Request: clone_ticket
Arguments: {
  "ticket_id": 12345,
  "include_comments": true
}
```
**Use Case**: Template creation - clone a well-handled ticket to create template for similar issues.

### Clone Ticket Without Comments
```
Request: clone_ticket
Arguments: {
  "ticket_id": 67890,
  "include_comments": false
}
```
**Use Case**: New issue tracking - clone ticket structure for new related issue without conversation history.

### Add Tags to Ticket
```
Request: add_ticket_tags
Arguments: {
  "ticket_id": 12345,
  "tags": ["billing", "urgent", "enterprise-customer"]
}
```
**Use Case**: Ticket classification - add relevant tags for better organization and routing.

### Remove Specific Tags
```
Request: remove_ticket_tags
Arguments: {
  "ticket_id": 12345,
  "tags": ["pending-customer", "waiting"]
}
```
**Use Case**: Status cleanup - remove outdated tags when ticket status changes.

### Find Related Tickets
```
Request: get_ticket_related_tickets
Arguments: {
  "ticket_id": 12345
}
```
**Use Case**: Context gathering - find other tickets from same customer or with similar issues for context.

## 🏢 **Organization Management**

### Get All Organizations
```
Request: get_organizations
Arguments: {}
```
**Use Case**: Organization overview - list all organizations for account management review.

### Search Organizations by Name
```
Request: get_organizations
Arguments: {
  "name": "Acme Corporation"
}
```
**Use Case**: Account lookup - find specific organization by name for account management.

### Search by External ID
```
Request: get_organizations
Arguments: {
  "external_id": "ORG-12345"
}
```
**Use Case**: System integration - lookup organization using external system identifier.

### Get Detailed Organization Information
```
Request: get_organization_details
Arguments: {
  "org_id": 12345678
}
```
**Use Case**: Account review - get comprehensive organization details including custom fields and metrics.

### Update Organization Information
```
Request: update_organization
Arguments: {
  "org_id": 12345678,
  "name": "Acme Corporation (Acquired)",
  "details": "Recently acquired by BigCorp Inc.",
  "notes": "Update billing contact after acquisition"
}
```
**Use Case**: Account maintenance - update organization information after corporate changes.

### Get All Users in Organization
```
Request: get_organization_users
Arguments: {
  "org_id": 12345678
}
```
**Use Case**: Account management - list all users for organization-wide communication or support planning.

## 👤 **Advanced User Management**

### Create New End User
```
Request: create_user
Arguments: {
  "name": "John Smith",
  "email": "john.smith@company.com",
  "role": "end-user",
  "organization_id": 12345678
}
```
**Use Case**: New customer onboarding - create user account for new customer contact.

### Create New Agent
```
Request: create_user
Arguments: {
  "name": "Sarah Johnson",
  "email": "sarah.johnson@ourcompany.com",
  "role": "agent"
}
```
**Use Case**: Team expansion - create new agent account for new hire.

### Update User Information
```
Request: update_user
Arguments: {
  "user_id": 98765432,
  "name": "John Smith-Wilson",
  "email": "j.smithwilson@company.com",
  "role": "agent"
}
```
**Use Case**: User maintenance - update user details after name change or role promotion.

### Suspend User Account
```
Request: suspend_user
Arguments: {
  "user_id": 98765432,
  "reason": "Employment terminated - security compliance"
}
```
**Use Case**: Security compliance - suspend user account when employee leaves company.

### Search Users by Role
```
Request: search_users
Arguments: {
  "query": "active:true",
  "role": "agent"
}
```
**Use Case**: Team management - find all active agents for scheduling or assignment purposes.

### Search Users in Organization
```
Request: search_users
Arguments: {
  "query": "verified:true",
  "organization_id": 12345678
}
```
**Use Case**: Account management - find verified users in specific organization for communication.

### Get User Contact Information
```
Request: get_user_identities
Arguments: {
  "user_id": 98765432
}
```
**Use Case**: Contact management - get all contact methods (email, phone) for important customer.

## 👥 **Groups and Agent Management**

### Get All Support Groups
```
Request: get_groups
Arguments: {}
```
**Use Case**: Team organization - review all support groups and their member counts.

### Get Group Memberships for Specific Group
```
Request: get_group_memberships
Arguments: {
  "group_id": 87654321
}
```
**Use Case**: Team management - see all agents assigned to specific support group.

### Get User's Group Memberships
```
Request: get_group_memberships
Arguments: {
  "user_id": 98765432
}
```
**Use Case**: Agent management - see which groups an agent belongs to for assignment planning.

### Assign Agent to Group
```
Request: assign_agent_to_group
Arguments: {
  "user_id": 98765432,
  "group_id": 87654321,
  "is_default": true
}
```
**Use Case**: Team onboarding - assign new agent to support group as their primary assignment.

### Assign Agent to Additional Group
```
Request: assign_agent_to_group
Arguments: {
  "user_id": 98765432,
  "group_id": 11111111,
  "is_default": false
}
```
**Use Case**: Cross-training - assign agent to additional group for backup support coverage.

### Remove Agent from Group
```
Request: remove_agent_from_group
Arguments: {
  "user_id": 98765432,
  "group_id": 87654321
}
```
**Use Case**: Team restructuring - remove agent from group during organizational changes.

## 📋 **Custom Fields and Configuration**

### Get All Ticket Fields
```
Request: get_ticket_fields
Arguments: {}
```
**Use Case**: Form configuration - review all available ticket fields for form customization.

### Get User Custom Fields
```
Request: get_user_fields
Arguments: {}
```
**Use Case**: User data management - see custom fields available for user profiles.

### Get Organization Custom Fields
```
Request: get_organization_fields
Arguments: {}
```
**Use Case**: Account management - review custom fields for organization data tracking.

## 🔍 **Advanced Search and Export**

### Advanced Ticket Search
```
Request: advanced_search
Arguments: {
  "search_type": "tickets",
  "query": "priority:high created>=2025-01-01",
  "sort_by": "created_at",
  "sort_order": "desc"
}
```
**Use Case**: Priority management - find all high priority tickets created this year, newest first.

### Search Users by Role
```
Request: advanced_search
Arguments: {
  "search_type": "users",
  "query": "role:agent active:true",
  "sort_by": "last_login_at",
  "sort_order": "desc"
}
```
**Use Case**: Team activity - find active agents sorted by most recent login.

### Search Organizations
```
Request: advanced_search
Arguments: {
  "search_type": "organizations",
  "query": "created>=2024-01-01",
  "sort_by": "created_at"
}
```
**Use Case**: Account growth - find organizations created this year for business analysis.

### Export Ticket Data for Reporting
```
Request: export_search_results
Arguments: {
  "query": "status:solved created>=2025-01-01 created<=2025-01-31",
  "object_type": "ticket"
}
```
**Use Case**: Monthly reporting - export all solved tickets from January for performance analysis.

### Export User Data
```
Request: export_search_results
Arguments: {
  "query": "role:end-user created>=2025-01-01",
  "object_type": "user"
}
```
**Use Case**: Customer growth analysis - export new customers from this year for business metrics.

## ⚙️ **Automation and Business Rules**

### View All Automations
```
Request: get_automations
Arguments: {}
```
**Use Case**: Automation audit - review all active automations and their conditions.

### View All Triggers
```
Request: get_triggers
Arguments: {}
```
**Use Case**: Workflow optimization - analyze triggers for performance and efficiency improvements.

### View SLA Policies
```
Request: get_sla_policies
Arguments: {}
```
**Use Case**: SLA management - review all SLA policies and their metrics for compliance planning.

## 🔧 **Data Limits and Full Data Access**

### Check Data Limits and Options
```
Request: get_data_limits_info
Arguments: {}
```
**Use Case**: Understanding current data limits and learning how to access full data when needed.

### Get More Comments with Custom Limits
```
Request: get_ticket_comments
Arguments: {
  "ticket_id": 12345,
  "limit": 25,
  "max_body_length": 800
}
```
**Use Case**: Investigation - get more comments with longer content than default limits.

### Get Full Untruncated Comments
```
Request: get_ticket_comments_full
Arguments: {
  "ticket_id": 12345,
  "limit": 10
}
```
**Use Case**: Deep analysis - get complete comment content without any truncation (WARNING: large data).

### Get Full Untruncated Audit History
```
Request: get_ticket_audits_full
Arguments: {
  "ticket_id": 12345,
  "limit": 20
}
```
**Use Case**: Compliance audit - get complete, untruncated audit trail with full metadata (WARNING: large data).

### Team Plan Optimized Search (Default)
```
Request: search_tickets
Arguments: {
  "query": "status:open priority:high"
}
```
**Use Case**: Team plan default - detailed responses with descriptions, categorization, and higher limits (25 tickets).

### Enhanced Search with Enrichment
```
Request: search_tickets
Arguments: {
  "query": "status:open priority:high",
  "limit": 30,
  "enrich": true,
  "categorize": true
}
```
**Use Case**: Comprehensive investigation - tickets with user/org details and automatic categorization.

### Comprehensive Ticket Analysis
```
Request: comprehensive_ticket_analysis
Arguments: {
  "ticket_id": 12345
}
```
**Use Case**: Complete ticket investigation - combines ticket, comments, audits, stakeholder info, and recommendations.

## 📚 **Knowledge Base Integration**

### Check Help Center Status (Diagnostic)
```
Request: check_help_center_status
Arguments: {}
```
**Use Case**: Troubleshooting - diagnose Help Center availability and configuration issues before searching for articles.

### Search Help Center Articles
```
Request: search_help_center
Arguments: {
  "query": "password reset",
  "locale": "en-us"
}
```
**Use Case**: Agent assistance - find relevant help articles to share with customers.

### Search Articles in Specific Category
```
Request: search_help_center
Arguments: {
  "query": "billing",
  "locale": "en-us",
  "category_id": 12345
}
```
**Use Case**: Focused search - find billing-related articles within specific category.

### Get Articles by Section
```
Request: get_help_center_articles
Arguments: {
  "section_id": 67890
}
```
**Use Case**: Content management - review all articles in specific help section.

### Get Articles by Category
```
Request: get_help_center_articles
Arguments: {
  "category_id": 12345
}
```
**Use Case**: Content audit - get all articles in category for content review and updates.

### Get All Available Articles
```
Request: get_help_center_articles
Arguments: {}
```
**Use Case**: Complete audit - list all published articles for content management and organization.

## 🔍 **Audit and Compliance**

### Get Complete Ticket Audit History
```
Request: get_ticket_audits
Arguments: {
  "ticket_id": 12345
}
```
**Use Case**: Compliance review - detailed audit trail for important ticket investigation.

### Get Ticket Events Timeline
```
Request: get_ticket_events
Arguments: {
  "ticket_id": 12345
}
```
**Use Case**: Timeline analysis - chronological view of all changes and activities on ticket.

## 👥 **Collaboration Features**

### Add Collaborators to Ticket
```
Request: add_ticket_collaborators
Arguments: {
  "ticket_id": 12345,
  "email_addresses": ["manager@company.com", "specialist@company.com"]
}
```
**Use Case**: Stakeholder involvement - add relevant team members to important ticket discussions.

### Get Current Collaborators
```
Request: get_ticket_collaborators
Arguments: {
  "ticket_id": 12345
}
```
**Use Case**: Communication management - see who is currently included in ticket communications.

### Remove Collaborators
```
Request: remove_ticket_collaborators
Arguments: {
  "ticket_id": 12345,
  "user_ids": [98765, 87654]
}
```
**Use Case**: Access control - remove users who no longer need access to ticket updates.

## 📊 **Advanced Reporting**

### Get Incremental Ticket Updates
```
Request: get_incremental_tickets
Arguments: {
  "start_time": 1704067200
}
```
**Use Case**: Data synchronization - efficiently sync ticket data with external systems.

### Get Detailed Ticket Metrics
```
Request: get_ticket_metrics_detailed
Arguments: {
  "ticket_id": 12345
}
```
**Use Case**: Performance analysis - deep dive into specific ticket's SLA and timing metrics.

### Generate Agent Activity Report
```
Request: generate_agent_activity_report
Arguments: {
  "agent_id": 98765432,
  "start_date": "2025-01-01",
  "end_date": "2025-01-31"
}
```
**Use Case**: Performance review - comprehensive monthly activity report for agent evaluation.

## 🔄 **Common Workflow Examples**

### Daily Team Standup Workflow
```
1. Check at-risk tickets: get_at_risk_tickets (time_horizon: 4)
2. Review workload: get_agent_workload_analysis
3. Suggest reassignments: suggest_ticket_reassignment (criteria: "workload_balance")
4. Check team performance: get_team_performance_dashboard (period: "week")
```

### Monthly Performance Review
```
1. Generate agent scorecards: generate_agent_scorecard (each agent, period: "month")
2. SLA compliance: get_sla_compliance_report (monthly range)
3. Team dashboard: get_team_performance_dashboard (period: "month")
4. Export data: export_search_results (solved tickets for reporting)
```

### Customer Escalation Workflow
```
1. Find related tickets: get_ticket_related_tickets
2. Get organization details: get_organization_details
3. Add stakeholders: add_ticket_collaborators
4. Escalate ticket: escalate_ticket (level: "manager")
5. Apply urgency macro: apply_macro_to_ticket
```

### New Customer Onboarding
```
1. Create organization: update_organization (if needed)
2. Create user: create_user
3. Get user identities: get_user_identities
4. Search help articles: search_help_center (for onboarding materials)
```

### Bulk Ticket Management
```
1. Search tickets: advanced_search (specific criteria)
2. Auto-categorize: auto_categorize_tickets
3. Bulk update: bulk_update_tickets (status, assignments, etc.)
4. Add tags: add_ticket_tags (for tracking)
```

---

**💡 Pro Tips:**
- Combine multiple tools for complex workflows
- Use export functions for external reporting
- Leverage automation tools for efficiency
- Monitor SLA compliance proactively
- Use audit trails for compliance and learning 