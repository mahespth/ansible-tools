
# AAP Redis issues and debug

status of services:
  https://access.redhat.com/solutions/7129046
  https://aap.local/api/gateway/v1/status

```json
{
  "status": "failed"
  "service_name": "redis"
  "nodes": {}
  "response": {
    "status": "failed",
    "mode": "standalone"
   }
  }
```

```bash
ansible all -b -m shell -a '
set -e
{
  cmd="redis-cli -s /run/redis/redis.sock"
  echo "=== $(hostname) ==="
  $cmd PING
  $cmd INFO all
  $cmd CONFIG GET \*
  $cmd LATENCY DOCTOR
  echo "SLOWLOG LEN:" $( $cmd SLOWLOG LEN )
  $cmd SLOWLOG GET 25
  $cmd CLIENT LIST
  $cmd MEMORY STATS
  $cmd MEMORY DOCTOR
  echo "DBSIZE:" $( $cmd DBSIZE )
} 2>&1
'
```


# Check latency

```bash
redis-cli -s /run/redis/redis.sock --latency
```


# Monitor

```bash
redis-cli -s /run/redis/redis.sock MONITOR
```


```bash
awx-manage print_settings | egrep -i 'REDIS|BROKER_URL|CHANNEL|CACHE'
```

Redhat suggested this could be due to stuck jobs, however I didnt see that.

```bash
awx-manage shell_plus
>>> UnifiedJob.objects.filter(status='pending')
>>> UnifiedJob.objects.filter(status='pending').update(status='canceled')
```
