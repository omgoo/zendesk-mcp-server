from typing import Dict, Any, List, Optional
import urllib.parse

from zenpy import Zenpy
from zenpy.lib.api_objects import Comment


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

    def get_ticket_comments(self, ticket_id: int) -> List[Dict[str, Any]]:
        """
        Get all comments for a specific ticket.
        """
        try:
            comments = self.client.tickets.comments(ticket=ticket_id)
            return [{
                'id': comment.id,
                'author_id': comment.author_id,
                'body': comment.body,
                'html_body': comment.html_body,
                'public': comment.public,
                'created_at': str(comment.created_at)
            } for comment in comments]
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

    def search_tickets(self, query: str, sort_by: str = "created_at", sort_order: str = "desc", compact: bool = False) -> List[Dict[str, Any]]:
        """
        Search for tickets using the Zendesk Search API.
        
        Args:
            query: Search query string
            sort_by: Field to sort by (created_at, updated_at, priority, status, etc.)
            sort_order: Sort order (asc or desc)
            compact: If True, returns minimal data without descriptions and comments for better performance
        """
        try:
            # Ensure the query includes type:ticket if not already specified
            if "type:ticket" not in query:
                query = f"type:ticket {query}"
            
            search_results = self.client.search(
                query=query,
                sort_by=sort_by,
                sort_order=sort_order
            )
            
            tickets = []
            for ticket in search_results:
                ticket_data = {
                    "id": getattr(ticket, 'id', None),
                    "subject": getattr(ticket, 'subject', 'No subject'),
                    "status": getattr(ticket, 'status', None),
                    "priority": getattr(ticket, 'priority', None),
                    "created_at": getattr(ticket, 'created_at', None),
                    "updated_at": getattr(ticket, 'updated_at', None),
                    "requester_id": getattr(ticket, 'requester_id', None),
                    "assignee_id": getattr(ticket, 'assignee_id', None),
                    "organization_id": getattr(ticket, 'organization_id', None),
                    "tags": getattr(ticket, 'tags', [])
                }
                
                # Only include verbose fields if not in compact mode
                if not compact:
                    description = getattr(ticket, 'description', '')
                    # Truncate very long descriptions
                    if len(description) > 500:
                        description = description[:497] + "..."
                    ticket_data["description"] = description
                else:
                    # In compact mode, truncate subject if very long
                    subject = ticket_data["subject"]
                    if len(subject) > 100:
                        ticket_data["subject"] = subject[:97] + "..."
                
                tickets.append(ticket_data)
                
            return tickets
            
        except Exception as e:
            # Improve error messaging for different types of failures
            error_msg = str(e)
            if "SSL" in error_msg or "ssl" in error_msg.lower():
                raise Exception(f"SSL connection error. Check your ZENDESK_SUBDOMAIN setting. Original error: {error_msg}")
            elif "401" in error_msg or "authentication" in error_msg.lower():
                raise Exception(f"Authentication failed. Check your ZENDESK_EMAIL and ZENDESK_API_KEY. Original error: {error_msg}")
            elif "403" in error_msg or "permission" in error_msg.lower():
                raise Exception(f"Permission denied. Your API token may not have search permissions. Original error: {error_msg}")
            else:
                raise Exception(f"Search failed: {error_msg}")

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

    def get_ticket_metrics(self, ticket_id: Optional[int] = None) -> Dict[str, Any]:
        """
        Get ticket metrics for analysis. If ticket_id provided, get metrics for that ticket,
        otherwise get aggregate metrics.
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
                
                return metrics
        except Exception as e:
            raise Exception(f"Failed to get ticket metrics: {str(e)}")

    def get_user_tickets(self, user_id: int, ticket_type: str = "requested") -> List[Dict[str, Any]]:
        """
        Get tickets for a specific user.
        
        Args:
            user_id: User ID
            ticket_type: Type of tickets (requested, ccd, assigned)
        """
        try:
            if ticket_type == "requested":
                tickets = self.client.users.tickets.requested(user=user_id)
            elif ticket_type == "ccd":
                tickets = self.client.users.tickets.ccd(user=user_id)
            elif ticket_type == "assigned":
                tickets = self.client.users.tickets.assigned(user=user_id)
            else:
                raise ValueError(f"Invalid ticket_type: {ticket_type}")
            
            return [{
                'id': ticket.id,
                'subject': ticket.subject,
                'status': ticket.status,
                'priority': ticket.priority,
                'created_at': str(ticket.created_at),
                'updated_at': str(ticket.updated_at)
            } for ticket in tickets]
        except Exception as e:
            raise Exception(f"Failed to get {ticket_type} tickets for user {user_id}: {str(e)}")

    def get_organization_tickets(self, org_id: int) -> List[Dict[str, Any]]:
        """
        Get all tickets for a specific organization.
        """
        try:
            tickets = self.client.organizations.tickets(organization=org_id)
            return [{
                'id': ticket.id,
                'subject': ticket.subject,
                'status': ticket.status,
                'priority': ticket.priority,
                'requester_id': ticket.requester_id,
                'assignee_id': ticket.assignee_id,
                'created_at': str(ticket.created_at),
                'updated_at': str(ticket.updated_at)
            } for ticket in tickets]
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
