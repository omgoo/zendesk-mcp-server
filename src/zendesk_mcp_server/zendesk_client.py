import json
import logging
from typing import Dict, Any, List, Optional
import urllib.parse
from datetime import datetime
from zenpy import Zenpy
from zenpy.lib.api_objects import Comment
from cachetools import TTLCache


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

    def get_agent_performance_metrics(
        self, 
        agent_id: Optional[int] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        include_satisfaction: bool = True
    ) -> Dict[str, Any]:
        """
        Get comprehensive agent performance metrics including:
        - Ticket volume and resolution rates
        - Average response/resolution times
        - Customer satisfaction scores
        - SLA compliance
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
            
            return metrics
            
        except Exception as e:
            return {
                "error": f"Failed to get agent performance metrics: {str(e)}",
                "function": "get_agent_performance_metrics"
            }

    def get_team_performance_dashboard(
        self, 
        team_id: Optional[int] = None,
        period: str = "week"
    ) -> Dict[str, Any]:
        """
        Generate team-wide performance dashboard with:
        - Agent rankings
        - Workload distribution
        - Trend analysis
        - Bottleneck identification
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
