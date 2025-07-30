import json
import logging
from typing import Dict, Any, List, Optional, TypeVar, Generic, Union
from dataclasses import dataclass
import urllib.parse
from datetime import datetime
from zenpy import Zenpy
from zenpy.lib.api_objects import Comment
from cachetools import TTLCache

T = TypeVar('T')

@dataclass
class PaginatedResponse(Generic[T]):
    """Base class for paginated responses with metadata"""
    data: T
    total_count: int
    page_size: int
    current_page: int
    has_more: bool
    next_cursor: Optional[str]
    estimated_size: int
    summary: Dict[str, Any]
    metadata: Dict[str, Any]

    @classmethod
    def create(cls, 
               data: T,
               total_count: int,
               page_size: int,
               current_page: int = 1,
               next_cursor: Optional[str] = None,
               summary: Optional[Dict[str, Any]] = None,
               metadata: Optional[Dict[str, Any]] = None) -> 'PaginatedResponse[T]':
        """Factory method to create a paginated response with calculated fields"""
        if isinstance(data, list):
            estimated_size = len(str(data)) if data else 0
        else:
            estimated_size = len(str(data))
            
        has_more = (current_page * page_size) < total_count
        
        return cls(
            data=data,
            total_count=total_count,
            page_size=page_size,
            current_page=current_page,
            has_more=has_more,
            next_cursor=next_cursor,
            estimated_size=estimated_size,
            summary=summary or {},
            metadata=metadata or {}
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert the response to a dictionary format"""
        return {
            'data': self.data,
            'pagination': {
                'total_count': self.total_count,
                'page_size': self.page_size,
                'current_page': self.current_page,
                'has_more': self.has_more,
                'next_cursor': self.next_cursor
            },
            'metadata': {
                'estimated_size': self.estimated_size,
                **self.metadata
            },
            'summary': self.summary
        }


class ZendeskClient:
    def __init__(self, subdomain: str, email: str, token: str):
        """
        Initialize the Zendesk client using zenpy lib.
        """
        if not subdomain or not email or not token:
            raise ValueError("Missing required Zendesk credentials. Please check ZENDESK_SUBDOMAIN, ZENDESK_EMAIL, and ZENDESK_API_KEY environment variables.")
        
        # Ensure subdomain doesn't include .zendesk.com (zenpy adds it automatically)
        if '.zendesk.com' in subdomain:
            subdomain = subdomain.replace('.zendesk.com', '')
            
        self.client = Zenpy(
            subdomain=subdomain,
            email=email,
            token=token
        )
        self.subdomain = subdomain
        
        # Response optimization settings
        self.MAX_RESPONSE_LENGTH = 2000
        self.DEFAULT_LIMIT = 10
        self.MAX_LIMIT = 20

    # =====================================
    # OPTIMIZATION AND CATEGORIZATION UTILITIES
    # =====================================
    
    def _categorize_ticket(self, ticket: Any) -> str:
        """Categorize individual ticket based on content"""
        subject = str(getattr(ticket, 'subject', '')).lower()
        description = str(getattr(ticket, 'description', '')).lower()
        tags = [t.lower() for t in getattr(ticket, 'tags', [])]
        tags_str = ' '.join(tags)
        combined = f"{subject} {description} {tags_str}"
        
        # Define category patterns
        categories = {
            'web_crawl_mirrorweb': ['mirrorweb', 'web', 'crawl', 'spider', 'qa:'],
            'email_archiving': ['email', 'domain', 'missing archive', 'archive'],
            'access_dashboard': ['access', 'login', 'dashboard', 'unable', '404'],
            'backup_cloud': ['backup', 'cloud', 'onedrive', 'failed'],
            'onboarding': ['onboarding', 'setup', 'new', 'welcome'],
            'technical_issue': ['error', 'bug', 'crash', 'not working'],
            'feature_request': ['feature', 'enhancement', 'request', 'would like'],
            'billing': ['billing', 'invoice', 'payment', 'charge'],
            'urgent_support': ['urgent', 'emergency', 'critical', 'production down']
        }
        
        for category, terms in categories.items():
            if any(term in combined for term in terms):
                return category
                
        return 'other'
    
    def _estimate_response_size(self, data: Any) -> int:
        """Estimate JSON response size in bytes"""
        try:
            return len(json.dumps(data, default=str))
        except:
            # Fallback for non-serializable objects
            return len(str(data))
    
    def _create_truncated_response(
        self,
        data: Dict[str, Any],
        items_key: str,
        max_size: int,
        page: int = 1,
        total_items: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Intelligently truncate response when it exceeds max size.
        
        Args:
            data: Original response dictionary
            items_key: Key containing the list of items to truncate
            max_size: Maximum allowed response size
            page: Current page number
            total_items: Total number of items (if known)
        """
        # Calculate base response size without items
        base_data = {k: v for k, v in data.items() if k != items_key}
        base_size = self._estimate_response_size(base_data)
        
        # Reserve space for pagination and truncation info
        available_size = max_size - base_size - 500
        
        items = data.get(items_key, [])
        if not items:
            return data
            
        # Calculate optimal number of items
        items_to_include = []
        current_size = 0
        
        for item in items:
            item_size = self._estimate_response_size(item)
            if current_size + item_size > available_size:
                break
            items_to_include.append(item)
            current_size += item_size
        
        # Create paginated response
        return PaginatedResponse.create(
            data={items_key: items_to_include},
            total_count=total_items or len(items),
            page_size=len(items_to_include),
            current_page=page,
            next_cursor=str(items_to_include[-1]['id']) if items_to_include else None,
            summary=self._generate_summary(items),
            metadata={
                **base_data,
                'truncation_info': {
                    'truncated': len(items_to_include) < len(items),
                    'showing': len(items_to_include),
                    'total_found': len(items),
                    'estimated_response_size': current_size + base_size,
                    'max_allowed_size': max_size
                }
            }
        ).to_dict()
    
    def _limit_response_size(self, data: Any, max_length: int = None) -> Union[str, Dict[str, Any]]:
        """
        Smart response size limiting with pagination and metadata.
        Returns either a JSON string for simple responses or a PaginatedResponse for complex data.
        """
        if max_length is None:
            max_length = self.MAX_RESPONSE_LENGTH

        # Handle PaginatedResponse objects
        if isinstance(data, PaginatedResponse):
            return data.to_dict()
            
        # Convert to string for size estimation
        response = json.dumps(data, indent=2)
        response_length = len(response)
        
        # If response is small enough, return as is
        if response_length <= max_length:
            return response

        # For list data, create paginated response
        if isinstance(data, list):
            total_items = len(data)
            page_size = self._calculate_optimal_page_size(data, max_length)
            first_page = data[:page_size]
            
            return PaginatedResponse.create(
                data=first_page,
                total_count=total_items,
                page_size=page_size,
                summary=self._generate_summary(data),
                metadata={
                    'total_size': response_length,
                    'truncated_size': len(json.dumps(first_page, indent=2))
                }
            ).to_dict()
            
        # For dict data with known list fields
        elif isinstance(data, dict):
            for key in ['tickets', 'users', 'organizations', 'results']:
                if key in data and isinstance(data[key], list):
                    items = data[key]
                    total_items = len(items)
                    page_size = self._calculate_optimal_page_size(items, max_length)
                    first_page = items[:page_size]
                    
                    # Preserve other dict fields in metadata
                    metadata = {k: v for k, v in data.items() if k != key}
                    metadata.update({
                        'total_size': response_length,
                        'truncated_size': len(json.dumps(first_page, indent=2))
                    })
                    
                    return PaginatedResponse.create(
                        data={key: first_page},
                        total_count=total_items,
                        page_size=page_size,
                        summary=self._generate_summary(items),
                        metadata=metadata
                    ).to_dict()
        
        # Fallback to simple truncation for other cases
        truncated = response[:max_length-200]
        last_newline = truncated.rfind('\n')
        if last_newline > max_length * 0.8:
            truncated = truncated[:last_newline]
            
        return truncated + f"\n\n... (truncated, {response_length - len(truncated)} characters omitted)"
    
    def _calculate_optimal_page_size(self, data: List[Any], max_length: int) -> int:
        """
        Calculate optimal page size based on data size and max length.
        """
        if not data:
            return self.DEFAULT_LIMIT
            
        # Estimate size per item
        sample_item = data[0]
        item_size = len(json.dumps(sample_item, indent=2))
        
        # Calculate how many items we can fit
        # Account for pagination metadata overhead (roughly 200 chars)
        available_space = max_length - 200
        optimal_size = max(1, min(
            len(data),  # Don't exceed total items
            available_space // item_size,  # Size-based limit
            self.MAX_LIMIT  # Hard limit
        ))
        
        return optimal_size
        
    def _generate_summary(self, data: List[Any]) -> Dict[str, Any]:
        """
        Generate a summary of the full dataset.
        """
        if not data:
            return {}
            
        summary: Dict[str, Any] = {
            'total_items': len(data)
        }
        
        # For tickets
        if hasattr(data[0], 'status'):
            status_counts = {}
            priority_counts = {}
            for item in data:
                status = getattr(item, 'status', 'unknown')
                priority = getattr(item, 'priority', 'none')
                status_counts[status] = status_counts.get(status, 0) + 1
                priority_counts[priority] = priority_counts.get(priority, 0) + 1
            summary.update({
                'status_distribution': status_counts,
                'priority_distribution': priority_counts
            })
            
        # For users
        elif hasattr(data[0], 'role'):
            role_counts = {}
            for item in data:
                role = getattr(item, 'role', 'unknown')
                role_counts[role] = role_counts.get(role, 0) + 1
            summary['role_distribution'] = role_counts
            
        return summary
        
    def _count_items(self, data: Any) -> str:
        """Count items in response data for truncation messages."""
        if isinstance(data, dict):
            if 'tickets' in data:
                return f"{len(data['tickets'])} tickets"
            elif 'users' in data:
                return f"{len(data['users'])} users"
            elif 'organizations' in data:
                return f"{len(data['organizations'])} organizations"
            elif isinstance(data.get('results'), list):
                return f"{len(data['results'])} items"
        elif isinstance(data, list):
            return f"{len(data)} items"
        return "multiple items"
    
    def _apply_limit(self, limit: Optional[int], default: int = None) -> int:
        """Apply and validate limit parameters."""
        if default is None:
            default = self.DEFAULT_LIMIT
            
        if limit is None:
            return default
        return min(limit, self.MAX_LIMIT)
    
    def _compact_ticket(self, ticket: Any) -> Dict[str, Any]:
        """
        Convert ticket to compact format with only essential fields.
        """
        subject = getattr(ticket, 'subject', 'No subject')
        if len(subject) > 50:
            subject = subject[:47] + "..."
            
        return {
            'id': getattr(ticket, 'id', None),
            'subject': subject,
            'status': getattr(ticket, 'status', None),
            'priority': getattr(ticket, 'priority', None),
            'created_at': getattr(ticket, 'created_at', None),
            'assignee_id': getattr(ticket, 'assignee_id', None)
        }
    
    def _compact_user(self, user: Any) -> Dict[str, Any]:
        """Convert user to compact format."""
        return {
            'id': getattr(user, 'id', None),
            'name': getattr(user, 'name', 'Unknown'),
            'email': getattr(user, 'email', 'Unknown'),
            'role': getattr(user, 'role', 'Unknown'),
            'active': getattr(user, 'active', True)
        }
    
    def _compact_organization(self, org: Any) -> Dict[str, Any]:
        """Convert organization to compact format."""
        return {
            'id': getattr(org, 'id', None),
            'name': getattr(org, 'name', 'Unknown'),
            'created_at': getattr(org, 'created_at', None)
        }

    # =====================================
    # SMART SUMMARIZATION FUNCTIONS
    # =====================================
    
    def summarize_tickets(self, tickets: List[Any]) -> Dict[str, Any]:
        """
        Create smart summary of ticket data showing key metrics only.
        """
        if not tickets:
            return {"summary": "No tickets found", "count": 0}
            
        # Count by status
        status_counts = {}
        priority_counts = {}
        assignee_counts = {}
        
        for ticket in tickets:
            status = getattr(ticket, 'status', 'unknown')
            status_counts[status] = status_counts.get(status, 0) + 1
            
            priority = getattr(ticket, 'priority', 'normal')
            priority_counts[priority] = priority_counts.get(priority, 0) + 1
            
            assignee_id = getattr(ticket, 'assignee_id', None)
            if assignee_id:
                assignee_counts[assignee_id] = assignee_counts.get(assignee_id, 0) + 1
        
        return {
            "summary": f"Found {len(tickets)} tickets",
            "count": len(tickets),
            "status_breakdown": status_counts,
            "priority_distribution": priority_counts,
            "top_assigned_agents": dict(list(sorted(assignee_counts.items(), key=lambda x: x[1], reverse=True))[:5]),
            "recommendations": self._generate_ticket_recommendations(status_counts, priority_counts)
        }
    
    def summarize_agent_performance(self, performance_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create executive summary of agent performance data.
        """
        if 'error' in performance_data:
            return performance_data
            
        top_performers = performance_data.get('top_performers', [])
        if not top_performers:
            return {"summary": "No performance data available"}
            
        total_tickets = performance_data.get('total_tickets_analyzed', 0)
        total_agents = performance_data.get('total_agents', 0)
        
        # Key insights
        best_performer = top_performers[0] if top_performers else None
        avg_tickets = total_tickets / total_agents if total_agents > 0 else 0
        
        return {
            "summary": f"Performance analysis for {total_agents} agents over {performance_data.get('period_days', 'N/A')} days",
            "key_metrics": {
                "total_tickets_solved": total_tickets,
                "active_agents": total_agents,
                "avg_tickets_per_agent": round(avg_tickets, 1),
                "top_performer": best_performer.get('name', 'Unknown') if best_performer else None,
                "top_performer_tickets": best_performer.get('tickets_solved', 0) if best_performer else 0
            },
            "insights": [
                f"Top 3 agents solved {sum(p.get('tickets_solved', 0) for p in top_performers[:3])} tickets",
                f"Average {round(avg_tickets, 1)} tickets per agent",
                "Use get_agent_performance_metrics for detailed analysis"
            ]
        }
    
    def summarize_workload(self, workload_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create executive summary of workload distribution.
        """
        if 'error' in workload_data:
            return workload_data
            
        summary = workload_data.get('summary', {})
        alerts = workload_data.get('workload_alerts', {})
        
        return {
            "summary": f"Workload analysis: {summary.get('total_active_tickets', 0)} tickets across {summary.get('total_agents', 0)} agents",
            "key_metrics": {
                "total_active_tickets": summary.get('total_active_tickets', 0),
                "avg_per_agent": summary.get('avg_tickets_per_agent', 0),
                "unassigned_tickets": summary.get('unassigned_tickets', 0),
                "overdue_tickets": summary.get('total_overdue_tickets', 0)
            },
            "alerts": {
                "overloaded_agents": len(alerts.get('overloaded_agents', [])),
                "underloaded_agents": len(alerts.get('underloaded_agents', [])),
                "agents_with_overdue": len(alerts.get('agents_with_overdue', []))
            },
            "recommendations": workload_data.get('recommendations', [])[:3],
            "note": "Use get_agent_workload_analysis for detailed breakdown"
        }
    
    def _generate_ticket_recommendations(self, status_counts: Dict, priority_counts: Dict) -> List[str]:
        """Generate actionable recommendations based on ticket data."""
        recommendations = []
        
        open_tickets = status_counts.get('open', 0) + status_counts.get('new', 0)
        if open_tickets > 20:
            recommendations.append(f"High open ticket count ({open_tickets}) - consider load balancing")
            
        urgent_tickets = priority_counts.get('urgent', 0)
        if urgent_tickets > 5:
            recommendations.append(f"Multiple urgent tickets ({urgent_tickets}) need immediate attention")
            
        pending_tickets = status_counts.get('pending', 0)
        if pending_tickets > 10:
            recommendations.append(f"Review {pending_tickets} pending tickets for stalled progress")
            
        return recommendations[:3]

    # =====================================
    # RESPONSE FORMATTING UTILITIES
    # =====================================
    
    def format_as_readable_summary(self, data: Dict[str, Any], title: str = "Results") -> str:
        """
        Format data as readable text summary instead of JSON dump.
        """
        lines = [f"📊 {title}", "=" * (len(title) + 2)]
        
        if 'summary' in data:
            lines.append(f"• {data['summary']}")
            lines.append("")
        
        if 'key_metrics' in data:
            lines.append("Key Metrics:")
            for key, value in data['key_metrics'].items():
                formatted_key = key.replace('_', ' ').title()
                lines.append(f"  • {formatted_key}: {value}")
            lines.append("")
        
        if 'status_breakdown' in data:
            lines.append("Status Distribution:")
            for status, count in data['status_breakdown'].items():
                lines.append(f"  • {status.title()}: {count}")
            lines.append("")
        
        if 'recommendations' in data and data['recommendations']:
            lines.append("📋 Recommendations:")
            for i, rec in enumerate(data['recommendations'][:3], 1):
                lines.append(f"  {i}. {rec}")
            lines.append("")
        
        if 'note' in data:
            lines.append(f"ℹ️  {data['note']}")
        
        result = "\n".join(lines)
        
        # Ensure it fits within response limits
        if len(result) > self.MAX_RESPONSE_LENGTH:
            return result[:self.MAX_RESPONSE_LENGTH-50] + "\n\n... (summary truncated)"
            
        return result

    def get_ticket(self, ticket_id: int) -> Dict[str, Any]:
        """
        Query a ticket by its ID
        """
        try:
            ticket = self.client.tickets(id=ticket_id)
            return {
                'id': ticket.id,
                'subject': ticket.subject,
                'description': ticket.description,
                'status': ticket.status,
                'priority': ticket.priority,
                'created_at': str(ticket.created_at),
                'updated_at': str(ticket.updated_at),
                'requester_id': ticket.requester_id,
                'assignee_id': ticket.assignee_id,
                'organization_id': ticket.organization_id
            }
        except Exception as e:
            raise Exception(f"Failed to get ticket {ticket_id}: {str(e)}")

    def get_ticket_comments(self, ticket_id: int, limit: int = 10, include_body: bool = True, max_body_length: int = 300) -> List[Dict[str, Any]]:
        """
        Get comments for a specific ticket with data limits to avoid conversation overflow.
        
        Args:
            ticket_id: The ticket ID
            limit: Maximum number of comments to return (default: 10)
            include_body: Whether to include comment body (default: True)
            max_body_length: Maximum length of comment body (default: 300)
        """
        try:
            comments = list(self.client.tickets.comments(ticket=ticket_id))
            
            # Sort by creation date (newest first) and limit
            comments.sort(key=lambda c: getattr(c, 'created_at', ''), reverse=True)
            limited_comments = comments[:limit]
            
            result = []
            for comment in limited_comments:
                comment_data = {
                    'id': getattr(comment, 'id', None),
                    'author_id': getattr(comment, 'author_id', None),
                    'public': getattr(comment, 'public', True),
                    'created_at': str(getattr(comment, 'created_at', ''))
                }
                
                if include_body:
                    body = getattr(comment, 'body', '')
                    if len(body) > max_body_length:
                        body = body[:max_body_length] + "... [truncated]"
                    comment_data['body'] = body
                    
                    # Only include html_body if it's different and short
                    html_body = getattr(comment, 'html_body', '')
                    if html_body and html_body != body and len(html_body) <= max_body_length:
                        comment_data['html_body'] = html_body
                
                result.append(comment_data)
            
            return result
        except Exception as e:
            raise Exception(f"Failed to get comments for ticket {ticket_id}: {str(e)}")

    def post_comment(self, ticket_id: int, comment: str, public: bool = True) -> str:
        """
        Post a comment to an existing ticket.
        """
        try:
            ticket = self.client.tickets(id=ticket_id)
            ticket.comment = Comment(
                html_body=comment,
                public=public
            )
            self.client.tickets.update(ticket)
            return comment
        except Exception as e:
            raise Exception(f"Failed to post comment on ticket {ticket_id}: {str(e)}")

    def search_tickets(
        self,
        query: str,
        limit: int = 20,
        compact: bool = True,
        include_description: bool = False,
        sort_by: str = "created_at",
        sort_order: str = "desc",
        max_response_size: Optional[int] = None,
        summary_mode: bool = False,
        categorize: bool = False,
        page: int = 1,
        cursor: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Unified ticket search with intelligent response management.
        
        Args:
            query: Zendesk search query string
            limit: Maximum tickets to return (1-100)
            compact: Return minimal data for better performance
            include_description: Include full ticket descriptions
            sort_by: Field to sort by (created_at, updated_at, priority, status)
            sort_order: Sort direction (asc/desc)
            max_response_size: Auto-truncate if response exceeds this size
            summary_mode: Return summary statistics instead of full tickets
            categorize: Add automatic categorization to results
            page: Page number for pagination
            cursor: Cursor for continuing from previous results
            
        Returns:
            Intelligent response based on parameters and data size:
            - Full results when within size limits
            - Truncated results with pagination when too large
            - Summary statistics when summary_mode=True
            - Category analysis when categorize=True
        """
        try:
            # Set defaults
            if max_response_size is None:
                max_response_size = self.MAX_RESPONSE_LENGTH
            
            # Ensure valid page and limit
            page = max(1, page)
            limit = min(max(1, limit), 100)  # Allow up to 100 items
            
            # Ensure the query includes type:ticket
            if "type:ticket" not in query:
                query = f"type:ticket {query}"
            
            # Execute search
            search_results = self.client.search(
                query=query,
                sort_by=sort_by,
                sort_order=sort_order
            )
            
            # Convert generator to list
            all_tickets = list(search_results)
            total_tickets = len(all_tickets)
            
            # Handle summary mode for large datasets
            if summary_mode:
                summary = self.summarize_tickets(all_tickets)
                summary.update({
                    'query': query,
                    'total_tickets': total_tickets,
                    'status_distribution': self._count_by_field(all_tickets, 'status'),
                    'priority_distribution': self._count_by_field(all_tickets, 'priority'),
                    'sample_tickets': [
                        self._compact_ticket(t) for t in all_tickets[:5]
                    ]
                })
                if categorize:
                    summary['category_distribution'] = self._count_by_category(all_tickets)
                return summary
            
            # Calculate pagination
            start_idx = (page - 1) * limit
            end_idx = start_idx + limit
            page_tickets = all_tickets[start_idx:end_idx]
            
            # Process tickets
            processed_tickets = []
            for ticket in page_tickets:
                if compact:
                    ticket_data = self._compact_ticket(ticket)
                else:
                    ticket_data = {
                        'id': getattr(ticket, 'id', None),
                        'subject': getattr(ticket, 'subject', 'No subject'),
                        'status': getattr(ticket, 'status', None),
                        'priority': getattr(ticket, 'priority', None),
                        'created_at': getattr(ticket, 'created_at', None),
                        'updated_at': getattr(ticket, 'updated_at', None),
                        'requester_id': getattr(ticket, 'requester_id', None),
                        'assignee_id': getattr(ticket, 'assignee_id', None),
                        'organization_id': getattr(ticket, 'organization_id', None),
                        'tags': getattr(ticket, 'tags', [])
                    }
                    
                    if include_description:
                        description = getattr(ticket, 'description', '')
                        ticket_data['description'] = description
                
                if categorize:
                    ticket_data['category'] = self._categorize_ticket(ticket)
                    
                processed_tickets.append(ticket_data)
            
            # Build response with all metadata
            result = {
                'tickets': processed_tickets,
                'total_found': total_tickets,
                'query': query,
                'parameters': {
                    'compact': compact,
                    'limit': limit,
                    'page': page,
                    'sort_by': sort_by,
                    'include_description': include_description,
                    'categorize': categorize
                }
            }
            
            # Add category summary if requested
            if categorize:
                result['category_summary'] = self._count_by_category(all_tickets)
            
            # Handle size management
            estimated_size = self._estimate_response_size(result)
            if estimated_size > max_response_size:
                return self._create_truncated_response(
                    data=result,
                    items_key='tickets',
                    max_size=max_response_size,
                    page=page,
                    total_items=total_tickets
                )
            
            # Calculate next cursor
            if end_idx < total_tickets and processed_tickets:
                result['next_cursor'] = str(processed_tickets[-1]['id'])
            
            return result
            
        except Exception as e:
            error_msg = str(e)
            if "SSL" in error_msg or "ssl" in error_msg.lower():
                raise Exception(f"SSL connection error. Check your ZENDESK_SUBDOMAIN setting. Original error: {error_msg}")
            elif "401" in error_msg or "authentication" in error_msg.lower():
                raise Exception(f"Authentication failed. Check your ZENDESK_EMAIL and ZENDESK_API_KEY. Original error: {error_msg}")
            elif "403" in error_msg or "permission" in error_msg.lower():
                raise Exception(f"Permission denied. Your API token may not have search permissions. Original error: {error_msg}")
            else:
                raise Exception(f"Search failed: {error_msg}")
                
    def _count_by_field(self, items: List[Any], field: str) -> Dict[str, int]:
        """Count items by a specific field value"""
        counts: Dict[str, int] = {}
        for item in items:
            value = str(getattr(item, field, 'unknown'))
            counts[value] = counts.get(value, 0) + 1
        return counts
        
    def _count_by_category(self, tickets: List[Any]) -> Dict[str, int]:
        """Count tickets by their categories"""
        counts: Dict[str, int] = {}
        for ticket in tickets:
            category = self._categorize_ticket(ticket)
            counts[category] = counts.get(category, 0) + 1
        return counts

    def get_ticket_counts(self) -> Dict[str, Any]:
        """
        Get counts of tickets by various categories.
        """
        try:
            counts = {}
            
            # Get total ticket count using the count API
            try:
                total_count = self.client.tickets.count()
                counts['total'] = total_count.value if hasattr(total_count, 'value') else 0
            except:
                counts['total'] = 0
            
            # Count by status using more efficient search with count only
            status_counts = {}
            for status in ['new', 'open', 'pending', 'hold', 'solved', 'closed']:
                try:
                    # Use search but limit to 1 result and just count
                    search_results = self.client.search(query=f"type:ticket status:{status}")
                    # Convert to list and get length - this is more reliable than count
                    result_list = list(search_results)
                    status_counts[status] = len(result_list)
                except Exception as e:
                    # If individual status search fails, set to 0
                    status_counts[status] = 0
            
            counts['by_status'] = status_counts
            
            # Count by priority - similar approach
            priority_counts = {}
            for priority in ['low', 'normal', 'high', 'urgent']:
                try:
                    search_results = self.client.search(query=f"type:ticket priority:{priority}")
                    result_list = list(search_results)
                    priority_counts[priority] = len(result_list)
                except Exception as e:
                    priority_counts[priority] = 0
            
            counts['by_priority'] = priority_counts
            
            # Add some recent activity counts
            try:
                recent_tickets = self.client.search(query="type:ticket created>7days")
                recent_list = list(recent_tickets)
                counts['recent_7_days'] = len(recent_list)
            except:
                counts['recent_7_days'] = 0
                
            try:
                updated_today = self.client.search(query="type:ticket updated>24hours")
                updated_list = list(updated_today)
                counts['updated_today'] = len(updated_list)
            except:
                counts['updated_today'] = 0
            
            return counts
        except Exception as e:
            # Return basic structure even if everything fails
            return {
                'total': 0,
                'by_status': {'new': 0, 'open': 0, 'pending': 0, 'hold': 0, 'solved': 0, 'closed': 0},
                'by_priority': {'low': 0, 'normal': 0, 'high': 0, 'urgent': 0},
                'recent_7_days': 0,
                'updated_today': 0,
                'error': f"Failed to get ticket counts: {str(e)}"
            }

    def get_ticket_metrics(self, ticket_id: Optional[int] = None, summarize: bool = True) -> Dict[str, Any]:
        """
        Get ticket metrics for analysis. If ticket_id provided, get metrics for that ticket,
        otherwise get aggregate metrics.
        
        Args:
            ticket_id: Specific ticket ID (optional)
            summarize: Return key numbers only (default: True)
        """
        try:
            if ticket_id:
                # Get metrics for specific ticket
                try:
                    ticket_metric = self.client.tickets.metrics(ticket=ticket_id)
                    return {
                        'ticket_id': ticket_id,
                        'assignee_updated_at': str(getattr(ticket_metric, 'assignee_updated_at', '')),
                        'initially_assigned_at': str(getattr(ticket_metric, 'initially_assigned_at', '')),
                        'latest_comment_added_at': str(getattr(ticket_metric, 'latest_comment_added_at', '')),
                        'reopens': getattr(ticket_metric, 'reopens', 0),
                        'replies': getattr(ticket_metric, 'replies', 0),
                        'assignee_stations': getattr(ticket_metric, 'assignee_stations', 0),
                        'group_stations': getattr(ticket_metric, 'group_stations', 0)
                    }
                except:
                    return {'error': f'No metrics found for ticket {ticket_id}'}
            else:
                # Get aggregate metrics from recent tickets
                metrics = {
                    'recent_tickets_count': 0,
                    'avg_replies': 0,
                    'avg_reopens': 0,
                    'total_replies': 0,
                    'total_reopens': 0
                }
                
                # Get recent tickets for analysis
                recent_tickets = list(self.client.search(query="type:ticket created>7days", sort_by="created_at"))
                metrics['recent_tickets_count'] = len(recent_tickets)
                
                if recent_tickets:
                    total_replies = 0
                    total_reopens = 0
                    valid_metrics = 0
                    
                    for ticket in recent_tickets[:50]:  # Limit to avoid rate limits
                        try:
                            ticket_metric = self.client.tickets.metrics(ticket=ticket.id)
                            replies = getattr(ticket_metric, 'replies', 0)
                            reopens = getattr(ticket_metric, 'reopens', 0)
                            total_replies += replies
                            total_reopens += reopens
                            valid_metrics += 1
                        except:
                            continue
                    
                    if valid_metrics > 0:
                        metrics['avg_replies'] = round(total_replies / valid_metrics, 2)
                        metrics['avg_reopens'] = round(total_reopens / valid_metrics, 2)
                        metrics['total_replies'] = total_replies
                        metrics['total_reopens'] = total_reopens
                        metrics['analyzed_tickets'] = valid_metrics
                
                # Return summary if requested
                if summarize and not ticket_id:
                    summary = {
                        "summary": f"Recent metrics from {metrics['recent_tickets_count']} tickets",
                        "key_numbers": {
                            "avg_replies_per_ticket": metrics["avg_replies"],
                            "avg_reopens_per_ticket": metrics["avg_reopens"],
                            "total_replies": metrics["total_replies"],
                            "tickets_analyzed": metrics.get("analyzed_tickets", 0)
                        },
                        "note": "Use summarize=False for detailed metrics"
                    }
                    return summary
                
                return metrics
        except Exception as e:
            raise Exception(f"Failed to get ticket metrics: {str(e)}")

    def get_user_tickets(self, user_id: int, ticket_type: str = "requested", compact: bool = True, limit: Optional[int] = None, summarize: bool = False) -> Dict[str, Any]:
        """
        Get tickets for a specific user.
        
        Args:
            user_id: User ID
            ticket_type: Type of tickets (requested, ccd, assigned)
            compact: Return minimal data for better performance (default: True)
            limit: Maximum number of tickets to return (default: 10, max: 20)
            summarize: Return summary instead of full ticket list
        """
        try:
            # Apply limit
            limit = self._apply_limit(limit)
            
            if ticket_type == "requested":
                all_tickets = list(self.client.users.tickets.requested(user=user_id))
            elif ticket_type == "ccd":
                all_tickets = list(self.client.users.tickets.ccd(user=user_id))
            elif ticket_type == "assigned":
                all_tickets = list(self.client.users.tickets.assigned(user=user_id))
            else:
                raise ValueError(f"Invalid ticket_type: {ticket_type}")
            
            # Apply limit
            limited_tickets = all_tickets[:limit]
            
            tickets = []
            for ticket in limited_tickets:
                if compact:
                    tickets.append(self._compact_ticket(ticket))
                else:
                    tickets.append({
                        'id': ticket.id,
                        'subject': ticket.subject,
                        'status': ticket.status,
                        'priority': ticket.priority,
                        'created_at': str(ticket.created_at),
                        'updated_at': str(ticket.updated_at),
                        'assignee_id': getattr(ticket, 'assignee_id', None),
                        'requester_id': getattr(ticket, 'requester_id', None)
                    })
            
            response_data = {
                "user_id": user_id,
                "ticket_type": ticket_type,
                "total_tickets": len(all_tickets),
                "showing": len(tickets),
                "compact_mode": compact,
                "tickets": tickets
            }
            
            if len(all_tickets) > limit:
                response_data["note"] = f"Showing first {limit} of {len(all_tickets)} {ticket_type} tickets."
            
            if summarize:
                summary = self.summarize_tickets(tickets)
                summary.update({
                    "user_id": user_id,
                    "ticket_type": ticket_type,
                    "total_tickets": len(all_tickets)
                })
                return summary
                
            return response_data
            
        except Exception as e:
            raise Exception(f"Failed to get {ticket_type} tickets for user {user_id}: {str(e)}")

    def get_organization_tickets(self, org_id: int, compact: bool = True, limit: Optional[int] = None, summarize: bool = False) -> Dict[str, Any]:
        """
        Get all tickets for a specific organization.
        
        Args:
            org_id: Organization ID
            compact: Return minimal data for better performance (default: True)
            limit: Maximum number of tickets to return (default: 10, max: 20)
            summarize: Return summary instead of full ticket list
        """
        try:
            # Apply limit
            limit = self._apply_limit(limit)
            
            all_tickets = list(self.client.organizations.tickets(organization=org_id))
            limited_tickets = all_tickets[:limit]
            
            tickets = []
            for ticket in limited_tickets:
                if compact:
                    tickets.append(self._compact_ticket(ticket))
                else:
                    tickets.append({
                        'id': ticket.id,
                        'subject': ticket.subject,
                        'status': ticket.status,
                        'priority': ticket.priority,
                        'requester_id': ticket.requester_id,
                        'assignee_id': ticket.assignee_id,
                        'created_at': str(ticket.created_at),
                        'updated_at': str(ticket.updated_at)
                    })
            
            response_data = {
                "organization_id": org_id,
                "total_tickets": len(all_tickets),
                "showing": len(tickets),
                "compact_mode": compact,
                "tickets": tickets
            }
            
            if len(all_tickets) > limit:
                response_data["note"] = f"Showing first {limit} of {len(all_tickets)} organization tickets."
            
            if summarize:
                summary = self.summarize_tickets(tickets)
                summary.update({
                    "organization_id": org_id,
                    "total_tickets": len(all_tickets)
                })
                return summary
                
            return response_data
            
        except Exception as e:
            raise Exception(f"Failed to get tickets for organization {org_id}: {str(e)}")

    def get_satisfaction_ratings(self, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Get customer satisfaction ratings.
        """
        try:
            ratings = []
            satisfaction_ratings = self.client.satisfaction_ratings()
            
            count = 0
            for rating in satisfaction_ratings:
                if count >= limit:
                    break
                ratings.append({
                    'id': rating.id,
                    'score': rating.score,
                    'comment': getattr(rating, 'comment', ''),
                    'ticket_id': rating.ticket_id,
                    'assignee_id': rating.assignee_id,
                    'requester_id': rating.requester_id,
                    'created_at': str(rating.created_at)
                })
                count += 1
            
            return ratings
        except Exception as e:
            raise Exception(f"Failed to get satisfaction ratings: {str(e)}")

    def get_all_articles(self) -> Dict[str, Any]:
        """
        Fetch help center articles as knowledge base.
        Returns a Dict of section -> [article].
        """
        try:
            # Get all sections
            sections = self.client.help_center.sections()

            # Get articles for each section
            kb = {}
            for section in sections:
                articles = self.client.help_center.sections.articles(section.id)
                kb[section.name] = {
                    'section_id': section.id,
                    'description': section.description,
                    'articles': [{
                        'id': article.id,
                        'title': article.title,
                        'body': article.body,
                        'updated_at': str(article.updated_at),
                        'url': article.html_url
                    } for article in articles]
                }

            return kb
        except Exception as e:
            raise Exception(f"Failed to fetch knowledge base: {str(e)}")

    def get_user_by_id(self, user_id: int) -> Dict[str, Any]:
        """
        Get user information by user ID.
        Returns user details including name, email, role, etc.
        """
        try:
            user = self.client.users(id=user_id)
            
            return {
                'id': getattr(user, 'id', user_id),
                'name': getattr(user, 'name', 'Unknown'),
                'email': getattr(user, 'email', 'Unknown'),
                'role': getattr(user, 'role', 'Unknown'),
                'active': getattr(user, 'active', True),
                'created_at': getattr(user, 'created_at', None),
                'last_login_at': getattr(user, 'last_login_at', None),
                'time_zone': getattr(user, 'time_zone', None),
                'locale': getattr(user, 'locale', None),
                'organization_id': getattr(user, 'organization_id', None)
            }
        except Exception as e:
            # Try searching for the user as backup
            try:
                search_results = self.client.search(query=f"type:user id:{user_id}")
                user_results = list(search_results)
                if user_results:
                    user = user_results[0]
                    return {
                        'id': getattr(user, 'id', user_id),
                        'name': getattr(user, 'name', f"User {user_id}"),
                        'email': getattr(user, 'email', 'Unknown'),
                        'role': getattr(user, 'role', 'Unknown'),
                        'active': getattr(user, 'active', True),
                        'created_at': getattr(user, 'created_at', None),
                        'last_login_at': getattr(user, 'last_login_at', None),
                        'time_zone': getattr(user, 'time_zone', None),
                        'locale': getattr(user, 'locale', None),
                        'organization_id': getattr(user, 'organization_id', None)
                    }
                else:
                    raise Exception(f"User {user_id} not found")
            except Exception:
                raise Exception(f"Failed to get user {user_id}: {str(e)}")

    def get_agent_performance(self, days: int = 7) -> Dict[str, Any]:
        """
        Get agent performance metrics for the specified number of days.
        Returns minimal data focused on performance metrics.
        """
        try:
            from datetime import datetime, timedelta
            
            # Calculate date range
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days)
            start_date_str = start_date.strftime('%Y-%m-%d')
            
            # Search for tickets updated/solved in the time period
            query = f"updated>{start_date_str} status:solved"
            search_results = self.client.search(query=query)
            
            # Convert to list to work with the data
            tickets = list(search_results)
            
            # Extract minimal data for analysis
            agent_stats = {}
            
            for ticket in tickets:
                assignee_id = getattr(ticket, 'assignee_id', None)
                if not assignee_id:
                    continue
                    
                if assignee_id not in agent_stats:
                    agent_stats[assignee_id] = {
                        'assignee_id': assignee_id,
                        'tickets_solved': 0,
                        'total_priority_score': 0,
                        'ticket_ids': [],
                        'subjects': []  # Keep only subjects for context
                    }
                
                agent_stats[assignee_id]['tickets_solved'] += 1
                agent_stats[assignee_id]['ticket_ids'].append(getattr(ticket, 'id', None))
                
                # Add subject but truncate if too long
                subject = getattr(ticket, 'subject', 'No subject')
                if len(subject) > 80:
                    subject = subject[:77] + "..."
                agent_stats[assignee_id]['subjects'].append(subject)
                
                # Calculate priority score (urgent=4, high=3, normal=2, low=1)
                priority = getattr(ticket, 'priority', 'normal')
                priority_scores = {'urgent': 4, 'high': 3, 'normal': 2, 'low': 1}
                agent_stats[assignee_id]['total_priority_score'] += priority_scores.get(priority, 2)
            
            # Convert to list and sort by tickets solved
            agent_list = list(agent_stats.values())
            agent_list.sort(key=lambda x: x['tickets_solved'], reverse=True)
            
            # Limit to top 10 agents to keep response manageable
            top_agents = agent_list[:10]
            
            # Try to get agent names for the top performers
            for agent in top_agents:
                try:
                    user = self.client.users(id=agent['assignee_id'])
                    agent['name'] = getattr(user, 'name', f"User {agent['assignee_id']}")
                    agent['email'] = getattr(user, 'email', 'Unknown')
                except Exception as e:
                    # If user lookup fails, try searching for the user
                    try:
                        search_results = self.client.search(query=f"type:user id:{agent['assignee_id']}")
                        user_results = list(search_results)
                        if user_results:
                            user = user_results[0]
                            agent['name'] = getattr(user, 'name', f"User {agent['assignee_id']}")
                            agent['email'] = getattr(user, 'email', 'Unknown')
                        else:
                            agent['name'] = f"Agent {agent['assignee_id']}"
                            agent['email'] = 'Unknown'
                    except Exception:
                        agent['name'] = f"Agent {agent['assignee_id']}"
                        agent['email'] = 'Unknown'
                
                # Calculate average priority score
                if agent['tickets_solved'] > 0:
                    agent['avg_priority_score'] = round(agent['total_priority_score'] / agent['tickets_solved'], 2)
                else:
                    agent['avg_priority_score'] = 0
            
            return {
                'period_days': days,
                'period_start': start_date_str,
                'total_tickets_analyzed': len(tickets),
                'total_agents': len(agent_stats),
                'top_performers': top_agents,
                'summary': {
                    'most_tickets': top_agents[0] if top_agents else None,
                    'total_solved_by_top_10': sum(agent['tickets_solved'] for agent in top_agents)
                }
            }
            
        except Exception as e:
            return {
                'error': f"Failed to get agent performance: {str(e)}",
                'period_days': days,
                'total_tickets_analyzed': 0,
                'total_agents': 0,
                'top_performers': []
            }

    def get_agent_performance_metrics(
        self, 
        agent_id: Optional[int] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        include_satisfaction: bool = True,
        summarize: bool = True
    ) -> Dict[str, Any]:
        """
        Get comprehensive agent performance metrics including:
        - Ticket volume and resolution rates
        - Average response/resolution times
        - Customer satisfaction scores
        - SLA compliance
        
        Args:
            agent_id: Specific agent to analyze (optional)
            start_date: Start date for analysis (YYYY-MM-DD)
            end_date: End date for analysis (YYYY-MM-DD)
            include_satisfaction: Include satisfaction data
            summarize: Return summary format (default: True)
        """
        try:
            from datetime import datetime, timedelta
            
            # Set default date range if not provided
            if not end_date:
                end_date = datetime.now().strftime('%Y-%m-%d')
            if not start_date:
                start_date = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
            
            # Build search query
            if agent_id:
                base_query = f"assignee:{agent_id}"
            else:
                base_query = "type:ticket"
            
            date_query = f"{base_query} created>={start_date} created<={end_date}"
            
            # Get all tickets for the period
            all_tickets = list(self.client.search(query=date_query))
            
            # Get solved tickets
            solved_query = f"{date_query} status:solved"
            solved_tickets = list(self.client.search(query=solved_query))
            
            # Calculate metrics
            total_tickets = len(all_tickets)
            solved_count = len(solved_tickets)
            resolution_rate = (solved_count / total_tickets * 100) if total_tickets > 0 else 0
            
            # Calculate response/resolution times
            response_times = []
            resolution_times = []
            
            for ticket in solved_tickets[:50]:  # Limit for performance
                try:
                    ticket_metrics = self.client.ticket_metrics(ticket.id)
                    
                    if hasattr(ticket_metrics, 'reply_time_in_minutes') and ticket_metrics.reply_time_in_minutes:
                        response_times.append(ticket_metrics.reply_time_in_minutes.business_minutes)
                    
                    if hasattr(ticket_metrics, 'full_resolution_time_in_minutes') and ticket_metrics.full_resolution_time_in_minutes:
                        resolution_times.append(ticket_metrics.full_resolution_time_in_minutes.business_minutes)
                except:
                    continue
            
            avg_response_time = sum(response_times) / len(response_times) if response_times else 0
            avg_resolution_time = sum(resolution_times) / len(resolution_times) if resolution_times else 0
            
            metrics = {
                "agent_id": agent_id,
                "period": {
                    "start_date": start_date,
                    "end_date": end_date
                },
                "ticket_metrics": {
                    "total_tickets": total_tickets,
                    "solved_tickets": solved_count,
                    "resolution_rate": round(resolution_rate, 2),
                    "avg_response_time_minutes": round(avg_response_time, 2),
                    "avg_resolution_time_minutes": round(avg_resolution_time, 2)
                },
                "performance_score": round((resolution_rate + (100 - min(avg_response_time/60, 100))) / 2, 2)
            }
            
            # Add satisfaction data if requested
            if include_satisfaction and agent_id:
                try:
                    # Get satisfaction ratings for this agent's tickets
                    satisfaction_ratings = []
                    for ticket in solved_tickets[:25]:  # Limit for performance
                        try:
                            ratings = self.client.ticket(ticket.id).satisfaction_rating
                            if ratings and hasattr(ratings, 'score'):
                                satisfaction_ratings.append(ratings.score)
                        except:
                            continue
                    
                    if satisfaction_ratings:
                        avg_satisfaction = sum([r for r in satisfaction_ratings if r]) / len([r for r in satisfaction_ratings if r])
                        metrics["satisfaction"] = {
                            "average_score": round(avg_satisfaction, 2),
                            "total_ratings": len(satisfaction_ratings),
                            "score_distribution": {
                                "good": len([r for r in satisfaction_ratings if r == "good"]),
                                "bad": len([r for r in satisfaction_ratings if r == "bad"])
                            }
                        }
                except:
                    metrics["satisfaction"] = {"error": "Could not retrieve satisfaction data"}
            
            # Return summary if requested
            if summarize:
                summary = {
                    "agent_id": agent_id,
                    "period": f"{start_date} to {end_date}",
                    "key_metrics": {
                        "total_tickets": metrics["ticket_metrics"]["total_tickets"],
                        "resolution_rate": f"{metrics['ticket_metrics']['resolution_rate']}%",
                        "avg_response_time": f"{metrics['ticket_metrics']['avg_response_time_minutes']} min",
                        "performance_score": metrics["performance_score"]
                    },
                    "note": "Use summarize=False for detailed metrics"
                }
                
                if "satisfaction" in metrics and "average_score" in metrics["satisfaction"]:
                    summary["key_metrics"]["satisfaction"] = metrics["satisfaction"]["average_score"]
                
                return self._limit_response_size(summary)
            
            return metrics
            
        except Exception as e:
            return {
                "error": f"Failed to get agent performance metrics: {str(e)}",
                "function": "get_agent_performance_metrics"
            }

    def get_team_performance_dashboard(
        self, 
        team_id: Optional[int] = None,
        period: str = "week",
        summarize: bool = True
    ) -> Dict[str, Any]:
        """
        Generate team-wide performance dashboard with:
        - Agent rankings
        - Workload distribution
        - Trend analysis
        - Bottleneck identification
        
        Args:
            team_id: Optional team ID filter
            period: Time period (week, month, quarter)
            summarize: Return summary format (default: True)
        """
        try:
            from datetime import datetime, timedelta
            
            # Calculate date range based on period
            end_date = datetime.now()
            if period == "week":
                start_date = end_date - timedelta(days=7)
            elif period == "month":
                start_date = end_date - timedelta(days=30)
            elif period == "quarter":
                start_date = end_date - timedelta(days=90)
            else:
                start_date = end_date - timedelta(days=7)
            
            start_date_str = start_date.strftime('%Y-%m-%d')
            end_date_str = end_date.strftime('%Y-%m-%d')
            
            # Get all tickets in the period
            query = f"type:ticket created>={start_date_str} created<={end_date_str}"
            tickets = list(self.client.search(query=query))
            
            # Group tickets by agent
            agent_performance = {}
            unassigned_tickets = []
            
            for ticket in tickets:
                assignee_id = getattr(ticket, 'assignee_id', None)
                if assignee_id:
                    if assignee_id not in agent_performance:
                        agent_performance[assignee_id] = {
                            "agent_id": assignee_id,
                            "total_tickets": 0,
                            "solved_tickets": 0,
                            "open_tickets": 0,
                            "pending_tickets": 0,
                            "priority_scores": []
                        }
                    
                    agent_performance[assignee_id]["total_tickets"] += 1
                    
                    status = getattr(ticket, 'status', 'unknown')
                    if status == 'solved':
                        agent_performance[assignee_id]["solved_tickets"] += 1
                    elif status == 'open':
                        agent_performance[assignee_id]["open_tickets"] += 1
                    elif status in ['pending', 'hold']:
                        agent_performance[assignee_id]["pending_tickets"] += 1
                    
                    # Add priority score
                    priority = getattr(ticket, 'priority', 'normal')
                    priority_scores = {'urgent': 4, 'high': 3, 'normal': 2, 'low': 1}
                    agent_performance[assignee_id]["priority_scores"].append(priority_scores.get(priority, 2))
                else:
                    unassigned_tickets.append(ticket)
            
            # Calculate performance metrics for each agent
            agent_rankings = []
            for agent_id, metrics in agent_performance.items():
                if metrics["total_tickets"] > 0:
                    resolution_rate = (metrics["solved_tickets"] / metrics["total_tickets"]) * 100
                    avg_priority = sum(metrics["priority_scores"]) / len(metrics["priority_scores"])
                    performance_score = (resolution_rate + (avg_priority * 10)) / 2
                    
                    agent_rankings.append({
                        "agent_id": agent_id,
                        "total_tickets": metrics["total_tickets"],
                        "solved_tickets": metrics["solved_tickets"],
                        "resolution_rate": round(resolution_rate, 2),
                        "avg_priority_score": round(avg_priority, 2),
                        "performance_score": round(performance_score, 2),
                        "current_workload": metrics["open_tickets"] + metrics["pending_tickets"]
                    })
            
            # Sort by performance score
            agent_rankings.sort(key=lambda x: x["performance_score"], reverse=True)
            
            # Try to get agent names for top performers
            for i, agent in enumerate(agent_rankings[:10]):
                try:
                    user = self.client.users(id=agent["agent_id"])
                    agent["name"] = getattr(user, 'name', f"Agent {agent['agent_id']}")
                    agent["email"] = getattr(user, 'email', 'Unknown')
                except:
                    agent["name"] = f"Agent {agent['agent_id']}"
                    agent["email"] = 'Unknown'
            
            # Calculate team statistics
            total_team_tickets = sum(agent["total_tickets"] for agent in agent_rankings)
            total_solved = sum(agent["solved_tickets"] for agent in agent_rankings)
            team_resolution_rate = (total_solved / total_team_tickets * 100) if total_team_tickets > 0 else 0
            
            dashboard = {
                "period": period,
                "date_range": {
                    "start_date": start_date_str,
                    "end_date": end_date_str
                },
                "team_summary": {
                    "total_tickets": total_team_tickets,
                    "solved_tickets": total_solved,
                    "team_resolution_rate": round(team_resolution_rate, 2),
                    "unassigned_tickets": len(unassigned_tickets),
                    "active_agents": len(agent_rankings)
                },
                "agent_rankings": agent_rankings[:10],  # Top 10 performers
                "workload_distribution": {
                    "high_workload_agents": [a for a in agent_rankings if a["current_workload"] > 10],
                    "balanced_agents": [a for a in agent_rankings if 5 <= a["current_workload"] <= 10],
                    "low_workload_agents": [a for a in agent_rankings if a["current_workload"] < 5]
                },
                "bottlenecks": {
                    "agents_with_low_resolution": [a for a in agent_rankings if a["resolution_rate"] < 70],
                    "overloaded_agents": [a for a in agent_rankings if a["current_workload"] > 15]
                }
            }
            
            # Return summary if requested
            if summarize:
                summary = {
                    "period": period,
                    "team_summary": dashboard["team_summary"],
                    "top_performers": dashboard["agent_rankings"][:3],  # Top 3 only
                    "alerts": {
                        "overloaded_agents": len(dashboard["workload_distribution"]["high_workload_agents"]),
                        "low_resolution_agents": len(dashboard["bottlenecks"]["agents_with_low_resolution"])
                    },
                    "note": "Use summarize=False for complete dashboard"
                }
                return self._limit_response_size(summary)
            
            return dashboard
            
        except Exception as e:
            return {
                "error": f"Failed to generate team performance dashboard: {str(e)}",
                "function": "get_team_performance_dashboard"
            }

    def generate_agent_scorecard(
        self,
        agent_id: int,
        period: str = "month"
    ) -> Dict[str, Any]:
        """
        Create detailed agent scorecard with:
        - Performance vs. targets
        - Improvement areas
        - Strength analysis
        - Historical trends
        """
        try:
            from datetime import datetime, timedelta
            
            # Calculate date range
            end_date = datetime.now()
            if period == "week":
                start_date = end_date - timedelta(days=7)
                target_tickets = 25  # Weekly target
            elif period == "month":
                start_date = end_date - timedelta(days=30)
                target_tickets = 100  # Monthly target
            elif period == "quarter":
                start_date = end_date - timedelta(days=90)
                target_tickets = 300  # Quarterly target
            else:
                start_date = end_date - timedelta(days=30)
                target_tickets = 100
            
            # Get comprehensive metrics for this agent
            metrics = self.get_agent_performance_metrics(
                agent_id=agent_id,
                start_date=start_date.strftime('%Y-%m-%d'),
                end_date=end_date.strftime('%Y-%m-%d'),
                include_satisfaction=True
            )
            
            if "error" in metrics:
                return metrics
            
            # Get agent details
            try:
                agent_info = self.get_user_by_id(agent_id)
            except:
                agent_info = {"name": f"Agent {agent_id}", "email": "Unknown"}
            
            # Define performance targets
            targets = {
                "resolution_rate": 85.0,
                "avg_response_time_hours": 2.0,
                "avg_resolution_time_hours": 24.0,
                "satisfaction_score": 4.0,
                "ticket_volume": target_tickets
            }
            
            # Calculate performance vs targets
            ticket_metrics = metrics.get("ticket_metrics", {})
            satisfaction = metrics.get("satisfaction", {})
            
            performance_vs_targets = {}
            for metric, target in targets.items():
                if metric == "resolution_rate":
                    actual = ticket_metrics.get("resolution_rate", 0)
                elif metric == "avg_response_time_hours":
                    actual = ticket_metrics.get("avg_response_time_minutes", 0) / 60
                elif metric == "avg_resolution_time_hours":
                    actual = ticket_metrics.get("avg_resolution_time_minutes", 0) / 60
                elif metric == "satisfaction_score":
                    actual = satisfaction.get("average_score", 0)
                elif metric == "ticket_volume":
                    actual = ticket_metrics.get("total_tickets", 0)
                else:
                    actual = 0
                
                performance_vs_targets[metric] = {
                    "actual": round(actual, 2),
                    "target": target,
                    "achievement_rate": round((actual / target * 100), 2) if target > 0 else 0,
                    "status": "exceeds" if actual > target else "meets" if actual >= target * 0.9 else "below"
                }
            
            # Identify strengths and improvement areas
            strengths = []
            improvements = []
            
            for metric, data in performance_vs_targets.items():
                if data["achievement_rate"] >= 100:
                    strengths.append({
                        "metric": metric.replace("_", " ").title(),
                        "achievement": f"{data['achievement_rate']}%",
                        "note": "Exceeds target"
                    })
                elif data["achievement_rate"] < 90:
                    improvements.append({
                        "metric": metric.replace("_", " ").title(),
                        "achievement": f"{data['achievement_rate']}%",
                        "gap": round(data["target"] - data["actual"], 2),
                        "priority": "high" if data["achievement_rate"] < 70 else "medium"
                    })
            
            scorecard = {
                "agent_info": agent_info,
                "period": {
                    "type": period,
                    "start_date": start_date.strftime('%Y-%m-%d'),
                    "end_date": end_date.strftime('%Y-%m-%d')
                },
                "overall_score": metrics.get("performance_score", 0),
                "performance_vs_targets": performance_vs_targets,
                "strengths": strengths,
                "improvement_areas": improvements,
                "detailed_metrics": metrics,
                "recommendations": self._generate_recommendations(performance_vs_targets, improvements)
            }
            
            return scorecard
            
        except Exception as e:
            return {
                "error": f"Failed to generate agent scorecard: {str(e)}",
                "function": "generate_agent_scorecard"
            }

    def _generate_recommendations(self, performance_data: Dict, improvements: List) -> List[str]:
        """Generate actionable recommendations based on performance data"""
        recommendations = []
        
        for improvement in improvements:
            metric = improvement["metric"].lower()
            if "response time" in metric:
                recommendations.append("Consider using templates and macros to speed up initial responses")
            elif "resolution time" in metric:
                recommendations.append("Focus on knowledge base utilization and escalation protocols")
            elif "resolution rate" in metric:
                recommendations.append("Review ticket prioritization and time management strategies")
            elif "satisfaction" in metric:
                recommendations.append("Enhance communication skills and follow-up practices")
            elif "ticket volume" in metric:
                recommendations.append("Discuss workload capacity and training opportunities")
        
        # Add general recommendations
        if len(improvements) > 2:
            recommendations.append("Consider additional training or mentoring support")
        
        return recommendations[:5]  # Limit to top 5 recommendations

    def get_agent_workload_analysis(
        self,
        include_pending: bool = True,
        include_open: bool = True
    ) -> Dict[str, Any]:
        """
        Analyze current workload distribution:
        - Active tickets per agent
        - Overdue tickets
        - Capacity utilization
        - Workload imbalance alerts
        """
        try:
            from datetime import datetime, timedelta
            
            # Build query for active tickets
            query_parts = ["type:ticket"]
            if include_open:
                query_parts.append("status:open")
            if include_pending:
                if include_open:
                    query_parts[-1] = "(status:open OR status:pending OR status:hold)"
                else:
                    query_parts.append("(status:pending OR status:hold)")
            
            query = " ".join(query_parts)
            active_tickets = list(self.client.search(query=query))
            
            # Group tickets by agent
            agent_workloads = {}
            unassigned_tickets = []
            overdue_threshold = datetime.now() - timedelta(hours=24)
            
            for ticket in active_tickets:
                assignee_id = getattr(ticket, 'assignee_id', None)
                if assignee_id:
                    if assignee_id not in agent_workloads:
                        agent_workloads[assignee_id] = {
                            'agent_id': assignee_id,
                            'active_tickets': 0,
                            'open_tickets': 0,
                            'pending_tickets': 0,
                            'urgent_tickets': 0,
                            'high_priority_tickets': 0,
                            'overdue_tickets': 0,
                            'ticket_ids': [],
                            'avg_ticket_age_hours': 0
                        }
                    
                    agent_workloads[assignee_id]['active_tickets'] += 1
                    agent_workloads[assignee_id]['ticket_ids'].append(getattr(ticket, 'id', None))
                    
                    # Categorize by status
                    status = getattr(ticket, 'status', 'unknown')
                    if status == 'open':
                        agent_workloads[assignee_id]['open_tickets'] += 1
                    elif status in ['pending', 'hold']:
                        agent_workloads[assignee_id]['pending_tickets'] += 1
                    
                    # Categorize by priority
                    priority = getattr(ticket, 'priority', 'normal')
                    if priority == 'urgent':
                        agent_workloads[assignee_id]['urgent_tickets'] += 1
                    elif priority == 'high':
                        agent_workloads[assignee_id]['high_priority_tickets'] += 1
                    
                    # Check if overdue (simplified - tickets older than 24 hours)
                    created_at = getattr(ticket, 'created_at', None)
                    if created_at:
                        try:
                            # Handle different datetime formats
                            if isinstance(created_at, str):
                                ticket_date = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                            else:
                                ticket_date = created_at
                            
                            if ticket_date < overdue_threshold:
                                agent_workloads[assignee_id]['overdue_tickets'] += 1
                        except:
                            pass
                else:
                    unassigned_tickets.append({
                        'id': getattr(ticket, 'id', None),
                        'subject': getattr(ticket, 'subject', 'No subject'),
                        'priority': getattr(ticket, 'priority', 'normal'),
                        'status': getattr(ticket, 'status', 'unknown')
                    })
            
            # Calculate workload statistics and get agent names
            workload_stats = []
            total_active_tickets = sum(data['active_tickets'] for data in agent_workloads.values())
            
            for agent_id, workload in agent_workloads.items():
                # Try to get agent name
                try:
                    user_info = self.get_user_by_id(agent_id)
                    agent_name = user_info.get('name', f'Agent {agent_id}')
                    agent_email = user_info.get('email', 'Unknown')
                except:
                    agent_name = f'Agent {agent_id}'
                    agent_email = 'Unknown'
                
                # Calculate capacity utilization (assuming 20 tickets is 100% capacity)
                capacity_utilization = min((workload['active_tickets'] / 20) * 100, 100)
                
                # Calculate workload balance (percentage of total team workload)
                workload_percentage = (workload['active_tickets'] / total_active_tickets * 100) if total_active_tickets > 0 else 0
                
                workload_stats.append({
                    'agent_id': agent_id,
                    'agent_name': agent_name,
                    'agent_email': agent_email,
                    'active_tickets': workload['active_tickets'],
                    'open_tickets': workload['open_tickets'],
                    'pending_tickets': workload['pending_tickets'],
                    'urgent_tickets': workload['urgent_tickets'],
                    'high_priority_tickets': workload['high_priority_tickets'],
                    'overdue_tickets': workload['overdue_tickets'],
                    'capacity_utilization': round(capacity_utilization, 2),
                    'workload_percentage': round(workload_percentage, 2),
                    'workload_status': self._determine_workload_status(workload['active_tickets'], workload['overdue_tickets'])
                })
            
            # Sort by active tickets (highest first)
            workload_stats.sort(key=lambda x: x['active_tickets'], reverse=True)
            
            # Identify imbalances and alerts
            avg_tickets_per_agent = total_active_tickets / len(workload_stats) if workload_stats else 0
            overloaded_agents = [agent for agent in workload_stats if agent['active_tickets'] > avg_tickets_per_agent * 1.5]
            underloaded_agents = [agent for agent in workload_stats if agent['active_tickets'] < avg_tickets_per_agent * 0.5]
            
            analysis = {
                'summary': {
                    'total_active_tickets': total_active_tickets,
                    'total_agents': len(workload_stats),
                    'avg_tickets_per_agent': round(avg_tickets_per_agent, 2),
                    'unassigned_tickets': len(unassigned_tickets),
                    'total_overdue_tickets': sum(agent['overdue_tickets'] for agent in workload_stats)
                },
                'agent_workloads': workload_stats,
                'workload_alerts': {
                    'overloaded_agents': overloaded_agents,
                    'underloaded_agents': underloaded_agents,
                    'agents_with_overdue': [agent for agent in workload_stats if agent['overdue_tickets'] > 0],
                    'high_priority_workload': [agent for agent in workload_stats if agent['urgent_tickets'] + agent['high_priority_tickets'] > 5]
                },
                'unassigned_tickets': unassigned_tickets[:10],  # Show first 10 unassigned
                'recommendations': self._generate_workload_recommendations(overloaded_agents, underloaded_agents, unassigned_tickets)
            }
            
            return analysis
            
        except Exception as e:
            return {
                "error": f"Failed to analyze agent workload: {str(e)}",
                "function": "get_agent_workload_analysis"
            }

    def suggest_ticket_reassignment(
        self,
        criteria: str = "workload_balance"
    ) -> List[Dict[str, Any]]:
        """
        Suggest ticket reassignments to:
        - Balance workload
        - Match agent expertise
        - Optimize resolution times
        """
        try:
            # Get current workload analysis
            workload_analysis = self.get_agent_workload_analysis()
            
            if "error" in workload_analysis:
                return [workload_analysis]
            
            suggestions = []
            
            if criteria == "workload_balance":
                overloaded = workload_analysis['workload_alerts']['overloaded_agents']
                underloaded = workload_analysis['workload_alerts']['underloaded_agents']
                
                # Suggest moving tickets from overloaded to underloaded agents
                for overloaded_agent in overloaded[:3]:  # Top 3 overloaded
                    for underloaded_agent in underloaded[:3]:  # Top 3 underloaded
                        tickets_to_move = min(3, overloaded_agent['active_tickets'] - underloaded_agent['active_tickets']) // 2
                        
                        if tickets_to_move > 0:
                            # Get some actual ticket IDs for the overloaded agent
                            agent_tickets_query = f"type:ticket assignee:{overloaded_agent['agent_id']} status:open"
                            agent_tickets = list(self.client.search(query=agent_tickets_query))
                            
                            suggestions.append({
                                'type': 'workload_balance',
                                'from_agent': {
                                    'id': overloaded_agent['agent_id'],
                                    'name': overloaded_agent['agent_name'],
                                    'current_tickets': overloaded_agent['active_tickets']
                                },
                                'to_agent': {
                                    'id': underloaded_agent['agent_id'],
                                    'name': underloaded_agent['agent_name'],
                                    'current_tickets': underloaded_agent['active_tickets']
                                },
                                'suggested_tickets': [
                                    {
                                        'id': getattr(ticket, 'id', None),
                                        'subject': getattr(ticket, 'subject', 'No subject')[:50] + "...",
                                        'priority': getattr(ticket, 'priority', 'normal'),
                                        'created_at': getattr(ticket, 'created_at', None)
                                    }
                                    for ticket in agent_tickets[:tickets_to_move]
                                ],
                                'reason': f"Balance workload: reduce {overloaded_agent['agent_name']}'s load from {overloaded_agent['active_tickets']} to {overloaded_agent['active_tickets'] - tickets_to_move}",
                                'priority': 'medium'
                            })
            
            elif criteria == "urgent_priority":
                # Focus on redistributing urgent/high priority tickets
                high_priority_agents = workload_analysis['workload_alerts']['high_priority_workload']
                underloaded = workload_analysis['workload_alerts']['underloaded_agents']
                
                for priority_agent in high_priority_agents[:2]:
                    if priority_agent['urgent_tickets'] > 3:
                        for target_agent in underloaded[:2]:
                            urgent_tickets_query = f"type:ticket assignee:{priority_agent['agent_id']} priority:urgent status:open"
                            urgent_tickets = list(self.client.search(query=urgent_tickets_query))
                            
                            if urgent_tickets:
                                suggestions.append({
                                    'type': 'urgent_redistribution',
                                    'from_agent': {
                                        'id': priority_agent['agent_id'],
                                        'name': priority_agent['agent_name'],
                                        'urgent_tickets': priority_agent['urgent_tickets']
                                    },
                                    'to_agent': {
                                        'id': target_agent['agent_id'],
                                        'name': target_agent['agent_name'],
                                        'current_tickets': target_agent['active_tickets']
                                    },
                                    'suggested_tickets': [
                                        {
                                            'id': getattr(ticket, 'id', None),
                                            'subject': getattr(ticket, 'subject', 'No subject')[:50] + "...",
                                            'priority': getattr(ticket, 'priority', 'urgent')
                                        }
                                        for ticket in urgent_tickets[:2]
                                    ],
                                    'reason': f"Distribute urgent tickets to reduce pressure on {priority_agent['agent_name']}",
                                    'priority': 'high'
                                })
            
            # Handle unassigned tickets
            unassigned = workload_analysis['unassigned_tickets']
            if unassigned and workload_analysis['agent_workloads']:
                # Suggest assigning to least loaded agents
                sorted_agents = sorted(workload_analysis['agent_workloads'], key=lambda x: x['active_tickets'])
                
                for i, ticket in enumerate(unassigned[:5]):  # Top 5 unassigned
                    target_agent = sorted_agents[i % len(sorted_agents)]
                    
                    suggestions.append({
                        'type': 'assign_unassigned',
                        'ticket': ticket,
                        'to_agent': {
                            'id': target_agent['agent_id'],
                            'name': target_agent['agent_name'],
                            'current_tickets': target_agent['active_tickets']
                        },
                        'reason': f"Assign to {target_agent['agent_name']} (currently has {target_agent['active_tickets']} tickets)",
                        'priority': 'medium' if ticket['priority'] in ['urgent', 'high'] else 'low'
                    })
            
            # Sort suggestions by priority
            priority_order = {'high': 3, 'medium': 2, 'low': 1}
            suggestions.sort(key=lambda x: priority_order.get(x['priority'], 0), reverse=True)
            
            return suggestions[:10]  # Return top 10 suggestions
            
        except Exception as e:
            return [{
                "error": f"Failed to suggest ticket reassignments: {str(e)}",
                "function": "suggest_ticket_reassignment"
            }]

    def _determine_workload_status(self, active_tickets: int, overdue_tickets: int) -> str:
        """Determine workload status based on ticket counts"""
        if overdue_tickets > 5:
            return "critical"
        elif active_tickets > 15:
            return "overloaded"
        elif active_tickets > 10:
            return "high"
        elif active_tickets > 5:
            return "normal"
        else:
            return "light"

    def _generate_workload_recommendations(self, overloaded: List, underloaded: List, unassigned: List) -> List[str]:
        """Generate actionable workload management recommendations"""
        recommendations = []
        
        if overloaded:
            recommendations.append(f"Consider redistributing tickets from {len(overloaded)} overloaded agents")
        
        if unassigned:
            recommendations.append(f"Assign {len(unassigned)} unassigned tickets to available agents")
        
        if underloaded:
            recommendations.append(f"Utilize {len(underloaded)} underloaded agents for new ticket assignments")
        
        if overloaded and underloaded:
            recommendations.append("Implement automatic load balancing between agents")
        
        recommendations.append("Monitor workload distribution daily to prevent bottlenecks")
        
        return recommendations[:5]

    def get_sla_compliance_report(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        agent_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Generate SLA compliance report:
        - First response time compliance
        - Resolution time compliance
        - Breach predictions
        - Performance by priority level
        """
        try:
            from datetime import datetime, timedelta
            
            # Set default date range if not provided
            if not end_date:
                end_date = datetime.now().strftime('%Y-%m-%d')
            if not start_date:
                start_date = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
            
            # Build query
            query = f"type:ticket created>={start_date} created<={end_date}"
            if agent_id:
                query += f" assignee:{agent_id}"
            
            # Get tickets for the period
            tickets = list(self.client.search(query=query))
            
            # SLA targets (in minutes)
            sla_targets = {
                'urgent': {'first_response': 60, 'resolution': 240},    # 1h, 4h
                'high': {'first_response': 120, 'resolution': 480},     # 2h, 8h
                'normal': {'first_response': 480, 'resolution': 1440},  # 8h, 24h
                'low': {'first_response': 1440, 'resolution': 2880}     # 24h, 48h
            }
            
            # Initialize compliance tracking
            compliance_data = {
                'urgent': {'total': 0, 'first_response_met': 0, 'resolution_met': 0, 'response_times': [], 'resolution_times': []},
                'high': {'total': 0, 'first_response_met': 0, 'resolution_met': 0, 'response_times': [], 'resolution_times': []},
                'normal': {'total': 0, 'first_response_met': 0, 'resolution_met': 0, 'response_times': [], 'resolution_times': []},
                'low': {'total': 0, 'first_response_met': 0, 'resolution_met': 0, 'response_times': [], 'resolution_times': []}
            }
            
            # Analyze each ticket
            for ticket in tickets[:100]:  # Limit for performance
                priority = getattr(ticket, 'priority', 'normal')
                if priority not in compliance_data:
                    priority = 'normal'
                
                compliance_data[priority]['total'] += 1
                
                try:
                    # Get ticket metrics
                    ticket_metrics = self.client.ticket_metrics(ticket.id)
                    
                    # Check first response time
                    if hasattr(ticket_metrics, 'reply_time_in_minutes') and ticket_metrics.reply_time_in_minutes:
                        response_time = ticket_metrics.reply_time_in_minutes.business_minutes
                        compliance_data[priority]['response_times'].append(response_time)
                        
                        if response_time <= sla_targets[priority]['first_response']:
                            compliance_data[priority]['first_response_met'] += 1
                    
                    # Check resolution time (for solved tickets)
                    if getattr(ticket, 'status', '') == 'solved':
                        if hasattr(ticket_metrics, 'full_resolution_time_in_minutes') and ticket_metrics.full_resolution_time_in_minutes:
                            resolution_time = ticket_metrics.full_resolution_time_in_minutes.business_minutes
                            compliance_data[priority]['resolution_times'].append(resolution_time)
                            
                            if resolution_time <= sla_targets[priority]['resolution']:
                                compliance_data[priority]['resolution_met'] += 1
                                
                except Exception:
                    # Skip if we can't get metrics for this ticket
                    continue
            
            # Calculate compliance percentages
            compliance_summary = {}
            overall_stats = {'total_tickets': 0, 'total_response_compliant': 0, 'total_resolution_compliant': 0}
            
            for priority, data in compliance_data.items():
                if data['total'] > 0:
                    response_compliance = (data['first_response_met'] / data['total']) * 100
                    
                    # Resolution compliance only for solved tickets
                    solved_tickets = len(data['resolution_times'])
                    resolution_compliance = (data['resolution_met'] / solved_tickets * 100) if solved_tickets > 0 else 0
                    
                    # Calculate average times
                    avg_response_time = sum(data['response_times']) / len(data['response_times']) if data['response_times'] else 0
                    avg_resolution_time = sum(data['resolution_times']) / len(data['resolution_times']) if data['resolution_times'] else 0
                    
                    compliance_summary[priority] = {
                        'total_tickets': data['total'],
                        'first_response_compliance': round(response_compliance, 2),
                        'resolution_compliance': round(resolution_compliance, 2),
                        'avg_response_time_minutes': round(avg_response_time, 2),
                        'avg_resolution_time_minutes': round(avg_resolution_time, 2),
                        'sla_targets': sla_targets[priority],
                        'status': 'good' if response_compliance >= 95 and resolution_compliance >= 90 else 'warning' if response_compliance >= 85 else 'critical'
                    }
                    
                    overall_stats['total_tickets'] += data['total']
                    overall_stats['total_response_compliant'] += data['first_response_met']
                    overall_stats['total_resolution_compliant'] += data['resolution_met']
            
            # Overall compliance rates
            overall_response_compliance = (overall_stats['total_response_compliant'] / overall_stats['total_tickets'] * 100) if overall_stats['total_tickets'] > 0 else 0
            total_solved = sum(len(data['resolution_times']) for data in compliance_data.values())
            overall_resolution_compliance = (overall_stats['total_resolution_compliant'] / total_solved * 100) if total_solved > 0 else 0
            
            report = {
                'period': {
                    'start_date': start_date,
                    'end_date': end_date
                },
                'agent_id': agent_id,
                'overall_compliance': {
                    'first_response_rate': round(overall_response_compliance, 2),
                    'resolution_rate': round(overall_resolution_compliance, 2),
                    'total_tickets_analyzed': overall_stats['total_tickets'],
                    'status': 'good' if overall_response_compliance >= 90 and overall_resolution_compliance >= 85 else 'needs_improvement'
                },
                'compliance_by_priority': compliance_summary,
                'recommendations': self._generate_sla_recommendations(compliance_summary)
            }
            
            return report
            
        except Exception as e:
            return {
                "error": f"Failed to generate SLA compliance report: {str(e)}",
                "function": "get_sla_compliance_report"
            }

    def get_at_risk_tickets(self, time_horizon: int = 24) -> List[Dict[str, Any]]:
        """
        Identify tickets at risk of SLA breach:
        - Time remaining until breach
        - Escalation recommendations
        - Priority adjustment suggestions
        """
        try:
            from datetime import datetime, timedelta
            
            # Get active tickets
            query = "type:ticket (status:new OR status:open OR status:pending)"
            active_tickets = list(self.client.search(query=query))
            
            # SLA targets (in hours)
            sla_targets = {
                'urgent': {'first_response': 1, 'resolution': 4},
                'high': {'first_response': 2, 'resolution': 8},
                'normal': {'first_response': 8, 'resolution': 24},
                'low': {'first_response': 24, 'resolution': 48}
            }
            
            at_risk_tickets = []
            current_time = datetime.now()
            
            for ticket in active_tickets[:50]:  # Limit for performance
                try:
                    priority = getattr(ticket, 'priority', 'normal')
                    if priority not in sla_targets:
                        priority = 'normal'
                    
                    created_at = getattr(ticket, 'created_at', None)
                    if not created_at:
                        continue
                    
                    # Parse creation time
                    if isinstance(created_at, str):
                        ticket_created = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                    else:
                        ticket_created = created_at
                    
                    # Calculate time elapsed
                    time_elapsed = current_time - ticket_created.replace(tzinfo=None)
                    hours_elapsed = time_elapsed.total_seconds() / 3600
                    
                    # Check if we need first response
                    status = getattr(ticket, 'status', 'new')
                    needs_first_response = status == 'new'
                    
                    risk_factors = []
                    risk_level = 'low'
                    
                    if needs_first_response:
                        first_response_target = sla_targets[priority]['first_response']
                        time_until_breach = first_response_target - hours_elapsed
                        
                        if time_until_breach <= 0:
                            risk_factors.append('First response SLA already breached')
                            risk_level = 'critical'
                        elif time_until_breach <= time_horizon:
                            risk_factors.append(f'First response SLA breach in {time_until_breach:.1f} hours')
                            risk_level = 'high' if time_until_breach <= time_horizon/2 else 'medium'
                    
                    # Check resolution SLA
                    resolution_target = sla_targets[priority]['resolution']
                    time_until_resolution_breach = resolution_target - hours_elapsed
                    
                    if time_until_resolution_breach <= 0:
                        risk_factors.append('Resolution SLA already breached')
                        risk_level = 'critical'
                    elif time_until_resolution_breach <= time_horizon:
                        if 'critical' not in risk_level:
                            risk_level = 'high' if time_until_resolution_breach <= time_horizon/2 else 'medium'
                        risk_factors.append(f'Resolution SLA breach in {time_until_resolution_breach:.1f} hours')
                    
                    # Only include tickets with risks
                    if risk_factors:
                        # Get assignee name
                        assignee_name = 'Unassigned'
                        assignee_id = getattr(ticket, 'assignee_id', None)
                        if assignee_id:
                            try:
                                user_info = self.get_user_by_id(assignee_id)
                                assignee_name = user_info.get('name', f'Agent {assignee_id}')
                            except:
                                assignee_name = f'Agent {assignee_id}'
                        
                        at_risk_tickets.append({
                            'ticket_id': getattr(ticket, 'id', None),
                            'subject': getattr(ticket, 'subject', 'No subject')[:60] + ("..." if len(getattr(ticket, 'subject', '')) > 60 else ""),
                            'priority': priority,
                            'status': status,
                            'assignee': assignee_name,
                            'created_at': created_at,
                            'hours_elapsed': round(hours_elapsed, 2),
                            'risk_level': risk_level,
                            'risk_factors': risk_factors,
                            'recommendations': self._generate_risk_recommendations(risk_level, priority, assignee_id is None, hours_elapsed)
                        })
                        
                except Exception:
                    continue
            
            # Sort by risk level and time
            risk_priority = {'critical': 4, 'high': 3, 'medium': 2, 'low': 1}
            at_risk_tickets.sort(key=lambda x: (risk_priority.get(x['risk_level'], 0), x['hours_elapsed']), reverse=True)
            
            return at_risk_tickets[:20]  # Return top 20 at-risk tickets
            
        except Exception as e:
            return [{
                "error": f"Failed to identify at-risk tickets: {str(e)}",
                "function": "get_at_risk_tickets"
            }]

    def _generate_sla_recommendations(self, compliance_data: Dict) -> List[str]:
        """Generate SLA improvement recommendations"""
        recommendations = []
        
        for priority, data in compliance_data.items():
            if data['first_response_compliance'] < 90:
                recommendations.append(f"Improve {priority} priority first response times (currently {data['first_response_compliance']}%)")
            
            if data['resolution_compliance'] < 85:
                recommendations.append(f"Focus on faster {priority} priority resolutions (currently {data['resolution_compliance']}%)")
        
        # General recommendations
        if any(data['status'] == 'critical' for data in compliance_data.values()):
            recommendations.append("Implement automated escalation for critical SLA breaches")
        
        if any(data['first_response_compliance'] < 80 for data in compliance_data.values()):
            recommendations.append("Consider using response templates and auto-assignment rules")
        
        return recommendations[:5]

    def _generate_risk_recommendations(self, risk_level: str, priority: str, unassigned: bool, hours_elapsed: float) -> List[str]:
        """Generate recommendations for at-risk tickets"""
        recommendations = []
        
        if risk_level == 'critical':
            recommendations.append("URGENT: Immediate escalation required")
            recommendations.append("Notify team lead and senior agents")
        elif risk_level == 'high':
            recommendations.append("High priority: Assign to available senior agent")
            recommendations.append("Consider priority escalation")
        
        if unassigned:
            recommendations.append("Assign to available agent immediately")
        
        if hours_elapsed > 24:
            recommendations.append("Review complexity and consider expert consultation")
        
        if priority in ['urgent', 'high']:
            recommendations.append("Ensure agent has necessary resources and tools")
        
        return recommendations[:3]

    def bulk_update_tickets(
        self,
        ticket_ids: List[int],
        updates: Dict[str, Any],
        reason: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Bulk update multiple tickets:
        - Status changes
        - Priority adjustments
        - Tag additions/removals
        - Assignment changes
        """
        try:
            if not ticket_ids:
                return {"error": "No ticket IDs provided", "function": "bulk_update_tickets"}
            
            if len(ticket_ids) > 100:
                return {"error": "Maximum 100 tickets can be updated at once", "function": "bulk_update_tickets"}
            
            results = {
                "total_tickets": len(ticket_ids),
                "successful_updates": 0,
                "failed_updates": 0,
                "results": [],
                "updates_applied": updates,
                "reason": reason
            }
            
            # Process tickets in batches for better performance
            batch_size = 20
            for i in range(0, len(ticket_ids), batch_size):
                batch = ticket_ids[i:i + batch_size]
                
                for ticket_id in batch:
                    try:
                        # Get the current ticket
                        ticket = self.client.tickets(id=ticket_id)
                        
                        # Apply updates
                        update_data = {}
                        
                        # Handle different types of updates
                        if 'status' in updates:
                            update_data['status'] = updates['status']
                        
                        if 'priority' in updates:
                            update_data['priority'] = updates['priority']
                        
                        if 'assignee_id' in updates:
                            update_data['assignee_id'] = updates['assignee_id']
                        
                        if 'tags' in updates:
                            # Handle tag operations
                            current_tags = getattr(ticket, 'tags', [])
                            if updates['tags'].get('action') == 'add':
                                new_tags = list(set(current_tags + updates['tags']['values']))
                            elif updates['tags'].get('action') == 'remove':
                                new_tags = [tag for tag in current_tags if tag not in updates['tags']['values']]
                            elif updates['tags'].get('action') == 'set':
                                new_tags = updates['tags']['values']
                            else:
                                new_tags = current_tags
                            update_data['tags'] = new_tags
                        
                        if 'group_id' in updates:
                            update_data['group_id'] = updates['group_id']
                        
                        # Update the ticket
                        if update_data:
                            updated_ticket = self.client.tickets.update(ticket_id, update_data)
                            
                            # Add comment with reason if provided
                            if reason:
                                comment_data = {
                                    'body': f"Bulk update applied: {reason}",
                                    'public': False
                                }
                                self.client.ticket_comments.create(ticket_id, comment_data)
                            
                            results["successful_updates"] += 1
                            results["results"].append({
                                "ticket_id": ticket_id,
                                "status": "success",
                                "message": "Updated successfully"
                            })
                        else:
                            results["results"].append({
                                "ticket_id": ticket_id,
                                "status": "skipped",
                                "message": "No valid updates provided"
                            })
                            
                    except Exception as e:
                        results["failed_updates"] += 1
                        results["results"].append({
                            "ticket_id": ticket_id,
                            "status": "failed",
                            "message": f"Update failed: {str(e)}"
                        })
            
            return results
            
        except Exception as e:
            return {
                "error": f"Failed to bulk update tickets: {str(e)}",
                "function": "bulk_update_tickets"
            }

    def auto_categorize_tickets(
        self,
        ticket_ids: Optional[List[int]] = None,
        use_ml: bool = True
    ) -> Dict[str, Any]:
        """
        Automatically categorize tickets based on:
        - Content analysis
        - Historical patterns
        - Machine learning models (simulated)
        """
        try:
            # If no specific tickets provided, get recent untagged tickets
            if not ticket_ids:
                query = "type:ticket created>7days tags:none"
                tickets = list(self.client.search(query=query))
                ticket_ids = [getattr(ticket, 'id', None) for ticket in tickets[:50] if getattr(ticket, 'id', None)]
            
            if not ticket_ids:
                return {"message": "No tickets found for categorization", "function": "auto_categorize_tickets"}
            
            # Define categorization rules based on content analysis
            categories = {
                'technical': ['error', 'bug', 'crash', 'api', 'integration', 'database', 'server', 'code'],
                'billing': ['payment', 'invoice', 'charge', 'billing', 'subscription', 'refund', 'credit'],
                'account': ['login', 'password', 'access', 'permission', 'account', 'user', 'profile'],
                'feature_request': ['feature', 'enhancement', 'improvement', 'request', 'add', 'new'],
                'support': ['help', 'how to', 'tutorial', 'guide', 'documentation', 'question'],
                'urgent': ['urgent', 'critical', 'emergency', 'down', 'outage', 'broken']
            }
            
            results = {
                "total_tickets": len(ticket_ids),
                "categorized": 0,
                "failed": 0,
                "categorizations": []
            }
            
            for ticket_id in ticket_ids:
                try:
                    # Get ticket details
                    ticket = self.client.tickets(id=ticket_id)
                    subject = getattr(ticket, 'subject', '').lower()
                    description = getattr(ticket, 'description', '').lower()
                    content = f"{subject} {description}"
                    
                    # Score each category
                    category_scores = {}
                    for category, keywords in categories.items():
                        score = sum(1 for keyword in keywords if keyword in content)
                        if score > 0:
                            category_scores[category] = score
                    
                    # Determine best category
                    suggested_tags = []
                    if category_scores:
                        # Get top scoring categories
                        max_score = max(category_scores.values())
                        top_categories = [cat for cat, score in category_scores.items() if score == max_score]
                        suggested_tags.extend(top_categories)
                        
                        # Add priority tag if urgent keywords found
                        if 'urgent' in category_scores:
                            suggested_tags.append('priority_escalation')
                    
                    # Apply ML-based categorization (simulated)
                    if use_ml and len(content) > 50:
                        # Simulate ML analysis
                        if 'integration' in content or 'api' in content:
                            suggested_tags.append('integration_team')
                        elif 'mobile' in content or 'app' in content:
                            suggested_tags.append('mobile_team')
                        elif len(content) > 200:
                            suggested_tags.append('complex_issue')
                    
                    # Apply tags if any were suggested
                    if suggested_tags:
                        # Get current tags
                        current_tags = getattr(ticket, 'tags', [])
                        new_tags = list(set(current_tags + suggested_tags))
                        
                        # Update ticket with new tags
                        self.client.tickets.update(ticket_id, {'tags': new_tags})
                        
                        results["categorized"] += 1
                        results["categorizations"].append({
                            "ticket_id": ticket_id,
                            "subject": getattr(ticket, 'subject', 'No subject')[:60],
                            "suggested_tags": suggested_tags,
                            "confidence": "high" if max(category_scores.values()) > 2 else "medium",
                            "status": "applied"
                        })
                    else:
                        results["categorizations"].append({
                            "ticket_id": ticket_id,
                            "subject": getattr(ticket, 'subject', 'No subject')[:60],
                            "suggested_tags": [],
                            "confidence": "low",
                            "status": "no_category_found"
                        })
                        
                except Exception as e:
                    results["failed"] += 1
                    results["categorizations"].append({
                        "ticket_id": ticket_id,
                        "status": "failed",
                        "error": str(e)
                    })
            
            return results
            
        except Exception as e:
            return {
                "error": f"Failed to auto-categorize tickets: {str(e)}",
                "function": "auto_categorize_tickets"
            }

    def escalate_ticket(
        self,
        ticket_id: int,
        escalation_level: str,
        reason: str,
        notify_stakeholders: bool = True
    ) -> Dict[str, Any]:
        """
        Escalate tickets with proper notifications and tracking:
        - manager: Escalate to team manager
        - senior_agent: Assign to senior agent
        - external: External escalation
        """
        try:
            # Get the current ticket
            ticket = self.client.tickets(id=ticket_id)
            if not ticket:
                return {"error": f"Ticket {ticket_id} not found", "function": "escalate_ticket"}
            
            # Prepare escalation data
            escalation_data = {
                "ticket_id": ticket_id,
                "escalation_level": escalation_level,
                "reason": reason,
                "escalated_at": datetime.now().isoformat(),
                "escalated_by": "MCP_Server",  # In real implementation, this would be the current user
                "previous_assignee": getattr(ticket, 'assignee_id', None)
            }
            
            # Apply escalation based on level
            update_data = {}
            notification_message = ""
            
            if escalation_level == "manager":
                # Set priority to high if not already urgent
                current_priority = getattr(ticket, 'priority', 'normal')
                if current_priority not in ['urgent', 'high']:
                    update_data['priority'] = 'high'
                
                # Add escalation tags
                current_tags = getattr(ticket, 'tags', [])
                new_tags = list(set(current_tags + ['escalated', 'manager_review']))
                update_data['tags'] = new_tags
                
                notification_message = f"Ticket escalated to manager review. Reason: {reason}"
                
            elif escalation_level == "senior_agent":
                # Would typically assign to a specific senior agent
                # For now, we'll add tags and increase priority
                current_priority = getattr(ticket, 'priority', 'normal')
                if current_priority == 'normal':
                    update_data['priority'] = 'high'
                elif current_priority == 'low':
                    update_data['priority'] = 'normal'
                
                current_tags = getattr(ticket, 'tags', [])
                new_tags = list(set(current_tags + ['escalated', 'senior_agent_required']))
                update_data['tags'] = new_tags
                
                notification_message = f"Ticket escalated to senior agent. Reason: {reason}"
                
            elif escalation_level == "external":
                # Mark for external escalation
                current_tags = getattr(ticket, 'tags', [])
                new_tags = list(set(current_tags + ['escalated', 'external_escalation']))
                update_data['tags'] = new_tags
                
                update_data['priority'] = 'urgent'
                notification_message = f"Ticket marked for external escalation. Reason: {reason}"
            
            # Update the ticket
            if update_data:
                self.client.tickets.update(ticket_id, update_data)
            
            # Add escalation comment
            escalation_comment = {
                'body': f"🔺 ESCALATION - {escalation_level.upper()}\n\nReason: {reason}\n\nThis ticket has been escalated and requires immediate attention.",
                'public': False
            }
            self.client.ticket_comments.create(ticket_id, escalation_comment)
            
            # Simulate stakeholder notifications (in real implementation, this would send actual notifications)
            notifications_sent = []
            if notify_stakeholders:
                if escalation_level == "manager":
                    notifications_sent.append("Team Manager")
                elif escalation_level == "senior_agent":
                    notifications_sent.append("Senior Agents")
                elif escalation_level == "external":
                    notifications_sent.append("External Team Lead")
            
            escalation_data.update({
                "status": "escalated",
                "updates_applied": update_data,
                "notification_message": notification_message,
                "notifications_sent": notifications_sent,
                "next_steps": self._generate_escalation_next_steps(escalation_level, reason)
            })
            
            return escalation_data
            
        except Exception as e:
            return {
                "error": f"Failed to escalate ticket: {str(e)}",
                "function": "escalate_ticket"
            }

    def _generate_escalation_next_steps(self, escalation_level: str, reason: str) -> List[str]:
        """Generate next steps based on escalation level and reason"""
        next_steps = []
        
        if escalation_level == "manager":
            next_steps.extend([
                "Manager will review within 2 hours",
                "Consider resource allocation or priority adjustment",
                "Evaluate if additional team members needed"
            ])
        elif escalation_level == "senior_agent":
            next_steps.extend([
                "Senior agent will be assigned within 1 hour",
                "Review technical complexity and requirements",
                "Consider knowledge transfer if needed"
            ])
        elif escalation_level == "external":
            next_steps.extend([
                "External team will be contacted immediately",
                "Prepare detailed handoff documentation",
                "Schedule handoff meeting if required"
            ])
        
        # Add specific next steps based on reason
        if "technical" in reason.lower():
            next_steps.append("Technical expertise consultation required")
        elif "customer" in reason.lower():
            next_steps.append("Customer relationship management involvement")
        elif "urgent" in reason.lower():
            next_steps.append("Immediate response protocol activated")
        
        return next_steps[:5]

    # =====================================
    # MACROS AND TEMPLATES MANAGEMENT
    # =====================================
    
    def get_macros(self) -> Dict[str, Any]:
        """Get all available macros for agents to use in tickets"""
        try:
            macros = list(self.client.macros())
            
            macro_list = []
            for macro in macros:
                macro_data = {
                    'id': getattr(macro, 'id', None),
                    'title': getattr(macro, 'title', 'Untitled'),
                    'active': getattr(macro, 'active', True),
                    'description': getattr(macro, 'description', ''),
                    'position': getattr(macro, 'position', 0),
                    'usage_1h': getattr(macro, 'usage_1h', 0),
                    'usage_7d': getattr(macro, 'usage_7d', 0),
                    'usage_30d': getattr(macro, 'usage_30d', 0),
                    'created_at': getattr(macro, 'created_at', None),
                    'updated_at': getattr(macro, 'updated_at', None)
                }
                macro_list.append(macro_data)
            
            # Sort by usage (most used first)
            macro_list.sort(key=lambda x: x['usage_30d'], reverse=True)
            
            return {
                'status': 'success',
                'total_macros': len(macro_list),
                'macros': macro_list
            }
            
        except Exception as e:
            return {
                'status': 'error',
                'message': f'Failed to get macros: {str(e)}'
            }

    def apply_macro_to_ticket(self, ticket_id: int, macro_id: int) -> Dict[str, Any]:
        """Apply a macro to a specific ticket"""
        try:
            # Get the macro first to verify it exists
            macro = self.client.macros(id=macro_id)
            if not macro:
                return {
                    'status': 'error',
                    'message': f'Macro {macro_id} not found'
                }
            
            # Apply the macro to the ticket
            result = self.client.tickets.macros.apply(ticket_id, macro_id)
            
            return {
                'status': 'success',
                'ticket_id': ticket_id,
                'macro_id': macro_id,
                'macro_title': getattr(macro, 'title', 'Unknown'),
                'result': 'Macro applied successfully'
            }
            
        except Exception as e:
            return {
                'status': 'error',
                'message': f'Failed to apply macro to ticket: {str(e)}'
            }

    def get_ticket_forms(self) -> Dict[str, Any]:
        """Get all ticket forms and their field configurations"""
        try:
            ticket_forms = list(self.client.ticket_forms())
            
            forms_list = []
            for form in ticket_forms:
                form_data = {
                    'id': getattr(form, 'id', None),
                    'name': getattr(form, 'name', 'Unnamed Form'),
                    'display_name': getattr(form, 'display_name', ''),
                    'active': getattr(form, 'active', True),
                    'default': getattr(form, 'default', False),
                    'position': getattr(form, 'position', 0),
                    'ticket_field_ids': getattr(form, 'ticket_field_ids', []),
                    'created_at': getattr(form, 'created_at', None),
                    'updated_at': getattr(form, 'updated_at', None)
                }
                forms_list.append(form_data)
            
            return {
                'status': 'success',
                'total_forms': len(forms_list),
                'ticket_forms': forms_list
            }
            
        except Exception as e:
            return {
                'status': 'error',
                'message': f'Failed to get ticket forms: {str(e)}'
            }

    # =====================================
    # ADVANCED TICKET OPERATIONS
    # =====================================
    
    def merge_tickets(self, source_ticket_ids: List[int], target_ticket_id: int) -> Dict[str, Any]:
        """Merge multiple source tickets into one target ticket"""
        try:
            # Verify target ticket exists
            target_ticket = self.client.tickets(id=target_ticket_id)
            if not target_ticket:
                return {
                    'status': 'error',
                    'message': f'Target ticket {target_ticket_id} not found'
                }
            
            merged_results = []
            for source_id in source_ticket_ids:
                try:
                    # Get source ticket
                    source_ticket = self.client.tickets(id=source_id)
                    if not source_ticket:
                        merged_results.append({
                            'source_ticket_id': source_id,
                            'status': 'failed',
                            'reason': 'Source ticket not found'
                        })
                        continue
                    
                    # Merge the ticket (in Zendesk, this involves updating the source ticket)
                    merge_data = {
                        'status': 'closed',
                        'comment': {
                            'body': f'This ticket has been merged into ticket #{target_ticket_id}',
                            'public': False
                        }
                    }
                    
                    self.client.tickets.update(source_id, merge_data)
                    
                    # Add a comment to the target ticket
                    target_comment = {
                        'body': f'Ticket #{source_id} has been merged into this ticket',
                        'public': False
                    }
                    self.client.ticket_comments.create(target_ticket_id, target_comment)
                    
                    merged_results.append({
                        'source_ticket_id': source_id,
                        'status': 'success',
                        'reason': 'Merged successfully'
                    })
                    
                except Exception as e:
                    merged_results.append({
                        'source_ticket_id': source_id,
                        'status': 'failed',
                        'reason': str(e)
                    })
            
            successful_merges = len([r for r in merged_results if r['status'] == 'success'])
            
            return {
                'status': 'success',
                'target_ticket_id': target_ticket_id,
                'total_source_tickets': len(source_ticket_ids),
                'successful_merges': successful_merges,
                'merge_results': merged_results
            }
            
        except Exception as e:
            return {
                'status': 'error',
                'message': f'Failed to merge tickets: {str(e)}'
            }

    def clone_ticket(self, ticket_id: int, include_comments: bool = False) -> Dict[str, Any]:
        """Clone a ticket with optional comments"""
        try:
            # Get the original ticket
            original_ticket = self.client.tickets(id=ticket_id)
            if not original_ticket:
                return {
                    'status': 'error',
                    'message': f'Ticket {ticket_id} not found'
                }
            
            # Create new ticket data based on original
            new_ticket_data = {
                'subject': f"[CLONED] {getattr(original_ticket, 'subject', 'No Subject')}",
                'description': getattr(original_ticket, 'description', ''),
                'priority': getattr(original_ticket, 'priority', 'normal'),
                'type': getattr(original_ticket, 'type', None),
                'status': 'new',  # Always create as new
                'requester_id': getattr(original_ticket, 'requester_id', None),
                'assignee_id': getattr(original_ticket, 'assignee_id', None),
                'group_id': getattr(original_ticket, 'group_id', None),
                'tags': getattr(original_ticket, 'tags', []) + ['cloned'],
                'custom_fields': getattr(original_ticket, 'custom_fields', [])
            }
            
            # Create the new ticket
            new_ticket = self.client.tickets.create(new_ticket_data)
            new_ticket_id = getattr(new_ticket, 'id', None)
            
            # Add comments if requested
            comments_cloned = 0
            if include_comments and new_ticket_id:
                try:
                    comments = list(self.client.tickets.comments(ticket_id))
                    for comment in comments:
                        if getattr(comment, 'public', False):  # Only clone public comments
                            comment_data = {
                                'body': f"[CLONED FROM TICKET #{ticket_id}]\n\n{getattr(comment, 'body', '')}",
                                'public': True
                            }
                            self.client.ticket_comments.create(new_ticket_id, comment_data)
                            comments_cloned += 1
                except Exception:
                    pass  # Continue even if comments fail
            
            # Add reference comment to original ticket
            try:
                reference_comment = {
                    'body': f'This ticket has been cloned to ticket #{new_ticket_id}',
                    'public': False
                }
                self.client.ticket_comments.create(ticket_id, reference_comment)
            except Exception:
                pass  # Continue even if reference comment fails
            
            return {
                'status': 'success',
                'original_ticket_id': ticket_id,
                'new_ticket_id': new_ticket_id,
                'comments_cloned': comments_cloned,
                'include_comments': include_comments
            }
            
        except Exception as e:
            return {
                'status': 'error',
                'message': f'Failed to clone ticket: {str(e)}'
            }

    def add_ticket_tags(self, ticket_id: int, tags: List[str]) -> Dict[str, Any]:
        """Add tags to a ticket"""
        try:
            # Get current ticket
            ticket = self.client.tickets(id=ticket_id)
            if not ticket:
                return {
                    'status': 'error',
                    'message': f'Ticket {ticket_id} not found'
                }
            
            # Get current tags and add new ones
            current_tags = getattr(ticket, 'tags', [])
            new_tags = list(set(current_tags + tags))  # Remove duplicates
            
            # Update ticket with new tags
            update_data = {'tags': new_tags}
            self.client.tickets.update(ticket_id, update_data)
            
            added_tags = [tag for tag in tags if tag not in current_tags]
            
            return {
                'status': 'success',
                'ticket_id': ticket_id,
                'tags_added': added_tags,
                'current_tags': new_tags,
                'total_tags': len(new_tags)
            }
            
        except Exception as e:
            return {
                'status': 'error',
                'message': f'Failed to add tags to ticket: {str(e)}'
            }

    def remove_ticket_tags(self, ticket_id: int, tags: List[str]) -> Dict[str, Any]:
        """Remove specific tags from a ticket"""
        try:
            # Get current ticket
            ticket = self.client.tickets(id=ticket_id)
            if not ticket:
                return {
                    'status': 'error',
                    'message': f'Ticket {ticket_id} not found'
                }
            
            # Get current tags and remove specified ones
            current_tags = getattr(ticket, 'tags', [])
            new_tags = [tag for tag in current_tags if tag not in tags]
            
            # Update ticket with remaining tags
            update_data = {'tags': new_tags}
            self.client.tickets.update(ticket_id, update_data)
            
            removed_tags = [tag for tag in tags if tag in current_tags]
            
            return {
                'status': 'success',
                'ticket_id': ticket_id,
                'tags_removed': removed_tags,
                'current_tags': new_tags,
                'total_tags': len(new_tags)
            }
            
        except Exception as e:
            return {
                'status': 'error',
                'message': f'Failed to remove tags from ticket: {str(e)}'
            }

    def get_ticket_related_tickets(self, ticket_id: int) -> Dict[str, Any]:
        """Get tickets related to the current ticket"""
        try:
            # Get the main ticket
            ticket = self.client.tickets(id=ticket_id)
            if not ticket:
                return {
                    'status': 'error',
                    'message': f'Ticket {ticket_id} not found'
                }
            
            related_tickets = []
            
            # Find tickets from the same requester
            requester_id = getattr(ticket, 'requester_id', None)
            if requester_id:
                try:
                    requester_query = f"type:ticket requester:{requester_id}"
                    requester_tickets = list(self.client.search(query=requester_query))
                    for rel_ticket in requester_tickets[:10]:  # Limit to 10
                        if getattr(rel_ticket, 'id', None) != ticket_id:
                            related_tickets.append({
                                'id': getattr(rel_ticket, 'id', None),
                                'subject': getattr(rel_ticket, 'subject', 'No Subject'),
                                'status': getattr(rel_ticket, 'status', 'unknown'),
                                'relationship': 'same_requester',
                                'created_at': getattr(rel_ticket, 'created_at', None)
                            })
                except Exception:
                    pass
            
            # Find tickets with similar tags
            tags = getattr(ticket, 'tags', [])
            if tags:
                try:
                    tag_query = f"type:ticket tags:{tags[0]}"  # Use first tag
                    tag_tickets = list(self.client.search(query=tag_query))
                    for rel_ticket in tag_tickets[:5]:  # Limit to 5
                        if getattr(rel_ticket, 'id', None) != ticket_id:
                            related_tickets.append({
                                'id': getattr(rel_ticket, 'id', None),
                                'subject': getattr(rel_ticket, 'subject', 'No Subject'),
                                'status': getattr(rel_ticket, 'status', 'unknown'),
                                'relationship': 'similar_tags',
                                'created_at': getattr(rel_ticket, 'created_at', None)
                            })
                except Exception:
                    pass
            
            # Remove duplicates
            seen_ids = set()
            unique_related = []
            for rel_ticket in related_tickets:
                if rel_ticket['id'] not in seen_ids:
                    seen_ids.add(rel_ticket['id'])
                    unique_related.append(rel_ticket)
            
            return {
                'status': 'success',
                'ticket_id': ticket_id,
                'related_tickets_count': len(unique_related),
                'related_tickets': unique_related
            }
            
        except Exception as e:
            return {
                'status': 'error',
                'message': f'Failed to get related tickets: {str(e)}'
            }

    # =====================================
    # ORGANIZATION MANAGEMENT
    # =====================================
    
    def get_organizations(self, external_id: str = None, name: str = None, compact: bool = True, limit: Optional[int] = None) -> Dict[str, Any]:
        """Get organizations with optional filtering and compact mode support"""
        try:
            organizations = []
            
            if external_id:
                # Search by external ID
                try:
                    org = self.client.organizations(external_id=external_id)
                    if org:
                        organizations = [org]
                except Exception:
                    pass
            elif name:
                # Search by name
                try:
                    search_query = f"type:organization name:{name}"
                    search_results = list(self.client.search(query=search_query))
                    organizations = search_results
                except Exception:
                    pass
            else:
                # Get all organizations (paginated)
                organizations = list(self.client.organizations())
            
            # Apply limit
            limit = self._apply_limit(limit)
            limited_orgs = organizations[:limit]
            
            org_list = []
            for org in limited_orgs:
                if compact:
                    org_list.append(self._compact_organization(org))
                else:
                    org_data = {
                        'id': getattr(org, 'id', None),
                        'name': getattr(org, 'name', 'Unnamed Organization'),
                        'external_id': getattr(org, 'external_id', None),
                        'details': getattr(org, 'details', ''),
                        'notes': getattr(org, 'notes', ''),
                        'shared_tickets': getattr(org, 'shared_tickets', False),
                        'shared_comments': getattr(org, 'shared_comments', False),
                        'tags': getattr(org, 'tags', []),
                        'created_at': getattr(org, 'created_at', None),
                        'updated_at': getattr(org, 'updated_at', None)
                    }
                    org_list.append(org_data)
            
            response_data = {
                'status': 'success',
                'total_found': len(organizations),
                'showing': len(org_list),
                'compact_mode': compact,
                'organizations': org_list,
                'filters_applied': {
                    'external_id': external_id,
                    'name': name
                }
            }
            
            if len(organizations) > limit:
                response_data['note'] = f"Showing first {limit} of {len(organizations)} organizations."
            
            return response_data
            
        except Exception as e:
            return {
                'status': 'error',
                'message': f'Failed to get organizations: {str(e)}'
            }

    def get_organization_details(self, org_id: int) -> Dict[str, Any]:
        """Get detailed organization information including custom fields"""
        try:
            organization = self.client.organizations(id=org_id)
            if not organization:
                return {
                    'status': 'error',
                    'message': f'Organization {org_id} not found'
                }
            
            # Get organization details
            org_details = {
                'id': getattr(organization, 'id', None),
                'name': getattr(organization, 'name', 'Unnamed Organization'),
                'external_id': getattr(organization, 'external_id', None),
                'details': getattr(organization, 'details', ''),
                'notes': getattr(organization, 'notes', ''),
                'shared_tickets': getattr(organization, 'shared_tickets', False),
                'shared_comments': getattr(organization, 'shared_comments', False),
                'tags': getattr(organization, 'tags', []),
                'domain_names': getattr(organization, 'domain_names', []),
                'organization_fields': getattr(organization, 'organization_fields', {}),
                'created_at': getattr(organization, 'created_at', None),
                'updated_at': getattr(organization, 'updated_at', None)
            }
            
            # Get organization users count
            try:
                users = list(self.client.organizations.users(org_id))
                org_details['user_count'] = len(users)
            except Exception:
                org_details['user_count'] = 0
            
            # Get organization tickets count
            try:
                tickets_query = f"type:ticket organization:{org_id}"
                tickets = list(self.client.search(query=tickets_query))
                org_details['ticket_count'] = len(tickets)
            except Exception:
                org_details['ticket_count'] = 0
            
            return {
                'status': 'success',
                'organization': org_details
            }
            
        except Exception as e:
            return {
                'status': 'error',
                'message': f'Failed to get organization details: {str(e)}'
            }

    def update_organization(self, org_id: int, name: str = None, details: str = None, notes: str = None, **kwargs) -> Dict[str, Any]:
        """Update organization details"""
        try:
            # Verify organization exists
            organization = self.client.organizations(id=org_id)
            if not organization:
                return {
                    'status': 'error',
                    'message': f'Organization {org_id} not found'
                }
            
            # Build update data
            update_data = {}
            if name is not None:
                update_data['name'] = name
            if details is not None:
                update_data['details'] = details
            if notes is not None:
                update_data['notes'] = notes
            
            # Add any additional fields
            for key, value in kwargs.items():
                if value is not None:
                    update_data[key] = value
            
            if not update_data:
                return {
                    'status': 'error',
                    'message': 'No update data provided'
                }
            
            # Update the organization
            updated_org = self.client.organizations.update(org_id, update_data)
            
            return {
                'status': 'success',
                'organization_id': org_id,
                'updated_fields': list(update_data.keys()),
                'organization': {
                    'id': getattr(updated_org, 'id', None),
                    'name': getattr(updated_org, 'name', ''),
                    'details': getattr(updated_org, 'details', ''),
                    'notes': getattr(updated_org, 'notes', ''),
                    'updated_at': getattr(updated_org, 'updated_at', None)
                }
            }
            
        except Exception as e:
            return {
                'status': 'error',
                'message': f'Failed to update organization: {str(e)}'
            }

    def get_organization_users(self, org_id: int) -> Dict[str, Any]:
        """Get all users in an organization"""
        try:
            # Verify organization exists
            organization = self.client.organizations(id=org_id)
            if not organization:
                return {
                    'status': 'error',
                    'message': f'Organization {org_id} not found'
                }
            
            # Get organization users
            users = list(self.client.organizations.users(org_id))
            
            user_list = []
            for user in users:
                user_data = {
                    'id': getattr(user, 'id', None),
                    'name': getattr(user, 'name', 'Unnamed User'),
                    'email': getattr(user, 'email', ''),
                    'role': getattr(user, 'role', 'end-user'),
                    'active': getattr(user, 'active', True),
                    'verified': getattr(user, 'verified', False),
                    'suspended': getattr(user, 'suspended', False),
                    'last_login_at': getattr(user, 'last_login_at', None),
                    'created_at': getattr(user, 'created_at', None)
                }
                user_list.append(user_data)
            
            # Sort by role and name
            user_list.sort(key=lambda x: (x['role'], x['name']))
            
            return {
                'status': 'success',
                'organization_id': org_id,
                'organization_name': getattr(organization, 'name', 'Unknown'),
                'total_users': len(user_list),
                'users': user_list
            }
            
        except Exception as e:
            return {
                'status': 'error',
                'message': f'Failed to get organization users: {str(e)}'
            }

    # =====================================
    # ADVANCED USER MANAGEMENT
    # =====================================
    
    def create_user(self, name: str, email: str, role: str = "end-user", organization_id: int = None, **kwargs) -> Dict[str, Any]:
        """Create a new user"""
        try:
            # Build user data
            user_data = {
                'name': name,
                'email': email,
                'role': role
            }
            
            if organization_id:
                user_data['organization_id'] = organization_id
            
            # Add any additional fields
            for key, value in kwargs.items():
                if value is not None:
                    user_data[key] = value
            
            # Create the user
            new_user = self.client.users.create(user_data)
            
            return {
                'status': 'success',
                'user': {
                    'id': getattr(new_user, 'id', None),
                    'name': getattr(new_user, 'name', ''),
                    'email': getattr(new_user, 'email', ''),
                    'role': getattr(new_user, 'role', ''),
                    'organization_id': getattr(new_user, 'organization_id', None),
                    'active': getattr(new_user, 'active', True),
                    'verified': getattr(new_user, 'verified', False),
                    'created_at': getattr(new_user, 'created_at', None)
                }
            }
            
        except Exception as e:
            return {
                'status': 'error',
                'message': f'Failed to create user: {str(e)}'
            }

    def update_user(self, user_id: int, name: str = None, email: str = None, role: str = None, **kwargs) -> Dict[str, Any]:
        """Update user information"""
        try:
            # Verify user exists
            user = self.client.users(id=user_id)
            if not user:
                return {
                    'status': 'error',
                    'message': f'User {user_id} not found'
                }
            
            # Build update data
            update_data = {}
            if name is not None:
                update_data['name'] = name
            if email is not None:
                update_data['email'] = email
            if role is not None:
                update_data['role'] = role
            
            # Add any additional fields
            for key, value in kwargs.items():
                if value is not None:
                    update_data[key] = value
            
            if not update_data:
                return {
                    'status': 'error',
                    'message': 'No update data provided'
                }
            
            # Update the user
            updated_user = self.client.users.update(user_id, update_data)
            
            return {
                'status': 'success',
                'user_id': user_id,
                'updated_fields': list(update_data.keys()),
                'user': {
                    'id': getattr(updated_user, 'id', None),
                    'name': getattr(updated_user, 'name', ''),
                    'email': getattr(updated_user, 'email', ''),
                    'role': getattr(updated_user, 'role', ''),
                    'organization_id': getattr(updated_user, 'organization_id', None),
                    'active': getattr(updated_user, 'active', True),
                    'updated_at': getattr(updated_user, 'updated_at', None)
                }
            }
            
        except Exception as e:
            return {
                'status': 'error',
                'message': f'Failed to update user: {str(e)}'
            }

    def suspend_user(self, user_id: int, reason: str = None) -> Dict[str, Any]:
        """Suspend a user account"""
        try:
            # Verify user exists
            user = self.client.users(id=user_id)
            if not user:
                return {
                    'status': 'error',
                    'message': f'User {user_id} not found'
                }
            
            # Suspend the user
            update_data = {'suspended': True}
            if reason:
                update_data['notes'] = f"Suspended: {reason}"
            
            updated_user = self.client.users.update(user_id, update_data)
            
            return {
                'status': 'success',
                'user_id': user_id,
                'action': 'suspended',
                'reason': reason,
                'user': {
                    'id': getattr(updated_user, 'id', None),
                    'name': getattr(updated_user, 'name', ''),
                    'email': getattr(updated_user, 'email', ''),
                    'suspended': getattr(updated_user, 'suspended', False),
                    'updated_at': getattr(updated_user, 'updated_at', None)
                }
            }
            
        except Exception as e:
            return {
                'status': 'error',
                'message': f'Failed to suspend user: {str(e)}'
            }

    def search_users(self, query: str, role: str = None, organization_id: int = None) -> Dict[str, Any]:
        """Search for users with advanced filters"""
        try:
            # Build search query
            search_query = f"type:user {query}"
            
            if role:
                search_query += f" role:{role}"
            if organization_id:
                search_query += f" organization_id:{organization_id}"
            
            # Perform search
            search_results = list(self.client.search(query=search_query))
            
            user_list = []
            for user in search_results[:25]:  # Reduced limit to 25 results
                user_data = {
                    'id': getattr(user, 'id', None),
                    'name': getattr(user, 'name', 'Unnamed User'),
                    'email': getattr(user, 'email', ''),
                    'role': getattr(user, 'role', 'end-user'),
                    'organization_id': getattr(user, 'organization_id', None),
                    'active': getattr(user, 'active', True),
                    'verified': getattr(user, 'verified', False),
                    'suspended': getattr(user, 'suspended', False),
                    'last_login_at': getattr(user, 'last_login_at', None),
                    'created_at': getattr(user, 'created_at', None)
                }
                user_list.append(user_data)
            
            return {
                'status': 'success',
                'search_query': search_query,
                'total_results': len(user_list),
                'users': user_list,
                'filters_applied': {
                    'query': query,
                    'role': role,
                    'organization_id': organization_id
                }
            }
            
        except Exception as e:
            return {
                'status': 'error',
                'message': f'Failed to search users: {str(e)}'
            }

    def get_user_identities(self, user_id: int) -> Dict[str, Any]:
        """Get user identity information (email addresses, phone numbers, etc.)"""
        try:
            # Verify user exists
            user = self.client.users(id=user_id)
            if not user:
                return {
                    'status': 'error',
                    'message': f'User {user_id} not found'
                }
            
            # Get user identities
            identities = list(self.client.users.identities(user_id))
            
            identity_list = []
            for identity in identities:
                identity_data = {
                    'id': getattr(identity, 'id', None),
                    'type': getattr(identity, 'type', 'unknown'),
                    'value': getattr(identity, 'value', ''),
                    'primary': getattr(identity, 'primary', False),
                    'verified': getattr(identity, 'verified', False),
                    'created_at': getattr(identity, 'created_at', None),
                    'updated_at': getattr(identity, 'updated_at', None)
                }
                identity_list.append(identity_data)
            
            return {
                'status': 'success',
                'user_id': user_id,
                'user_name': getattr(user, 'name', 'Unknown'),
                'total_identities': len(identity_list),
                'identities': identity_list
            }
            
        except Exception as e:
            return {
                'status': 'error',
                'message': f'Failed to get user identities: {str(e)}'
            }

    # =====================================
    # GROUPS AND AGENT MANAGEMENT
    # =====================================
    
    def get_groups(self) -> Dict[str, Any]:
        """Get all support groups"""
        try:
            groups = list(self.client.groups())
            
            group_list = []
            for group in groups:
                group_data = {
                    'id': getattr(group, 'id', None),
                    'name': getattr(group, 'name', 'Unnamed Group'),
                    'description': getattr(group, 'description', ''),
                    'default': getattr(group, 'default', False),
                    'deleted': getattr(group, 'deleted', False),
                    'created_at': getattr(group, 'created_at', None),
                    'updated_at': getattr(group, 'updated_at', None)
                }
                
                # Get group member count
                try:
                    memberships = list(self.client.group_memberships(group_id=group.id))
                    group_data['member_count'] = len(memberships)
                except Exception:
                    group_data['member_count'] = 0
                
                group_list.append(group_data)
            
            return {
                'status': 'success',
                'total_groups': len(group_list),
                'groups': group_list
            }
            
        except Exception as e:
            return {
                'status': 'error',
                'message': f'Failed to get groups: {str(e)}'
            }

    def get_group_memberships(self, group_id: int = None, user_id: int = None) -> Dict[str, Any]:
        """Get group memberships"""
        try:
            memberships = []
            
            if group_id and user_id:
                # Get specific membership
                try:
                    membership = self.client.group_memberships(group_id=group_id, user_id=user_id)
                    if membership:
                        memberships = [membership]
                except Exception:
                    pass
            elif group_id:
                # Get all memberships for a group
                memberships = list(self.client.group_memberships(group_id=group_id))
            elif user_id:
                # Get all memberships for a user
                memberships = list(self.client.group_memberships(user_id=user_id))
            else:
                # Get all memberships (limited)
                memberships = list(self.client.group_memberships())[:100]
            
            membership_list = []
            for membership in memberships:
                membership_data = {
                    'id': getattr(membership, 'id', None),
                    'user_id': getattr(membership, 'user_id', None),
                    'group_id': getattr(membership, 'group_id', None),
                    'default': getattr(membership, 'default', False),
                    'created_at': getattr(membership, 'created_at', None),
                    'updated_at': getattr(membership, 'updated_at', None)
                }
                
                # Try to get user and group names
                try:
                    user = self.client.users(id=membership_data['user_id'])
                    membership_data['user_name'] = getattr(user, 'name', 'Unknown')
                except Exception:
                    membership_data['user_name'] = 'Unknown'
                
                try:
                    group = self.client.groups(id=membership_data['group_id'])
                    membership_data['group_name'] = getattr(group, 'name', 'Unknown')
                except Exception:
                    membership_data['group_name'] = 'Unknown'
                
                membership_list.append(membership_data)
            
            return {
                'status': 'success',
                'total_memberships': len(membership_list),
                'memberships': membership_list,
                'filters_applied': {
                    'group_id': group_id,
                    'user_id': user_id
                }
            }
            
        except Exception as e:
            return {
                'status': 'error',
                'message': f'Failed to get group memberships: {str(e)}'
            }

    def assign_agent_to_group(self, user_id: int, group_id: int, is_default: bool = False) -> Dict[str, Any]:
        """Assign an agent to a group"""
        try:
            # Verify user and group exist
            user = self.client.users(id=user_id)
            if not user:
                return {
                    'status': 'error',
                    'message': f'User {user_id} not found'
                }
            
            group = self.client.groups(id=group_id)
            if not group:
                return {
                    'status': 'error',
                    'message': f'Group {group_id} not found'
                }
            
            # Check if user is an agent
            user_role = getattr(user, 'role', 'end-user')
            if user_role not in ['agent', 'admin']:
                return {
                    'status': 'error',
                    'message': f'User must be an agent or admin to be assigned to groups. Current role: {user_role}'
                }
            
            # Create group membership
            membership_data = {
                'user_id': user_id,
                'group_id': group_id,
                'default': is_default
            }
            
            membership = self.client.group_memberships.create(membership_data)
            
            return {
                'status': 'success',
                'membership': {
                    'id': getattr(membership, 'id', None),
                    'user_id': user_id,
                    'user_name': getattr(user, 'name', 'Unknown'),
                    'group_id': group_id,
                    'group_name': getattr(group, 'name', 'Unknown'),
                    'default': getattr(membership, 'default', False),
                    'created_at': getattr(membership, 'created_at', None)
                }
            }
            
        except Exception as e:
            return {
                'status': 'error',
                'message': f'Failed to assign agent to group: {str(e)}'
            }

    def remove_agent_from_group(self, user_id: int, group_id: int) -> Dict[str, Any]:
        """Remove an agent from a group"""
        try:
            # Find the membership
            memberships = list(self.client.group_memberships(user_id=user_id))
            target_membership = None
            
            for membership in memberships:
                if getattr(membership, 'group_id', None) == group_id:
                    target_membership = membership
                    break
            
            if not target_membership:
                return {
                    'status': 'error',
                    'message': f'User {user_id} is not a member of group {group_id}'
                }
            
            # Delete the membership
            membership_id = getattr(target_membership, 'id', None)
            self.client.group_memberships.delete(membership_id)
            
            return {
                'status': 'success',
                'action': 'removed',
                'user_id': user_id,
                'group_id': group_id,
                'membership_id': membership_id
            }
            
        except Exception as e:
            return {
                'status': 'error',
                'message': f'Failed to remove agent from group: {str(e)}'
            }

    # =====================================
    # CUSTOM FIELDS AND TICKET FIELDS
    # =====================================
    
    def get_ticket_fields(self) -> Dict[str, Any]:
        """Get all ticket fields including custom fields with their configurations"""
        try:
            ticket_fields = list(self.client.ticket_fields())
            
            field_list = []
            for field in ticket_fields:
                field_data = {
                    'id': getattr(field, 'id', None),
                    'type': getattr(field, 'type', 'text'),
                    'title': getattr(field, 'title', 'Untitled Field'),
                    'description': getattr(field, 'description', ''),
                    'position': getattr(field, 'position', 0),
                    'active': getattr(field, 'active', True),
                    'required': getattr(field, 'required', False),
                    'collapsed_for_agents': getattr(field, 'collapsed_for_agents', False),
                    'regexp_for_validation': getattr(field, 'regexp_for_validation', None),
                    'title_in_portal': getattr(field, 'title_in_portal', ''),
                    'visible_in_portal': getattr(field, 'visible_in_portal', True),
                    'editable_in_portal': getattr(field, 'editable_in_portal', True),
                    'required_in_portal': getattr(field, 'required_in_portal', False),
                    'tag': getattr(field, 'tag', None),
                    'created_at': getattr(field, 'created_at', None),
                    'updated_at': getattr(field, 'updated_at', None)
                }
                
                # Add custom field options if they exist
                if hasattr(field, 'custom_field_options'):
                    options = getattr(field, 'custom_field_options', [])
                    field_data['options'] = [
                        {
                            'id': getattr(option, 'id', None),
                            'name': getattr(option, 'name', ''),
                            'value': getattr(option, 'value', ''),
                            'position': getattr(option, 'position', 0)
                        }
                        for option in options
                    ]
                
                field_list.append(field_data)
            
            # Sort by position
            field_list.sort(key=lambda x: x['position'])
            
            return {
                'status': 'success',
                'total_fields': len(field_list),
                'ticket_fields': field_list
            }
            
        except Exception as e:
            return {
                'status': 'error',
                'message': f'Failed to get ticket fields: {str(e)}'
            }

    def get_user_fields(self) -> Dict[str, Any]:
        """Get all user fields including custom fields"""
        try:
            user_fields = list(self.client.user_fields())
            
            field_list = []
            for field in user_fields:
                field_data = {
                    'id': getattr(field, 'id', None),
                    'type': getattr(field, 'type', 'text'),
                    'key': getattr(field, 'key', ''),
                    'title': getattr(field, 'title', 'Untitled Field'),
                    'description': getattr(field, 'description', ''),
                    'position': getattr(field, 'position', 0),
                    'active': getattr(field, 'active', True),
                    'system': getattr(field, 'system', False),
                    'regexp_for_validation': getattr(field, 'regexp_for_validation', None),
                    'created_at': getattr(field, 'created_at', None),
                    'updated_at': getattr(field, 'updated_at', None)
                }
                
                # Add custom field options if they exist
                if hasattr(field, 'custom_field_options'):
                    options = getattr(field, 'custom_field_options', [])
                    field_data['options'] = [
                        {
                            'id': getattr(option, 'id', None),
                            'name': getattr(option, 'name', ''),
                            'value': getattr(option, 'value', ''),
                            'position': getattr(option, 'position', 0)
                        }
                        for option in options
                    ]
                
                field_list.append(field_data)
            
            return {
                'status': 'success',
                'total_fields': len(field_list),
                'user_fields': field_list
            }
            
        except Exception as e:
            return {
                'status': 'error',
                'message': f'Failed to get user fields: {str(e)}'
            }

    def get_organization_fields(self) -> Dict[str, Any]:
        """Get all organization fields including custom fields"""
        try:
            org_fields = list(self.client.organization_fields())
            
            field_list = []
            for field in org_fields:
                field_data = {
                    'id': getattr(field, 'id', None),
                    'type': getattr(field, 'type', 'text'),
                    'key': getattr(field, 'key', ''),
                    'title': getattr(field, 'title', 'Untitled Field'),
                    'description': getattr(field, 'description', ''),
                    'position': getattr(field, 'position', 0),
                    'active': getattr(field, 'active', True),
                    'system': getattr(field, 'system', False),
                    'regexp_for_validation': getattr(field, 'regexp_for_validation', None),
                    'created_at': getattr(field, 'created_at', None),
                    'updated_at': getattr(field, 'updated_at', None)
                }
                
                # Add custom field options if they exist
                if hasattr(field, 'custom_field_options'):
                    options = getattr(field, 'custom_field_options', [])
                    field_data['options'] = [
                        {
                            'id': getattr(option, 'id', None),
                            'name': getattr(option, 'name', ''),
                            'value': getattr(option, 'value', ''),
                            'position': getattr(option, 'position', 0)
                        }
                        for option in options
                    ]
                
                field_list.append(field_data)
            
            return {
                'status': 'success',
                'total_fields': len(field_list),
                'organization_fields': field_list
            }
            
        except Exception as e:
            return {
                'status': 'error',
                'message': f'Failed to get organization fields: {str(e)}'
            }

    # =====================================
    # ADVANCED SEARCH AND FILTERING
    # =====================================
    
    def advanced_search(self, search_type: str, query: str, sort_by: str = None, sort_order: str = "desc") -> Dict[str, Any]:
        """Advanced search across different object types"""
        try:
            # Build search query
            if search_type not in ['tickets', 'users', 'organizations']:
                return {
                    'status': 'error',
                    'message': f'Invalid search type: {search_type}. Must be one of: tickets, users, organizations'
                }
            
            search_query = f"type:{search_type.rstrip('s')} {query}"
            
            # Perform search
            search_results = list(self.client.search(query=search_query, sort_by=sort_by, sort_order=sort_order))
            
            # Format results based on type
            formatted_results = []
            for result in search_results[:50]:  # Reduced limit to 50 results
                if search_type == 'tickets':
                    formatted_results.append({
                        'id': getattr(result, 'id', None),
                        'subject': getattr(result, 'subject', 'No Subject'),
                        'status': getattr(result, 'status', 'unknown'),
                        'priority': getattr(result, 'priority', 'normal'),
                        'requester_id': getattr(result, 'requester_id', None),
                        'assignee_id': getattr(result, 'assignee_id', None),
                        'created_at': getattr(result, 'created_at', None),
                        'updated_at': getattr(result, 'updated_at', None)
                    })
                elif search_type == 'users':
                    formatted_results.append({
                        'id': getattr(result, 'id', None),
                        'name': getattr(result, 'name', 'Unnamed User'),
                        'email': getattr(result, 'email', ''),
                        'role': getattr(result, 'role', 'end-user'),
                        'organization_id': getattr(result, 'organization_id', None),
                        'active': getattr(result, 'active', True),
                        'created_at': getattr(result, 'created_at', None)
                    })
                elif search_type == 'organizations':
                    # Truncate organization details to prevent large responses
                    details = getattr(result, 'details', '')
                    if len(details) > 200:
                        details = details[:197] + "..."
                    
                    formatted_results.append({
                        'id': getattr(result, 'id', None),
                        'name': getattr(result, 'name', 'Unnamed Organization'),
                        'external_id': getattr(result, 'external_id', None),
                        'details': details,
                        'created_at': getattr(result, 'created_at', None)
                    })
            
            return {
                'status': 'success',
                'search_type': search_type,
                'query': search_query,
                'total_results': len(formatted_results),
                'results': formatted_results,
                'sort_options': {
                    'sort_by': sort_by,
                    'sort_order': sort_order
                }
            }
            
        except Exception as e:
            return {
                'status': 'error',
                'message': f'Failed to perform advanced search: {str(e)}'
            }

    def export_search_results(self, query: str, object_type: str = "ticket") -> Dict[str, Any]:
        """Export search results for bulk processing"""
        try:
            # Build search query
            search_query = f"type:{object_type} {query}"
            
            # Perform search with larger limit for export
            search_results = list(self.client.search(query=search_query))
            
            export_data = []
            for result in search_results[:500]:  # Limit to 500 for export
                if object_type == 'ticket':
                    export_data.append({
                        'id': getattr(result, 'id', None),
                        'subject': getattr(result, 'subject', 'No Subject'),
                        'description': getattr(result, 'description', ''),
                        'status': getattr(result, 'status', 'unknown'),
                        'priority': getattr(result, 'priority', 'normal'),
                        'type': getattr(result, 'type', None),
                        'requester_id': getattr(result, 'requester_id', None),
                        'assignee_id': getattr(result, 'assignee_id', None),
                        'group_id': getattr(result, 'group_id', None),
                        'organization_id': getattr(result, 'organization_id', None),
                        'tags': getattr(result, 'tags', []),
                        'created_at': getattr(result, 'created_at', None),
                        'updated_at': getattr(result, 'updated_at', None),
                        'solved_at': getattr(result, 'solved_at', None)
                    })
                else:
                    # Generic export for other types
                    export_data.append({
                        'id': getattr(result, 'id', None),
                        'name': getattr(result, 'name', ''),
                        'created_at': getattr(result, 'created_at', None),
                        'updated_at': getattr(result, 'updated_at', None)
                    })
            
            return {
                'status': 'success',
                'export_type': object_type,
                'query': search_query,
                'total_exported': len(export_data),
                'export_timestamp': datetime.now().isoformat(),
                'data': export_data
            }
            
        except Exception as e:
            return {
                'status': 'error',
                'message': f'Failed to export search results: {str(e)}'
            }

    # =====================================
    # AUTOMATION AND BUSINESS RULES
    # =====================================
    
    def get_automations(self) -> Dict[str, Any]:
        """Get all automations with their conditions and actions"""
        try:
            automations = list(self.client.automations())
            
            automation_list = []
            for automation in automations:
                automation_data = {
                    'id': getattr(automation, 'id', None),
                    'title': getattr(automation, 'title', 'Untitled Automation'),
                    'active': getattr(automation, 'active', True),
                    'position': getattr(automation, 'position', 0),
                    'conditions': getattr(automation, 'conditions', {}),
                    'actions': getattr(automation, 'actions', []),
                    'created_at': getattr(automation, 'created_at', None),
                    'updated_at': getattr(automation, 'updated_at', None)
                }
                automation_list.append(automation_data)
            
            return {
                'status': 'success',
                'total_automations': len(automation_list),
                'automations': automation_list
            }
            
        except Exception as e:
            return {
                'status': 'error',
                'message': f'Failed to get automations: {str(e)}'
            }

    def get_triggers(self) -> Dict[str, Any]:
        """Get all triggers with their conditions and actions"""
        try:
            triggers = list(self.client.triggers())
            
            trigger_list = []
            for trigger in triggers:
                trigger_data = {
                    'id': getattr(trigger, 'id', None),
                    'title': getattr(trigger, 'title', 'Untitled Trigger'),
                    'active': getattr(trigger, 'active', True),
                    'position': getattr(trigger, 'position', 0),
                    'conditions': getattr(trigger, 'conditions', {}),
                    'actions': getattr(trigger, 'actions', []),
                    'category_id': getattr(trigger, 'category_id', None),
                    'created_at': getattr(trigger, 'created_at', None),
                    'updated_at': getattr(trigger, 'updated_at', None)
                }
                trigger_list.append(trigger_data)
            
            return {
                'status': 'success',
                'total_triggers': len(trigger_list),
                'triggers': trigger_list
            }
            
        except Exception as e:
            return {
                'status': 'error',
                'message': f'Failed to get triggers: {str(e)}'
            }

    def get_sla_policies(self) -> Dict[str, Any]:
        """Get all SLA policies and their configurations"""
        try:
            sla_policies = list(self.client.sla_policies())
            
            policy_list = []
            for policy in sla_policies:
                policy_data = {
                    'id': getattr(policy, 'id', None),
                    'title': getattr(policy, 'title', 'Untitled Policy'),
                    'description': getattr(policy, 'description', ''),
                    'position': getattr(policy, 'position', 0),
                    'filter': getattr(policy, 'filter', {}),
                    'policy_metrics': getattr(policy, 'policy_metrics', []),
                    'created_at': getattr(policy, 'created_at', None),
                    'updated_at': getattr(policy, 'updated_at', None)
                }
                policy_list.append(policy_data)
            
            return {
                'status': 'success',
                'total_policies': len(policy_list),
                'sla_policies': policy_list
            }
            
        except Exception as e:
            return {
                'status': 'error',
                'message': f'Failed to get SLA policies: {str(e)}'
            }

    # =====================================
    # KNOWLEDGE BASE INTEGRATION
    # =====================================
    
    def check_help_center_status(self) -> Dict[str, Any]:
        """Check if Help Center is available and accessible"""
        try:
            # Test sections access
            sections = list(self.client.help_center.sections())
            sections_count = len(sections)
            
            # Test direct Help Center article search (this is working)
            help_center_results = list(self.client.help_center.articles.search(query="help"))
            articles_via_help_center = len(help_center_results)
            
            # Get a quick sample of articles from the first few sections
            article_sample_count = 0
            sections_with_articles = 0
            
            for section in sections[:10]:  # Check first 10 sections
                try:
                    section_articles = list(self.client.help_center.sections.articles(section.id))
                    if len(section_articles) > 0:
                        sections_with_articles += 1
                        article_sample_count += len(section_articles)
                except Exception:
                    continue
            
            status = {
                'help_center_available': True,
                'sections_count': sections_count,
                'sections_with_articles': sections_with_articles,
                'sample_articles_count': article_sample_count,
                'search_working': articles_via_help_center > 0,
                'articles_found_via_search': articles_via_help_center,
                'sections_sample': [
                    {
                        'id': getattr(section, 'id', None),
                        'name': getattr(section, 'name', 'Unknown'),
                        'description': getattr(section, 'description', '')[:100] + '...' if len(getattr(section, 'description', '')) > 100 else getattr(section, 'description', '')
                    }
                    for section in sections[:5]  # Show first 5 sections
                ],
                'recommendation': f'Help Center is working! Found {sections_count} sections, {sections_with_articles} sections contain articles, and search found {articles_via_help_center} results.'
            }
            
            return {
                'status': 'success',
                'help_center_status': status
            }
            
        except Exception as e:
            return {
                'status': 'error',
                'message': f'Failed to check help center status: {str(e)}'
            }
    
    def search_help_center(self, query: str, locale: str = "en-us", category_id: int = None) -> Dict[str, Any]:
        """Search help center articles using the working method identified in testing"""
        try:
            # Use the Help Center articles search method (verified working in test)
            search_results = list(self.client.help_center.articles.search(query=query))
            
            # Filter by category if specified
            if category_id:
                search_results = [
                    article for article in search_results 
                    if getattr(article, 'category_id', None) == category_id
                ]
            
            # Filter by locale if specified and not default
            if locale and locale != "en-us":
                search_results = [
                    article for article in search_results 
                    if getattr(article, 'locale', 'en-us') == locale
                ]
            
            article_list = []
            for article in search_results[:50]:  # Limit to 50 results
                article_data = {
                    'id': getattr(article, 'id', None),
                    'title': getattr(article, 'title', 'Untitled Article'),
                    'body': getattr(article, 'body', '')[:300] + '...' if len(getattr(article, 'body', '')) > 300 else getattr(article, 'body', ''),
                    'html_url': getattr(article, 'html_url', ''),
                    'section_id': getattr(article, 'section_id', None),
                    'category_id': getattr(article, 'category_id', None),
                    'locale': getattr(article, 'locale', locale),
                    'outdated': getattr(article, 'outdated', False),
                    'draft': getattr(article, 'draft', False),
                    'promoted': getattr(article, 'promoted', False),
                    'vote_sum': getattr(article, 'vote_sum', 0),
                    'vote_count': getattr(article, 'vote_count', 0),
                    'created_at': str(getattr(article, 'created_at', '')),
                    'updated_at': str(getattr(article, 'updated_at', ''))
                }
                article_list.append(article_data)
            
            return {
                'status': 'success',
                'query': query,
                'locale': locale,
                'category_id': category_id,
                'total_results': len(article_list),
                'articles': article_list,
                'search_method': 'help_center.articles.search (verified working)'
            }
            
        except Exception as e:
            # Fallback to general search if Help Center search fails
            try:
                search_query = f'type:article {query}'
                if locale and locale != "en-us":
                    search_query += f' locale:{locale}'
                
                fallback_results = list(self.client.search(query=search_query))
                
                article_list = []
                for article in fallback_results[:50]:
                    article_data = {
                        'id': getattr(article, 'id', None),
                        'title': getattr(article, 'title', 'Untitled Article'),
                        'body': getattr(article, 'body', '')[:300] + '...' if len(getattr(article, 'body', '')) > 300 else getattr(article, 'body', ''),
                        'html_url': getattr(article, 'html_url', ''),
                        'section_id': getattr(article, 'section_id', None),
                        'locale': getattr(article, 'locale', locale),
                        'created_at': str(getattr(article, 'created_at', '')),
                        'updated_at': str(getattr(article, 'updated_at', ''))
                    }
                    article_list.append(article_data)
                
                return {
                    'status': 'success',
                    'query': query,
                    'locale': locale,
                    'category_id': category_id,
                    'total_results': len(article_list),
                    'articles': article_list,
                    'search_method': 'general_search_fallback',
                    'note': f'Used fallback search due to: {str(e)}'
                }
                
            except Exception as fallback_error:
                return {
                    'status': 'error',
                    'message': f'Both Help Center search and fallback failed. Help Center search error: {str(e)}, Fallback error: {str(fallback_error)}'
                }

    def get_help_center_articles(self, section_id: int = None, category_id: int = None) -> Dict[str, Any]:
        """Get help center articles by section, category, or all articles"""
        try:
            articles = []
            
            if section_id:
                # Get articles from specific section
                articles = list(self.client.help_center.sections.articles(section_id))
                filter_info = f"section {section_id}"
                
            elif category_id:
                # Get all sections in the category, then get articles from each section
                sections = list(self.client.help_center.categories.sections(category_id))
                for section in sections:
                    section_articles = list(self.client.help_center.sections.articles(section.id))
                    articles.extend(section_articles)
                filter_info = f"category {category_id}"
                
            else:
                # Get all articles using search (more reliable than sections)
                # Since sections might be empty but articles exist
                try:
                    # Use broad search queries to get most articles
                    search_queries = ["help", "how", "the", "a", "to", "and"]
                    all_articles = []
                    article_ids_seen = set()
                    
                    for search_query in search_queries:
                        try:
                            search_results = list(self.client.help_center.articles.search(query=search_query))
                            for article in search_results:
                                article_id = getattr(article, 'id', None)
                                if article_id and article_id not in article_ids_seen:
                                    all_articles.append(article)
                                    article_ids_seen.add(article_id)
                            
                            # Stop if we have enough articles
                            if len(all_articles) >= 100:
                                break
                        except Exception:
                            continue
                    
                    articles = all_articles[:100]  # Limit to 100 articles
                    filter_info = f"all articles via search (found {len(articles)} unique articles)"
                except Exception:
                    # Fallback: try getting from sections
                    sections = list(self.client.help_center.sections())
                    for section in sections[:20]:  # Limit to first 20 sections to avoid timeout
                        try:
                            section_articles = list(self.client.help_center.sections.articles(section.id))
                            articles.extend(section_articles)
                        except Exception:
                            continue  # Skip sections we can't access
                    filter_info = "all sections (fallback)"
            
            if not articles:
                return {
                    'status': 'success',
                    'section_id': section_id,
                    'category_id': category_id,
                    'total_articles': 0,
                    'articles': [],
                    'message': f'No articles found in {filter_info}',
                    'filter_applied': filter_info
                }
            
            # Process articles into standardized format
            article_list = []
            for article in articles[:100]:  # Limit to 100 articles
                try:
                    article_data = {
                        'id': getattr(article, 'id', None),
                        'title': getattr(article, 'title', 'Untitled Article'),
                        'body': getattr(article, 'body', '')[:500] + '...' if len(getattr(article, 'body', '')) > 500 else getattr(article, 'body', ''),
                        'html_url': getattr(article, 'html_url', ''),
                        'section_id': getattr(article, 'section_id', None),
                        'category_id': getattr(article, 'category_id', None),
                        'locale': getattr(article, 'locale', 'en-us'),
                        'outdated': getattr(article, 'outdated', False),
                        'draft': getattr(article, 'draft', False),
                        'promoted': getattr(article, 'promoted', False),
                        'position': getattr(article, 'position', 0),
                        'vote_sum': getattr(article, 'vote_sum', 0),
                        'vote_count': getattr(article, 'vote_count', 0),
                        'created_at': str(getattr(article, 'created_at', '')),
                        'updated_at': str(getattr(article, 'updated_at', ''))
                    }
                    article_list.append(article_data)
                except Exception:
                    # Skip articles that can't be processed
                    continue
            
            return {
                'status': 'success',
                'section_id': section_id,
                'category_id': category_id,
                'total_articles': len(article_list),
                'articles': article_list,
                'filter_applied': filter_info,
                'note': 'Articles retrieved successfully using Help Center API'
            }
            
        except Exception as e:
            # Fallback: try using search API
            try:
                if section_id:
                    search_query = f'type:article section_id:{section_id}'
                elif category_id:
                    search_query = f'type:article category_id:{category_id}'
                else:
                    search_query = 'type:article'
                
                fallback_results = list(self.client.search(query=search_query))[:100]
                
                article_list = []
                for article in fallback_results:
                    try:
                        article_data = {
                            'id': getattr(article, 'id', None),
                            'title': getattr(article, 'title', 'Untitled Article'),
                            'body': getattr(article, 'body', '')[:500] + '...' if len(getattr(article, 'body', '')) > 500 else getattr(article, 'body', ''),
                            'html_url': getattr(article, 'html_url', ''),
                            'section_id': getattr(article, 'section_id', None),
                            'created_at': str(getattr(article, 'created_at', '')),
                            'updated_at': str(getattr(article, 'updated_at', ''))
                        }
                        article_list.append(article_data)
                    except Exception:
                        continue
                
                return {
                    'status': 'success',
                    'section_id': section_id,
                    'category_id': category_id,
                    'total_articles': len(article_list),
                    'articles': article_list,
                    'search_method': 'search_api_fallback',
                    'note': f'Used search API fallback due to: {str(e)}'
                }
                
            except Exception as fallback_error:
                return {
                    'status': 'error',
                    'message': f'Failed to get help center articles. Primary error: {str(e)}, Fallback error: {str(fallback_error)}',
                    'section_id': section_id,
                    'category_id': category_id
                }
                return {
                    'status': 'success',
                    'message': 'No articles found matching the criteria',
                    'section_id': section_id,
                    'category_id': category_id,
                    'total_articles': 0,
                    'articles': []
                }
            
            article_list = []
            for article in articles:
                try:
                    article_data = {
                        'id': getattr(article, 'id', None),
                        'title': getattr(article, 'title', 'Untitled Article'),
                        'body': getattr(article, 'body', '')[:200] + '...' if len(getattr(article, 'body', '')) > 200 else getattr(article, 'body', ''),
                        'html_url': getattr(article, 'html_url', ''),
                        'section_id': getattr(article, 'section_id', None),
                        'locale': getattr(article, 'locale', 'en-us'),
                        'outdated': getattr(article, 'outdated', False),
                        'draft': getattr(article, 'draft', False),
                        'promoted': getattr(article, 'promoted', False),
                        'vote_sum': getattr(article, 'vote_sum', 0),
                        'vote_count': getattr(article, 'vote_count', 0),
                        'created_at': getattr(article, 'created_at', None),
                        'updated_at': getattr(article, 'updated_at', None)
                    }
                    article_list.append(article_data)
                except Exception:
                    # Skip articles that can't be processed
                    continue
            


    # =====================================
    # TICKET EVENTS AND AUDIT LOG
    # =====================================
    
    def get_ticket_audits(self, ticket_id: int, limit: int = 20, include_metadata: bool = False) -> Dict[str, Any]:
        """Get audit events for a ticket (recent change history) with data limits"""
        try:
            # Verify ticket exists
            ticket = self.client.tickets(id=ticket_id)
            if not ticket:
                return {
                    'status': 'error',
                    'message': f'Ticket {ticket_id} not found'
                }
            
            # Get ticket audits
            audits = list(self.client.tickets.audits(ticket_id))
            
            # Sort by creation date (newest first) and limit
            audits.sort(key=lambda a: getattr(a, 'created_at', ''), reverse=True)
            limited_audits = audits[:limit]
            
            audit_list = []
            for audit in limited_audits:
                audit_data = {
                    'id': getattr(audit, 'id', None),
                    'ticket_id': getattr(audit, 'ticket_id', ticket_id),
                    'created_at': getattr(audit, 'created_at', None),
                    'author_id': getattr(audit, 'author_id', None),
                    'events': []
                }
                
                # Include metadata only if requested (can be large)
                if include_metadata:
                    audit_data['metadata'] = getattr(audit, 'metadata', {})
                
                # Process audit events (limit to important ones)
                events = getattr(audit, 'events', [])
                for event in events[:10]:  # Limit events per audit
                    event_data = {
                        'id': getattr(event, 'id', None),
                        'type': getattr(event, 'type', 'unknown'),
                        'field_name': getattr(event, 'field_name', None)
                    }
                    
                    # Truncate large values
                    prev_val = getattr(event, 'previous_value', None)
                    if isinstance(prev_val, str) and len(prev_val) > 100:
                        prev_val = prev_val[:97] + "..."
                    event_data['previous_value'] = prev_val
                    
                    curr_val = getattr(event, 'value', None)
                    if isinstance(curr_val, str) and len(curr_val) > 100:
                        curr_val = curr_val[:97] + "..."
                    event_data['value'] = curr_val
                    
                    audit_data['events'].append(event_data)
                
                # Try to get author name (cache this in production)
                try:
                    author = self.client.users(id=audit_data['author_id'])
                    audit_data['author_name'] = getattr(author, 'name', 'Unknown')
                except Exception:
                    audit_data['author_name'] = 'Unknown'
                
                audit_list.append(audit_data)
            
            total_audits = len(audits)
            return {
                'status': 'success',
                'ticket_id': ticket_id,
                'total_audits': total_audits,
                'showing_audits': len(audit_list),
                'audits': audit_list,
                'note': f'Showing {len(audit_list)} most recent audits out of {total_audits} total' if total_audits > limit else None
            }
            
        except Exception as e:
            return {
                'status': 'error',
                'message': f'Failed to get ticket audits: {str(e)}'
            }

    def get_ticket_events(self, ticket_id: int) -> Dict[str, Any]:
        """Get all events for a ticket including system events"""
        try:
            # Get ticket audits (which contain events)
            audit_result = self.get_ticket_audits(ticket_id)
            
            if audit_result['status'] == 'error':
                return audit_result
            
            # Extract and flatten all events
            all_events = []
            for audit in audit_result['audits']:
                for event in audit['events']:
                    event_with_context = {
                        'audit_id': audit['id'],
                        'created_at': audit['created_at'],
                        'author_id': audit['author_id'],
                        'author_name': audit['author_name'],
                        'event_id': event['id'],
                        'event_type': event['type'],
                        'field_name': event['field_name'],
                        'previous_value': event['previous_value'],
                        'current_value': event['value']
                    }
                    all_events.append(event_with_context)
            
            # Sort events by creation time
            all_events.sort(key=lambda x: x['created_at'] or '', reverse=True)
            
            return {
                'status': 'success',
                'ticket_id': ticket_id,
                'total_events': len(all_events),
                'events': all_events
            }
            
        except Exception as e:
            return {
                'status': 'error',
                'message': f'Failed to get ticket events: {str(e)}'
            }

    # =====================================
    # COLLABORATION FEATURES
    # =====================================
    
    def add_ticket_collaborators(self, ticket_id: int, email_addresses: List[str]) -> Dict[str, Any]:
        """Add collaborators (CC) to a ticket"""
        try:
            # Verify ticket exists
            ticket = self.client.tickets(id=ticket_id)
            if not ticket:
                return {
                    'status': 'error',
                    'message': f'Ticket {ticket_id} not found'
                }
            
            # Get current collaborators
            current_collaborators = getattr(ticket, 'collaborator_ids', [])
            
            # Find or create users for email addresses
            added_collaborators = []
            failed_collaborators = []
            
            for email in email_addresses:
                try:
                    # Search for existing user
                    user_search = list(self.client.search(query=f"type:user email:{email}"))
                    
                    if user_search:
                        user = user_search[0]
                        user_id = getattr(user, 'id', None)
                        if user_id not in current_collaborators:
                            current_collaborators.append(user_id)
                            added_collaborators.append({
                                'email': email,
                                'user_id': user_id,
                                'name': getattr(user, 'name', 'Unknown'),
                                'status': 'existing_user'
                            })
                    else:
                        # Create new user
                        new_user_data = {
                            'name': email.split('@')[0],  # Use email prefix as name
                            'email': email,
                            'role': 'end-user'
                        }
                        new_user = self.client.users.create(new_user_data)
                        user_id = getattr(new_user, 'id', None)
                        
                        if user_id:
                            current_collaborators.append(user_id)
                            added_collaborators.append({
                                'email': email,
                                'user_id': user_id,
                                'name': getattr(new_user, 'name', 'Unknown'),
                                'status': 'new_user_created'
                            })
                            
                except Exception as e:
                    failed_collaborators.append({
                        'email': email,
                        'error': str(e)
                    })
            
            # Update ticket with new collaborators
            if added_collaborators:
                update_data = {'collaborator_ids': current_collaborators}
                self.client.tickets.update(ticket_id, update_data)
            
            return {
                'status': 'success',
                'ticket_id': ticket_id,
                'added_collaborators': added_collaborators,
                'failed_collaborators': failed_collaborators,
                'total_collaborators': len(current_collaborators)
            }
            
        except Exception as e:
            return {
                'status': 'error',
                'message': f'Failed to add ticket collaborators: {str(e)}'
            }

    def get_ticket_collaborators(self, ticket_id: int) -> Dict[str, Any]:
        """Get all collaborators on a ticket"""
        try:
            # Verify ticket exists
            ticket = self.client.tickets(id=ticket_id)
            if not ticket:
                return {
                    'status': 'error',
                    'message': f'Ticket {ticket_id} not found'
                }
            
            collaborator_ids = getattr(ticket, 'collaborator_ids', [])
            
            collaborator_list = []
            for collaborator_id in collaborator_ids:
                try:
                    user = self.client.users(id=collaborator_id)
                    collaborator_data = {
                        'id': getattr(user, 'id', None),
                        'name': getattr(user, 'name', 'Unknown'),
                        'email': getattr(user, 'email', ''),
                        'role': getattr(user, 'role', 'end-user'),
                        'active': getattr(user, 'active', True),
                        'organization_id': getattr(user, 'organization_id', None)
                    }
                    collaborator_list.append(collaborator_data)
                except Exception:
                    # Handle case where user might not exist
                    collaborator_list.append({
                        'id': collaborator_id,
                        'name': 'Unknown User',
                        'email': '',
                        'role': 'unknown',
                        'active': False,
                        'organization_id': None
                    })
            
            return {
                'status': 'success',
                'ticket_id': ticket_id,
                'total_collaborators': len(collaborator_list),
                'collaborators': collaborator_list
            }
            
        except Exception as e:
            return {
                'status': 'error',
                'message': f'Failed to get ticket collaborators: {str(e)}'
            }

    def remove_ticket_collaborators(self, ticket_id: int, user_ids: List[int]) -> Dict[str, Any]:
        """Remove collaborators from a ticket"""
        try:
            # Verify ticket exists
            ticket = self.client.tickets(id=ticket_id)
            if not ticket:
                return {
                    'status': 'error',
                    'message': f'Ticket {ticket_id} not found'
                }
            
            # Get current collaborators and remove specified ones
            current_collaborators = getattr(ticket, 'collaborator_ids', [])
            removed_collaborators = []
            
            for user_id in user_ids:
                if user_id in current_collaborators:
                    current_collaborators.remove(user_id)
                    removed_collaborators.append(user_id)
            
            # Update ticket
            if removed_collaborators:
                update_data = {'collaborator_ids': current_collaborators}
                self.client.tickets.update(ticket_id, update_data)
            
            return {
                'status': 'success',
                'ticket_id': ticket_id,
                'removed_collaborators': removed_collaborators,
                'remaining_collaborators': len(current_collaborators)
            }
            
        except Exception as e:
            return {
                'status': 'error',
                'message': f'Failed to remove ticket collaborators: {str(e)}'
            }

    # =====================================
    # ADVANCED REPORTING
    # =====================================
    
    def get_incremental_tickets(self, start_time: int, cursor: str = None) -> Dict[str, Any]:
        """Get tickets incrementally for data synchronization"""
        try:
            # Use incremental export API
            if cursor:
                # Continue from cursor
                result = self.client.incremental_tickets(start_time=start_time, cursor=cursor)
            else:
                # Start fresh
                result = self.client.incremental_tickets(start_time=start_time)
            
            # Format tickets
            ticket_list = []
            for ticket in result.tickets:
                ticket_data = {
                    'id': getattr(ticket, 'id', None),
                    'subject': getattr(ticket, 'subject', 'No Subject'),
                    'description': getattr(ticket, 'description', ''),
                    'status': getattr(ticket, 'status', 'unknown'),
                    'priority': getattr(ticket, 'priority', 'normal'),
                    'type': getattr(ticket, 'type', None),
                    'requester_id': getattr(ticket, 'requester_id', None),
                    'assignee_id': getattr(ticket, 'assignee_id', None),
                    'group_id': getattr(ticket, 'group_id', None),
                    'organization_id': getattr(ticket, 'organization_id', None),
                    'tags': getattr(ticket, 'tags', []),
                    'created_at': getattr(ticket, 'created_at', None),
                    'updated_at': getattr(ticket, 'updated_at', None),
                    'solved_at': getattr(ticket, 'solved_at', None)
                }
                ticket_list.append(ticket_data)
            
            return {
                'status': 'success',
                'start_time': start_time,
                'end_time': getattr(result, 'end_time', None),
                'next_page': getattr(result, 'next_page', None),
                'count': len(ticket_list),
                'tickets': ticket_list
            }
            
        except Exception as e:
            return {
                'status': 'error',
                'message': f'Failed to get incremental tickets: {str(e)}'
            }

    def get_ticket_metrics_detailed(self, ticket_id: int) -> Dict[str, Any]:
        """Get detailed metrics for a specific ticket including SLA data"""
        try:
            # Get the ticket
            ticket = self.client.tickets(id=ticket_id)
            if not ticket:
                return {
                    'status': 'error',
                    'message': f'Ticket {ticket_id} not found'
                }
            
            # Get ticket metrics
            try:
                metrics = self.client.ticket_metrics(ticket_id)
            except Exception:
                return {
                    'status': 'error',
                    'message': f'Metrics not available for ticket {ticket_id}'
                }
            
            # Format metrics data
            metrics_data = {
                'ticket_id': ticket_id,
                'ticket_subject': getattr(ticket, 'subject', 'No Subject'),
                'ticket_status': getattr(ticket, 'status', 'unknown'),
                'ticket_priority': getattr(ticket, 'priority', 'normal'),
                'created_at': getattr(ticket, 'created_at', None),
                'updated_at': getattr(ticket, 'updated_at', None),
                'solved_at': getattr(ticket, 'solved_at', None),
                'metrics': {
                    'agent_wait_time_in_minutes': {},
                    'assignee_stations': getattr(metrics, 'assignee_stations', 0),
                    'assignee_updated_at': getattr(metrics, 'assignee_updated_at', None),
                    'created_at': getattr(metrics, 'created_at', None),
                    'first_resolution_time_in_minutes': {},
                    'full_resolution_time_in_minutes': {},
                    'group_stations': getattr(metrics, 'group_stations', 0),
                    'initially_assigned_at': getattr(metrics, 'initially_assigned_at', None),
                    'latest_comment_added_at': getattr(metrics, 'latest_comment_added_at', None),
                    'on_hold_time_in_minutes': {},
                    'reopens': getattr(metrics, 'reopens', 0),
                    'replies': getattr(metrics, 'replies', 0),
                    'reply_time_in_minutes': {},
                    'requester_updated_at': getattr(metrics, 'requester_updated_at', None),
                    'requester_wait_time_in_minutes': {},
                    'solved_at': getattr(metrics, 'solved_at', None),
                    'status_updated_at': getattr(metrics, 'status_updated_at', None),
                    'updated_at': getattr(metrics, 'updated_at', None)
                }
            }
            
            # Extract time-based metrics
            time_metrics = [
                'agent_wait_time_in_minutes',
                'first_resolution_time_in_minutes', 
                'full_resolution_time_in_minutes',
                'on_hold_time_in_minutes',
                'reply_time_in_minutes',
                'requester_wait_time_in_minutes'
            ]
            
            for metric_name in time_metrics:
                metric_obj = getattr(metrics, metric_name, None)
                if metric_obj:
                    metrics_data['metrics'][metric_name] = {
                        'business_minutes': getattr(metric_obj, 'business_minutes', None),
                        'calendar_minutes': getattr(metric_obj, 'calendar_minutes', None)
                    }
            
            # Calculate additional derived metrics
            created_at = getattr(ticket, 'created_at', None)
            solved_at = getattr(ticket, 'solved_at', None)
            
            if created_at and solved_at:
                from datetime import datetime
                created = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                solved = datetime.fromisoformat(solved_at.replace('Z', '+00:00'))
                total_resolution_hours = (solved - created).total_seconds() / 3600
                metrics_data['derived_metrics'] = {
                    'total_resolution_hours': round(total_resolution_hours, 2),
                    'business_days': round(total_resolution_hours / 24, 2)
                }
            
            return {
                'status': 'success',
                'data': metrics_data
            }
            
        except Exception as e:
            return {
                'status': 'error',
                'message': f'Failed to get detailed ticket metrics: {str(e)}'
            }

    def generate_agent_activity_report(self, agent_id: int, start_date: str, end_date: str) -> Dict[str, Any]:
        """Generate detailed activity report for an agent"""
        try:
            from datetime import datetime, timedelta
            
            # Verify agent exists
            agent = self.client.users(id=agent_id)
            if not agent:
                return {
                    'status': 'error',
                    'message': f'Agent {agent_id} not found'
                }
            
            # Build search queries for different activities
            date_range = f"created>={start_date} created<={end_date}"
            
            activities = {}
            
            # Tickets created
            try:
                created_query = f"type:ticket assignee:{agent_id} {date_range}"
                created_tickets = list(self.client.search(query=created_query))
                activities['tickets_created'] = len(created_tickets)
            except Exception:
                activities['tickets_created'] = 0
            
            # Tickets solved
            try:
                solved_query = f"type:ticket assignee:{agent_id} status:solved updated>={start_date} updated<={end_date}"
                solved_tickets = list(self.client.search(query=solved_query))
                activities['tickets_solved'] = len(solved_tickets)
            except Exception:
                activities['tickets_solved'] = 0
            
            # Comments added (approximate via updated tickets)
            try:
                updated_query = f"type:ticket assignee:{agent_id} updated>={start_date} updated<={end_date}"
                updated_tickets = list(self.client.search(query=updated_query))
                activities['tickets_updated'] = len(updated_tickets)
            except Exception:
                activities['tickets_updated'] = 0
            
            # Calculate performance metrics
            performance = {
                'productivity_score': 0,
                'resolution_rate': 0,
                'activity_level': 'normal'
            }
            
            if activities['tickets_created'] > 0:
                performance['resolution_rate'] = round(
                    (activities['tickets_solved'] / activities['tickets_created']) * 100, 2
                )
            
            # Determine activity level
            total_activity = activities['tickets_created'] + activities['tickets_solved'] + activities['tickets_updated']
            if total_activity > 50:
                performance['activity_level'] = 'high'
            elif total_activity < 10:
                performance['activity_level'] = 'low'
            
            performance['productivity_score'] = min(100, total_activity * 2)
            
            # Get ticket details for analysis
            ticket_analysis = {
                'by_status': {},
                'by_priority': {},
                'by_type': {},
                'response_times': []
            }
            
            for ticket in created_tickets[:50]:  # Analyze up to 50 tickets
                status = getattr(ticket, 'status', 'unknown')
                priority = getattr(ticket, 'priority', 'normal')
                ticket_type = getattr(ticket, 'type', 'incident')
                
                ticket_analysis['by_status'][status] = ticket_analysis['by_status'].get(status, 0) + 1
                ticket_analysis['by_priority'][priority] = ticket_analysis['by_priority'].get(priority, 0) + 1
                ticket_analysis['by_type'][ticket_type] = ticket_analysis['by_type'].get(ticket_type, 0) + 1
            
            return {
                'status': 'success',
                'agent': {
                    'id': agent_id,
                    'name': getattr(agent, 'name', 'Unknown Agent'),
                    'email': getattr(agent, 'email', ''),
                    'role': getattr(agent, 'role', 'agent')
                },
                'report_period': {
                    'start_date': start_date,
                    'end_date': end_date
                },
                'activities': activities,
                'performance': performance,
                'ticket_analysis': ticket_analysis,
                'report_generated_at': datetime.now().isoformat()
            }
            
        except Exception as e:
            return {
                'status': 'error',
                'message': f'Failed to generate agent activity report: {str(e)}'
            }

    def get_ticket_comments_full(self, ticket_id: int, limit: int = None) -> List[Dict[str, Any]]:
        """
        Get full, untruncated comments for a ticket - use when you need complete data.
        WARNING: May return large amounts of data.
        """
        try:
            comments = list(self.client.tickets.comments(ticket=ticket_id))
            
            # Sort by creation date (newest first)
            comments.sort(key=lambda c: getattr(c, 'created_at', ''), reverse=True)
            
            # Apply limit if specified
            if limit:
                comments = comments[:limit]
            
            result = []
            for comment in comments:
                comment_data = {
                    'id': getattr(comment, 'id', None),
                    'author_id': getattr(comment, 'author_id', None),
                    'body': getattr(comment, 'body', ''),  # Full, untruncated
                    'html_body': getattr(comment, 'html_body', ''),  # Full, untruncated
                    'public': getattr(comment, 'public', True),
                    'created_at': str(getattr(comment, 'created_at', ''))
                }
                result.append(comment_data)
            
            return result
        except Exception as e:
            raise Exception(f"Failed to get full comments for ticket {ticket_id}: {str(e)}")

    def get_ticket_audits_full(self, ticket_id: int, limit: int = None) -> Dict[str, Any]:
        """
        Get full, untruncated audit history for a ticket - use when you need complete data.
        WARNING: May return large amounts of data.
        """
        try:
            # Verify ticket exists
            ticket = self.client.tickets(id=ticket_id)
            if not ticket:
                return {
                    'status': 'error',
                    'message': f'Ticket {ticket_id} not found'
                }
            
            # Get all ticket audits
            audits = list(self.client.tickets.audits(ticket_id))
            
            # Sort by creation date (newest first)
            audits.sort(key=lambda a: getattr(a, 'created_at', ''), reverse=True)
            
            # Apply limit if specified
            if limit:
                audits = audits[:limit]
            
            audit_list = []
            for audit in audits:
                audit_data = {
                    'id': getattr(audit, 'id', None),
                    'ticket_id': getattr(audit, 'ticket_id', ticket_id),
                    'created_at': getattr(audit, 'created_at', None),
                    'author_id': getattr(audit, 'author_id', None),
                    'metadata': getattr(audit, 'metadata', {}),  # Full metadata
                    'events': []
                }
                
                # Process ALL audit events (no limit)
                events = getattr(audit, 'events', [])
                for event in events:
                    event_data = {
                        'id': getattr(event, 'id', None),
                        'type': getattr(event, 'type', 'unknown'),
                        'field_name': getattr(event, 'field_name', None),
                        'previous_value': getattr(event, 'previous_value', None),  # Full, untruncated
                        'value': getattr(event, 'value', None)  # Full, untruncated
                    }
                    audit_data['events'].append(event_data)
                
                # Try to get author name
                try:
                    author = self.client.users(id=audit_data['author_id'])
                    audit_data['author_name'] = getattr(author, 'name', 'Unknown')
                except Exception:
                    audit_data['author_name'] = 'Unknown'
                
                audit_list.append(audit_data)
            
            total_audits = len(list(self.client.tickets.audits(ticket_id)))
            return {
                'status': 'success',
                'ticket_id': ticket_id,
                'total_audits': total_audits,
                'showing_audits': len(audit_list),
                'audits': audit_list,
                'note': 'FULL DATA - untruncated audit history'
            }
            
        except Exception as e:
            return {
                'status': 'error',
                'message': f'Failed to get full ticket audits: {str(e)}'
            }



    def get_data_limits_info(self) -> Dict[str, Any]:
        """
        Get information about data limits and how to access full data when needed.
        """
        return {
            'status': 'success',
            'data_limits': {
                'purpose': 'Data limits prevent conversation overflow in Claude Desktop',
                'standard_limits': {
                    'ticket_comments': '10 comments, 300 chars each',
                    'ticket_audits': '20 audits, 100 chars per value',
                    'search_tickets': '20 results by default, configurable up to 100',
                    'search_users': '25 results',
                    'advanced_search': '50 results'
                },
                'search_tickets_options': {
                    'limit': {
                        'description': 'Maximum tickets to return (1-100)',
                        'default': 20
                    },
                    'compact': {
                        'description': 'Return minimal data for better performance',
                        'default': True
                    },
                    'include_description': {
                        'description': 'Include full ticket descriptions',
                        'default': False
                    },
                    'max_response_size': {
                        'description': 'Auto-truncate if response exceeds this size',
                        'default': '50KB'
                    },
                    'summary_mode': {
                        'description': 'Return summary statistics instead of full tickets',
                        'default': False
                    },
                    'categorize': {
                        'description': 'Add automatic categorization to results',
                        'default': False
                    }
                },
                'pagination_support': {
                    'page': 'Page number for pagination',
                    'cursor': 'Cursor for continuing from previous results'
                }
            },
            'usage_recommendations': {
                'quick_search': {
                    'description': 'Fast search with minimal data',
                    'parameters': {
                        'compact': True,
                        'limit': 20
                    }
                },
                'detailed_search': {
                    'description': 'Full ticket details',
                    'parameters': {
                        'compact': False,
                        'include_description': True,
                        'limit': 50
                    }
                },
                'large_dataset': {
                    'description': 'Handle large result sets',
                    'parameters': {
                        'summary_mode': True,
                        'categorize': True
                    }
                },
                'analysis': {
                    'description': 'Detailed analysis with categories',
                    'parameters': {
                        'categorize': True,
                        'include_description': True,
                        'limit': 100
                    }
                }
            },
            'examples': {
                'basic_search': {
                    'description': 'Simple ticket search',
                    'call': 'search_tickets("status:open priority:high")'
                },
                'detailed_search': {
                    'description': 'Search with full details',
                    'call': 'search_tickets("status:open", compact=False, include_description=True, limit=50)'
                },
                'large_dataset': {
                    'description': 'Handle large result set',
                    'call': 'search_tickets("status:open", summary_mode=True)'
                },
                'categorized_search': {
                    'description': 'Search with automatic categorization',
                    'call': 'search_tickets("status:open", categorize=True, limit=100)'
                }
            }
        }
