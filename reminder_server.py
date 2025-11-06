import sys
import json
import logging
from datetime import datetime, timedelta
from mcp.server.fastmcp import FastMCP

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stderr
)
logger = logging.getLogger("reminder_server")

mcp = FastMCP("Xiaozhi Reminder Server")

reminders = {}
reminder_counter = 0


def get_next_id():
    global reminder_counter
    reminder_counter += 1
    return str(reminder_counter)


def parse_datetime(datetime_str):
    formats = [
        "%Y-%m-%d %H:%M",
        "%Y-%m-%d %H:%M:%S",
        "%Y/%m/%d %H:%M",
        "%d-%m-%Y %H:%M",
        "%m/%d/%Y %H:%M"
    ]
    
    for fmt in formats:
        try:
            return datetime.strptime(datetime_str, fmt)
        except ValueError:
            continue
    
    raise ValueError(f"Unable to parse datetime: {datetime_str}. Use format: YYYY-MM-DD HH:MM")


@mcp.tool()
def add_reminder(title: str, datetime_str: str, description: str = ""):
    """Add a new reminder with title, datetime (YYYY-MM-DD HH:MM), and optional description"""
    try:
        reminder_time = parse_datetime(datetime_str)
        
        if reminder_time < datetime.now():
            return json.dumps({
                "success": False,
                "error": "Cannot create reminder for past time"
            }, indent=2)
        
        reminder_id = get_next_id()
        reminders[reminder_id] = {
            "id": reminder_id,
            "title": title,
            "description": description,
            "datetime": reminder_time.isoformat(),
            "completed": False,
            "created_at": datetime.now().isoformat()
        }
        
        logger.info(f"Added reminder: {reminder_id} - {title}")
        
        return json.dumps({
            "success": True,
            "message": "Reminder added successfully",
            "reminder": reminders[reminder_id]
        }, indent=2)
        
    except ValueError as e:
        return json.dumps({
            "success": False,
            "error": str(e)
        }, indent=2)
    except Exception as e:
        logger.error(f"Error adding reminder: {e}")
        return json.dumps({
            "success": False,
            "error": f"Failed to add reminder: {str(e)}"
        }, indent=2)


@mcp.tool()
def list_reminders(include_completed: str = "false"):
    """List all reminders, optionally include completed ones (true/false)"""
    try:
        show_completed = include_completed.lower() == "true"
        
        filtered_reminders = [
            r for r in reminders.values()
            if show_completed or not r["completed"]
        ]
        
        if not filtered_reminders:
            return json.dumps({
                "success": True,
                "message": "No reminders found",
                "reminders": []
            }, indent=2)
        
        sorted_reminders = sorted(
            filtered_reminders,
            key=lambda x: x["datetime"]
        )
        
        return json.dumps({
            "success": True,
            "count": len(sorted_reminders),
            "reminders": sorted_reminders
        }, indent=2)
        
    except Exception as e:
        logger.error(f"Error listing reminders: {e}")
        return json.dumps({
            "success": False,
            "error": f"Failed to list reminders: {str(e)}"
        }, indent=2)


@mcp.tool()
def get_upcoming_reminders(hours: str = "24"):
    """Get reminders due within the next N hours (default 24)"""
    try:
        hours_int = int(hours)
        now = datetime.now()
        future_time = now + timedelta(hours=hours_int)
        
        upcoming = []
        for reminder in reminders.values():
            if reminder["completed"]:
                continue
                
            reminder_dt = datetime.fromisoformat(reminder["datetime"])
            if now <= reminder_dt <= future_time:
                time_until = reminder_dt - now
                hours_until = time_until.total_seconds() / 3600
                
                reminder_copy = reminder.copy()
                reminder_copy["hours_until"] = round(hours_until, 1)
                upcoming.append(reminder_copy)
        
        upcoming.sort(key=lambda x: x["datetime"])
        
        return json.dumps({
            "success": True,
            "count": len(upcoming),
            "time_window_hours": hours_int,
            "reminders": upcoming
        }, indent=2)
        
    except ValueError:
        return json.dumps({
            "success": False,
            "error": "Hours must be a valid number"
        }, indent=2)
    except Exception as e:
        logger.error(f"Error getting upcoming reminders: {e}")
        return json.dumps({
            "success": False,
            "error": f"Failed to get upcoming reminders: {str(e)}"
        }, indent=2)


@mcp.tool()
def check_overdue_reminders():
    """Check for overdue reminders that need immediate attention"""
    try:
        now = datetime.now()
        overdue = []
        
        for reminder in reminders.values():
            if reminder["completed"]:
                continue
                
            reminder_dt = datetime.fromisoformat(reminder["datetime"])
            if reminder_dt < now:
                time_overdue = now - reminder_dt
                hours_overdue = time_overdue.total_seconds() / 3600
                
                reminder_copy = reminder.copy()
                reminder_copy["hours_overdue"] = round(hours_overdue, 1)
                overdue.append(reminder_copy)
        
        overdue.sort(key=lambda x: x["datetime"])
        
        if not overdue:
            return json.dumps({
                "success": True,
                "message": "No overdue reminders",
                "reminders": []
            }, indent=2)
        
        return json.dumps({
            "success": True,
            "count": len(overdue),
            "message": f"ALERT: You have {len(overdue)} overdue reminder(s)!",
            "reminders": overdue
        }, indent=2)
        
    except Exception as e:
        logger.error(f"Error checking overdue reminders: {e}")
        return json.dumps({
            "success": False,
            "error": f"Failed to check overdue reminders: {str(e)}"
        }, indent=2)


@mcp.tool()
def complete_reminder(reminder_id: str):
    """Mark a reminder as completed by its ID"""
    try:
        if reminder_id not in reminders:
            return json.dumps({
                "success": False,
                "error": f"Reminder with ID {reminder_id} not found"
            }, indent=2)
        
        reminders[reminder_id]["completed"] = True
        reminders[reminder_id]["completed_at"] = datetime.now().isoformat()
        
        logger.info(f"Completed reminder: {reminder_id}")
        
        return json.dumps({
            "success": True,
            "message": "Reminder marked as completed",
            "reminder": reminders[reminder_id]
        }, indent=2)
        
    except Exception as e:
        logger.error(f"Error completing reminder: {e}")
        return json.dumps({
            "success": False,
            "error": f"Failed to complete reminder: {str(e)}"
        }, indent=2)


@mcp.tool()
def delete_reminder(reminder_id: str):
    """Delete a reminder by its ID"""
    try:
        if reminder_id not in reminders:
            return json.dumps({
                "success": False,
                "error": f"Reminder with ID {reminder_id} not found"
            }, indent=2)
        
        deleted_reminder = reminders.pop(reminder_id)
        logger.info(f"Deleted reminder: {reminder_id}")
        
        return json.dumps({
            "success": True,
            "message": "Reminder deleted successfully",
            "deleted_reminder": deleted_reminder
        }, indent=2)
        
    except Exception as e:
        logger.error(f"Error deleting reminder: {e}")
        return json.dumps({
            "success": False,
            "error": f"Failed to delete reminder: {str(e)}"
        }, indent=2)


@mcp.tool()
def search_reminders(query: str):
    """Search reminders by title or description"""
    try:
        query_lower = query.lower()
        results = []
        
        for reminder in reminders.values():
            title_match = query_lower in reminder["title"].lower()
            desc_match = query_lower in reminder["description"].lower()
            
            if title_match or desc_match:
                results.append(reminder)
        
        if not results:
            return json.dumps({
                "success": True,
                "message": f"No reminders found matching '{query}'",
                "reminders": []
            }, indent=2)
        
        results.sort(key=lambda x: x["datetime"])
        
        return json.dumps({
            "success": True,
            "count": len(results),
            "query": query,
            "reminders": results
        }, indent=2)
        
    except Exception as e:
        logger.error(f"Error searching reminders: {e}")
        return json.dumps({
            "success": False,
            "error": f"Failed to search reminders: {str(e)}"
        }, indent=2)


@mcp.tool()
def get_reminder_stats():
    """Get statistics about all reminders"""
    try:
        total = len(reminders)
        completed = sum(1 for r in reminders.values() if r["completed"])
        pending = total - completed
        
        now = datetime.now()
        overdue = 0
        upcoming_24h = 0
        
        for reminder in reminders.values():
            if reminder["completed"]:
                continue
            
            reminder_dt = datetime.fromisoformat(reminder["datetime"])
            if reminder_dt < now:
                overdue += 1
            elif reminder_dt <= now + timedelta(hours=24):
                upcoming_24h += 1
        
        return json.dumps({
            "success": True,
            "stats": {
                "total_reminders": total,
                "completed": completed,
                "pending": pending,
                "overdue": overdue,
                "upcoming_24h": upcoming_24h
            }
        }, indent=2)
        
    except Exception as e:
        logger.error(f"Error getting stats: {e}")
        return json.dumps({
            "success": False,
            "error": f"Failed to get statistics: {str(e)}"
        }, indent=2)


if __name__ == "__main__":
    logger.info("Starting Xiaozhi Reminder Server...")
    mcp.run(transport="stdio")
