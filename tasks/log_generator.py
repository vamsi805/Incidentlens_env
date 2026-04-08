"""
Shared log generation utilities for IncidentLens tasks.

Generates realistic application logs with timestamps, service names,
log levels, and messages that mimic real microservice architectures.
"""

import random
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple


SERVICES = ["api-gateway", "auth-service", "user-service", "order-service",
            "payment-service", "inventory-service", "notification-service",
            "search-service", "cache-layer", "db-primary", "db-replica",
            "queue-worker", "scheduler"]

INFO_MESSAGES = {
    "api-gateway": [
        "Handled request GET /api/v1/users in {latency}ms",
        "Handled request POST /api/v1/orders in {latency}ms",
        "Handled request GET /api/v1/products in {latency}ms",
        "Rate limit check passed for client_id={client_id}",
        "Request routed to {target_service}",
        "Health check OK",
    ],
    "auth-service": [
        "User {user_id} authenticated successfully",
        "Token refreshed for user {user_id}",
        "Session created session_id={session_id}",
        "JWT validated for request_id={request_id}",
    ],
    "user-service": [
        "Fetched profile for user {user_id}",
        "Updated preferences for user {user_id}",
        "Cache hit for user {user_id}",
    ],
    "order-service": [
        "Order {order_id} created for user {user_id}",
        "Order {order_id} status updated to {status}",
        "Fetched order history for user {user_id}",
    ],
    "payment-service": [
        "Payment {payment_id} processed successfully amount=${amount}",
        "Payment {payment_id} authorized via {provider}",
        "Refund initiated for payment {payment_id}",
    ],
    "inventory-service": [
        "Stock check for product {product_id}: {quantity} available",
        "Reserved {quantity} units of product {product_id}",
        "Inventory sync completed in {latency}ms",
    ],
    "notification-service": [
        "Email sent to user {user_id} template={template}",
        "Push notification queued for user {user_id}",
        "SMS sent to user {user_id}",
    ],
    "search-service": [
        "Search query '{query}' returned {count} results in {latency}ms",
        "Index refresh completed",
        "Search cache warmed for category {category}",
    ],
    "cache-layer": [
        "Cache hit key={cache_key} ttl={ttl}s",
        "Cache miss key={cache_key}",
        "Cache eviction: {count} keys expired",
    ],
    "db-primary": [
        "Query executed in {latency}ms rows_affected={rows}",
        "Connection pool: {active}/{max} active connections",
        "Checkpoint completed in {latency}ms",
    ],
    "db-replica": [
        "Replication lag: {lag}ms",
        "Read query routed to replica in {latency}ms",
        "Replica sync status: OK",
    ],
    "queue-worker": [
        "Processed message queue={queue_name} in {latency}ms",
        "Message acknowledged id={msg_id}",
        "Queue depth: {depth} messages pending",
    ],
    "scheduler": [
        "Cron job {job_name} started",
        "Cron job {job_name} completed in {latency}ms",
        "Scheduled task {task_name} queued",
    ],
}

WARN_MESSAGES = {
    "api-gateway": [
        "Slow response: GET /api/v1/{endpoint} took {latency}ms (threshold: 500ms)",
        "Rate limit approaching for client_id={client_id}: {count}/1000 requests",
        "Upstream {target_service} response time elevated: {latency}ms",
    ],
    "auth-service": [
        "Failed login attempt for user {user_id} from ip={ip}",
        "Token near expiry for session {session_id}",
    ],
    "db-primary": [
        "Connection pool utilization high: {active}/{max} ({pct}%)",
        "Slow query detected: {latency}ms on table {table}",
        "Lock wait timeout approaching on table {table}",
    ],
    "db-replica": [
        "Replication lag increasing: {lag}ms",
        "Replica falling behind primary by {lag}ms",
    ],
    "cache-layer": [
        "Cache hit rate dropped to {rate}%",
        "Memory usage at {pct}% of allocated",
    ],
    "queue-worker": [
        "Message processing slow: {latency}ms for queue {queue_name}",
        "Queue depth increasing: {depth} messages pending",
        "Consumer lag detected on queue {queue_name}",
    ],
}


def _fill_template(template: str, rng: random.Random) -> str:
    """Fill a log message template with random values."""
    replacements = {
        "{latency}": str(rng.randint(1, 2000)),
        "{client_id}": f"client-{rng.randint(100, 999)}",
        "{target_service}": rng.choice(SERVICES),
        "{user_id}": f"usr-{rng.randint(10000, 99999)}",
        "{session_id}": f"sess-{rng.randint(100000, 999999)}",
        "{request_id}": f"req-{rng.randint(100000, 999999)}",
        "{order_id}": f"ord-{rng.randint(10000, 99999)}",
        "{payment_id}": f"pay-{rng.randint(10000, 99999)}",
        "{product_id}": f"prod-{rng.randint(100, 999)}",
        "{amount}": f"{rng.uniform(5, 500):.2f}",
        "{provider}": rng.choice(["stripe", "paypal", "square"]),
        "{quantity}": str(rng.randint(1, 100)),
        "{status}": rng.choice(["processing", "shipped", "delivered"]),
        "{template}": rng.choice(["order_confirm", "welcome", "reset_password"]),
        "{query}": rng.choice(["laptop", "headphones", "keyboard", "monitor"]),
        "{count}": str(rng.randint(0, 500)),
        "{category}": rng.choice(["electronics", "clothing", "books"]),
        "{cache_key}": f"cache:{rng.choice(['user', 'product', 'session'])}:{rng.randint(1, 9999)}",
        "{ttl}": str(rng.randint(60, 3600)),
        "{rows}": str(rng.randint(1, 1000)),
        "{active}": str(rng.randint(5, 45)),
        "{max}": "50",
        "{pct}": str(rng.randint(60, 95)),
        "{lag}": str(rng.randint(10, 5000)),
        "{table}": rng.choice(["users", "orders", "products", "payments", "sessions"]),
        "{queue_name}": rng.choice(["orders", "notifications", "analytics", "payments"]),
        "{msg_id}": f"msg-{rng.randint(100000, 999999)}",
        "{depth}": str(rng.randint(10, 10000)),
        "{job_name}": rng.choice(["cleanup", "report", "sync", "backup"]),
        "{task_name}": rng.choice(["daily_report", "index_rebuild", "cache_warm"]),
        "{rate}": str(rng.randint(20, 80)),
        "{ip}": f"{rng.randint(1,255)}.{rng.randint(0,255)}.{rng.randint(0,255)}.{rng.randint(1,255)}",
        "{endpoint}": rng.choice(["users", "orders", "products", "search"]),
    }
    result = template
    for k, v in replacements.items():
        result = result.replace(k, v)
    return result


def generate_baseline_logs(
    rng: random.Random,
    start_time: datetime,
    duration_minutes: int = 60,
    logs_per_minute: int = 8,
    services: Optional[List[str]] = None,
) -> List[Dict[str, str]]:
    """Generate normal baseline logs for a time period."""
    services = services or SERVICES
    logs = []
    current = start_time

    for _ in range(duration_minutes * logs_per_minute):
        service = rng.choice(services)
        # Mostly INFO, some WARN
        if rng.random() < 0.05:
            level = "WARN"
            templates = WARN_MESSAGES.get(service, ["Unexpected condition detected"])
        elif rng.random() < 0.02:
            level = "DEBUG"
            templates = [f"Debug: processing request for {service}"]
        else:
            level = "INFO"
            templates = INFO_MESSAGES.get(service, ["Operation completed"])

        template = rng.choice(templates)
        message = _fill_template(template, rng)

        # Advance time slightly
        current += timedelta(seconds=rng.uniform(0.5, 15))

        logs.append({
            "timestamp": current.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],
            "service": service,
            "level": level,
            "message": message,
        })

    return logs


def format_log_line(entry: Dict[str, str]) -> str:
    """Format a log entry as a standard log line."""
    return f"[{entry['timestamp']}] [{entry['level']:5s}] [{entry['service']}] {entry['message']}"
